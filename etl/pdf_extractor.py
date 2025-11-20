import os
import sys
import json
from textwrap import shorten
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

import pdfplumber

from etl.llm_client import ask_llm
from etl.prompts import (
    CONSTRUCTION_PROCESS_PROMPT,
    PROJECT_SCHEDULE_PROMPT,
    REGULATORY_RULES_PROMPT,
    COSTING_EXTRACTION_PAGE_PROMPT,
)

# ----------------- CONCURRENCY LIMITS -----------------
# Max PDFs processed in parallel
MAX_DOC_WORKERS = 4
# Max pages (LLM calls) per PDF in parallel
MAX_PAGE_WORKERS = 4

PROMPT_MAP = {
    "construction_process": CONSTRUCTION_PROCESS_PROMPT,
    "construction_costing": COSTING_EXTRACTION_PAGE_PROMPT,
    "project_schedule": PROJECT_SCHEDULE_PROMPT,
    "ura_circular": REGULATORY_RULES_PROMPT,
}


# --------------------------------------------------------------------
# Helper: serialize a pdfplumber table into markdown-like text
# --------------------------------------------------------------------
def table_to_markdown(table: list[list[str]]) -> str:
    """
    Convert a single pdfplumber table (list of rows) into a markdown-ish string.
    We keep the first non-empty row as header.
    """
    if not table:
        return ""

    # Clean cells
    cleaned = []
    for row in table:
        cleaned.append([(cell or "").replace("\n", " ").strip() for cell in row])

    # find first non-empty row as header
    header_idx = 0
    for idx, row in enumerate(cleaned):
        if any(cell for cell in row):
            header_idx = idx
            break

    header = cleaned[header_idx]
    body = cleaned[header_idx + 1 :]

    # Build markdown
    # Ensure all rows have same length
    max_cols = max(len(r) for r in cleaned)
    norm = lambda r: r + [""] * (max_cols - len(r))

    header = norm(header)
    body = [norm(r) for r in body]

    lines = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")

    for row in body:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def extract_page_content(page, page_number: int) -> dict:
    """
    Extract text + tables from a single pdfplumber page.
    Returns dict with 'text' and 'tables_markdown'.
    """
    text = page.extract_text() or ""
    text = text.strip()

    # limit raw text length to save tokens
    if len(text) > 6000:
        text = text[:6000]

    # tables
    try:
        tables = page.extract_tables() or []
    except Exception as e:
        logger.warning(f"[PDF] Table extraction failed on page {page_number}: {e}")
        tables = []

    md_tables = []
    for t_idx, tbl in enumerate(tables, start=1):
        md = table_to_markdown(tbl)
        if md.strip():
            md_tables.append(f"### Table {t_idx}\n{md}")

    tables_markdown = "\n\n".join(md_tables)

    return {
        "page_number": page_number,
        "text": text,
        "tables_markdown": tables_markdown,
    }


# --------------------------------------------------------------------
# Safe JSON loader for LLM responses
# --------------------------------------------------------------------
def safe_json_loads(raw):
    """
    Try to parse JSON from an LLM response.
    Strips code fences and trailing text if needed.
    """
    if isinstance(raw, dict) or isinstance(raw, list):
        return raw

    s = str(raw).strip()

    # strip common ```json ... ``` wrappers
    if s.startswith("```"):
        # remove leading/trailing backticks
        s = s.strip("`")
        # after stripping backticks, sometimes 'json\n[ ... ]'
        if s.lower().startswith("json"):
            s = s[4:].lstrip()

    # try direct parse
    try:
        return json.loads(s)
    except Exception:
        # heuristic: keep only substring from first '[' to last ']'
        try:
            start = s.index("[")
            end = s.rindex("]")
            snippet = s[start : end + 1]
            return json.loads(snippet)
        except Exception as e:
            logger.error(f"[JSON] Failed to parse LLM JSON: {e}")
            return []


