import uuid
from typing import List, Dict, Any
from loguru import logger
import pdfplumber


# --------------------------------------------------------
# Helper: normalize chunk
# --------------------------------------------------------

def make_chunk(text: str, metadata: dict) -> dict:
    """
    Standard chunk object format.
    """
    return {
        "id": str(uuid.uuid4()),
        "text": (text or "").strip(),
        "metadata": metadata or {},
    }


# --------------------------------------------------------
# Table → markdown helper (for PDF tables)
# --------------------------------------------------------

def table_to_markdown(table: List[List[str]]) -> str:
    """
    Convert a single pdfplumber table (list of rows) into a markdown-ish string.

    We keep the first non-empty row as header and normalise row lengths.
    """
    if not table:
        return ""

    # Clean cells
    cleaned: List[List[str]] = []
    for row in table:
        cleaned.append([(cell or "").replace("\n", " ").strip() for cell in row])

    # Find first non-empty row as header
    header_idx = 0
    for idx, row in enumerate(cleaned):
        if any(cell for cell in row):
            header_idx = idx
            break

    header = cleaned[header_idx]
    body = cleaned[header_idx + 1 :]

    # normalise row length
    max_cols = max(len(r) for r in cleaned)
    def norm(r: List[str]) -> List[str]:
        return r + [""] * (max_cols - len(r))

    header = norm(header)
    body = [norm(r) for r in body]

    lines: List[str] = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")

    for row in body:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


# --------------------------------------------------------
# Extract content from a single pdfplumber page
# --------------------------------------------------------

def extract_page_content(page, page_number: int, include_tables: bool = True,
                         max_text_chars: int = 8000) -> str:
    """
    Extract text + (optionally) tables (as markdown) from a single page and
    return one big string that will then be chunked.

    - Text is trimmed to max_text_chars to avoid huge prompts.
    """
    # Text
    text = page.extract_text() or ""
    text = text.strip()
    if max_text_chars and len(text) > max_text_chars:
        text = text[:max_text_chars]

    # Tables
    tables_markdown = ""
    if include_tables:
        try:
            tables = page.extract_tables() or []
        except Exception as e:
            logger.warning(f"[PDF] Table extraction failed on page {page_number}: {e}")
            tables = []

        md_tables: List[str] = []
        for t_idx, tbl in enumerate(tables, start=1):
            md = table_to_markdown(tbl)
            if md.strip():
                md_tables.append(f"### Table {t_idx} (page {page_number})\n{md}")

        if md_tables:
            tables_markdown = "\n\n".join(md_tables)

    # Combine
    parts: List[str] = []
    if text:
        parts.append(text)
    if tables_markdown:
        parts.append(tables_markdown)

    full = "\n\n".join(parts).strip()
    return full


# --------------------------------------------------------
# Chunk a single page's text into sliding-window word chunks
# --------------------------------------------------------

def chunk_page_text(page_text: str,
                    pdf_type: str,
                    page_number: int,
                    chunk_size_words: int = 400,
                    overlap_words: int = 50,
                    global_chunk_start_index: int = 0) -> List[dict]:
    """
    Break a single page's text into overlapping word chunks.

    Returns a list of chunk dicts; each chunk's metadata includes:
      - pdf_type
      - page_number
      - local_chunk_index (within that page)
      - global_chunk_index (across whole PDF)
    """
    words = page_text.split()
    chunks: List[dict] = []

    if not words:
        return chunks

    start = 0
    local_index = 0
    global_index = global_chunk_start_index

    while start < len(words):
        end = min(start + chunk_size_words, len(words))
        text_block = " ".join(words[start:end])

        metadata = {
            "pdf_type": pdf_type,
            "page_number": page_number,
            "local_chunk_index": local_index,
            "global_chunk_index": global_index,
        }

        chunks.append(make_chunk(text_block, metadata))

        local_index += 1
        global_index += 1

        if end == len(words):
            break

        # slide window with overlap
        start = max(0, end - overlap_words)

    return chunks


# --------------------------------------------------------
# Main: chunk an entire PDF (universal, page-based)
# --------------------------------------------------------

def chunk_pdf(pdf_path: str,
              pdf_type: str,
              chunk_size_words: int = 400,
              overlap_words: int = 50,
              include_tables: bool = True) -> List[dict]:
    """
    Chunk the *complete PDF* into overlapping text chunks.

    - Reads each page via pdfplumber.
    - Extracts text (and optionally markdown tables).
    - Splits into chunks of chunk_size_words with overlap_words.
    - Adds metadata for pdf_type, page_number, local & global chunk indexes.
    """
    logger.info(f"[CHUNK] Opening PDF for chunking → {pdf_path}")
    chunks: List[dict] = []
    global_chunk_index = 0

    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)
        logger.info(f"[CHUNK] Total pages in PDF: {num_pages}")

        for page_idx, page in enumerate(pdf.pages, start=1):
            logger.info(f"[CHUNK] Processing page {page_idx}/{num_pages}")

            page_text = extract_page_content(
                page,
                page_number=page_idx,
                include_tables=include_tables,
                max_text_chars=8000,
            )

            # Skip empty pages
            if not any(c.isalnum() for c in page_text):
                logger.info(f"[CHUNK] Page {page_idx} is effectively empty; skipping.")
                continue

            page_chunks = chunk_page_text(
                page_text=page_text,
                pdf_type=pdf_type,
                page_number=page_idx,
                chunk_size_words=chunk_size_words,
                overlap_words=overlap_words,
                global_chunk_start_index=global_chunk_index,
            )

            chunks.extend(page_chunks)
            global_chunk_index += len(page_chunks)

    logger.success(f"[CHUNK] Finished chunking PDF. Total chunks: {len(chunks)}")
    return chunks


# --------------------------------------------------------
# Compatibility / single entry point
# --------------------------------------------------------

def chunk_document(pdf_path: str,
                   pdf_type: str,
                   chunk_size_words: int = 400,
                   overlap_words: int = 50,
                   include_tables: bool = True) -> List[dict]:
    """
    Unified entry point (for your pipeline).

    You can call this right after classification:

        classifier = detect_pdf_type(pdf_path)
        pdf_type = classifier["pdf_type"]
        chunks = chunk_document(pdf_path, pdf_type)

    This now chunks the **complete PDF**, not the extracted JSON.
    """
    return chunk_pdf(
        pdf_path=pdf_path,
        pdf_type=pdf_type,
        chunk_size_words=chunk_size_words,
        overlap_words=overlap_words,
        include_tables=include_tables,
    )