# --------------------------------------------------------------------
# Single-page LLM worker (used in thread pool)
# --------------------------------------------------------------------
def _process_page_with_llm(
    pdf_type: str,
    prompt_template: str,
    page_info: dict,
):
    """
    Build prompt for a single page, call LLM, parse JSON.
    Returns (page_number, list_of_items).
    """
    page_number = page_info["page_number"]
    text = page_info["text"]
    tables_md = page_info["tables_markdown"]

    # ------------- build LLM prompt -------------
    if pdf_type == "construction_costing":
        # COSTING_EXTRACTION_PAGE_PROMPT is assumed to have
        # {{PAGE_NUMBER}}, {{PAGE_TEXT}}, {{PAGE_TABLES}} placeholders
        prompt = (
            prompt_template
            .replace("{{PAGE_NUMBER}}", str(page_number))
            .replace("{{PAGE_TEXT}}", text)
            .replace("{{PAGE_TABLES}}", tables_md)
        )
    else:
        # For other types, prompts are "instruction only".
        # We append the actual page content at the end.
        content_blocks = [f"Page number: {page_number}"]
        if text:
            content_blocks.append("PAGE TEXT:\n" + text)
        if tables_md:
            content_blocks.append("PAGE TABLES (markdown):\n" + tables_md)

        page_block = "\n\n".join(content_blocks)

        prompt = prompt_template.strip() + "\n\n" + page_block

    # ------------- call LLM -------------
    logger.info(f"[LLM] Extracting data from page {page_number} ({pdf_type})...")
    llm_raw = ask_llm(prompt)

    page_results = safe_json_loads(llm_raw)

    if not isinstance(page_results, list):
        logger.warning(f"[LLM] Non-list JSON for page {page_number}, skipping.")
        return page_number, []

    # For non-costing types, tag page_number if not present
    if pdf_type in ("construction_process", "project_schedule", "ura_circular"):
        tagged = []
        for obj in page_results:
            if isinstance(obj, dict):
                if "page_number" not in obj:
                    obj["page_number"] = page_number
                tagged.append(obj)
            else:
                tagged.append(obj)
        page_results = tagged

    return page_number, page_results


# --------------------------------------------------------------------
# Main per-PDF processor (now supports all pdf_types) + page-level parallel
# --------------------------------------------------------------------
def process_single_pdf(pdf_path: str, classifier: dict) -> dict:
    pdf_type = classifier["pdf_type"]
    logger.info(f"[PROCESS] PDF detected as → {pdf_type}")

    if pdf_type not in PROMPT_MAP:
        raise ValueError(f"Unknown pdf_type '{pdf_type}'. Supported: {list(PROMPT_MAP.keys())}")

    prompt_template = PROMPT_MAP[pdf_type]

    # -------- First: extract all pages (sequential pdfplumber) --------
    pages_to_process = []
    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)
        logger.info(f"[PROCESS] Total pages: {num_pages}")

        for page_index, page in enumerate(pdf.pages, start=1):
            logger.info(f"[PAGE] Reading page {page_index}/{num_pages}")
            page_info = extract_page_content(page, page_index)
            text = page_info["text"]
            tables_md = page_info["tables_markdown"]

            # skip empty pages
            if not text and not tables_md:
                logger.info(f"[PAGE] Page {page_index}: empty text & tables, skipping.")
                continue

            # For costing PDFs, skip pages with no digits at all to save tokens
            if pdf_type == "construction_costing":
                if not any(c.isdigit() for c in (text + tables_md)):
                    logger.info(f"[PAGE] Page {page_index}: no digits, skipping (costing).")
                    continue

            pages_to_process.append(page_info)

    if not pages_to_process:
        logger.warning("[PROCESS] No pages selected for LLM processing.")
        structured = []
    else:
        # -------- Second: call LLM per page (possibly in parallel) --------
        all_results_by_page = {}

        if len(pages_to_process) == 1:
            # single page → no multithreading
            page_number, items = _process_page_with_llm(
                pdf_type,
                prompt_template,
                pages_to_process[0],
            )
            all_results_by_page[page_number] = items
        else:
            # multiple pages → limited parallelism
            workers = min(MAX_PAGE_WORKERS, len(pages_to_process))
            logger.info(
                f"[PROCESS] Starting page-level thread pool with {workers} workers "
                f"for {len(pages_to_process)} pages."
            )
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_page = {
                    executor.submit(
                        _process_page_with_llm,
                        pdf_type,
                        prompt_template,
                        page_info,
                    ): page_info["page_number"]
                    for page_info in pages_to_process
                }

                for future in as_completed(future_to_page):
                    page_number = future_to_page[future]
                    try:
                        pn, items = future.result()
                        all_results_by_page[pn] = items
                    except Exception as e:
                        logger.error(f"[PROCESS] Page {page_number} failed in thread: {e}")
                        all_results_by_page.setdefault(page_number, [])

        # flatten in page order
        structured = []
        for pn in sorted(all_results_by_page.keys()):
            structured.extend(all_results_by_page[pn])

    return {
        "filename": os.path.basename(pdf_path),
        "pdf_type": pdf_type,
        "classifier_info": classifier,
        "structured_data": structured,
    }


# --------------------------------------------------------------------
# Multi-PDF processor (document-level parallelism)
# --------------------------------------------------------------------
def process_many_pdfs(pdf_paths: list[str]) -> list[dict]:
    """
    Process multiple PDFs. If only 1 → sequential.
    If 2+ → parallel up to MAX_DOC_WORKERS.
    """
    from etl.pdf_classifier import detect_pdf_type

    jobs = []
    for path in pdf_paths:
        logger.info(f"[CLASSIFY] Detecting type for: {path}")
        classifier = detect_pdf_type(path)
        jobs.append((path, classifier))

    results = []

    if len(jobs) == 1:
        # single document → no doc-level multithreading
        path, classifier = jobs[0]
        results.append(process_single_pdf(path, classifier))
    else:
        workers = min(MAX_DOC_WORKERS, len(jobs))
        logger.info(
            f"[MULTI] Starting doc-level thread pool with {workers} workers "
            f"for {len(jobs)} PDFs."
        )
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_path = {
                executor.submit(process_single_pdf, path, classifier): path
                for (path, classifier) in jobs
            }

            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    logger.error(f"[MULTI] Failed to process {path}: {e}")

    return results


if __name__ == "__main__":
    from etl.pdf_classifier import detect_pdf_type

    # If you pass PDFs as CLI args → use those
    # else default to the single test PDF in documents.
    if len(sys.argv) > 1:
        input_pdfs = sys.argv[1:]
    else:
        # single test file
        input_pdfs = [
            os.path.join(ROOT_DIR, "documents", "Project schedule document.pdf")
        ]

    # Normalize paths
    input_pdfs = [os.path.abspath(p) for p in input_pdfs]

    if len(input_pdfs) == 1:
        test_pdf = input_pdfs[0]
        logger.info(f"Testing extraction → {test_pdf}")

        classifier = detect_pdf_type(test_pdf)
        print("\nCLASSIFIER OUTPUT:\n", classifier)

        result = process_single_pdf(test_pdf, classifier)

        print("\n\n================== STRUCTURED OUTPUT ==================\n")
        print(json.dumps(result["structured_data"], indent=2))
        print("\n=======================================================\n")

        out_name = f"output_{os.path.splitext(os.path.basename(test_pdf))[0]}.json"
        with open(out_name, "w") as f:
            json.dump(result["structured_data"], f, indent=2)
        print(f"Saved output to {out_name}")
    else:
        logger.info(f"Processing {len(input_pdfs)} PDFs in parallel...")
        results = process_many_pdfs(input_pdfs)

        for res in results:
            fname = res["filename"]
            structured = res["structured_data"]
            out_name = f"output_{os.path.splitext(os.path.basename(fname))[0]}.json"
            with open(out_name, "w") as f:
                json.dump(structured, f, indent=2)
            print(f"[DONE] {fname} → {out_name}")
