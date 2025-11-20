import os, sys
import re
import json
from loguru import logger

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from etl.llm_client import ask_llm
from etl.prompts import PDF_CLASSIFICATION_PROMPT
import pdfplumber
import pytesseract
from pdf2image import convert_from_path


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text: str) -> str:
    """Normalize text for stable LLM classification."""
    text = text.replace("\x00", "")                     
    text = re.sub(r"[ ]{2,}", " ", text)                
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text


# ============================================================
# TEXT EXTRACTION (PDF → TEXT → LLM)
# ============================================================

def extract_text(pdf_path: str) -> str:
    logger.info(f"[EXTRACT] Reading PDF: {pdf_path}")

    extracted = ""

    # ---- 1) Try direct PDF text extraction ----
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = [(p.extract_text() or "") for p in pdf.pages]
            extracted = "\n".join(pages).strip()
    except Exception as e:
        logger.error(f"[EXTRACT] pdfplumber failed: {e}")

    # ---- 2) OCR fallback if extraction too small ----
    if len(extracted) < 100:
        logger.warning("[EXTRACT] Very small text → Using OCR fallback")

        try:
            images = convert_from_path(pdf_path, dpi=200)
            ocr_texts = [pytesseract.image_to_string(img) for img in images]
            extracted = "\n".join(ocr_texts).strip()
        except Exception as e:
            logger.error(f"[EXTRACT] OCR failed: {e}")

    # ---- 3) Clean text ----
    extracted = clean_text(extracted)

    # ---- 4) Token optimization (Gemini safe limit) ----
    MAX_CHARS = 25000  # ≈ 7–9k input tokens
    if len(extracted) > MAX_CHARS:
        logger.info(f"[EXTRACT] Trimming text {len(extracted)} → {MAX_CHARS}")
        extracted = extracted[:MAX_CHARS] + "\n...[TRUNCATED]..."

    return extracted


# ============================================================
# RAW CLASSIFIER (calls LLM)
# ============================================================

def classify_pdf(pdf_path: str) -> str:
    """
    Calls Gemini with the classification prompt.
    Returns RAW JSON STRING from the LLM.
    """
    logger.info(f"[CLASSIFIER] Running LLM classification → {pdf_path}")

    content = extract_text(pdf_path)

    # Build prompt
    prompt = PDF_CLASSIFICATION_PROMPT.replace("{{CONTENT}}", content)

    # Ask Gemini
    llm_output = ask_llm(prompt)

    logger.info("\n----- RAW LLM RESPONSE -----\n" + llm_output + "\n----------------------------")

    return llm_output


# ============================================================
# PARSED CLASSIFIER (used by Prefect)
# ============================================================

def detect_pdf_type(pdf_path: str) -> dict:
    """
    Calls classify_pdf() to get raw JSON
    → Cleans wrapper formatting
    → Parses into Python dict

    Returns:
    {
        "pdf_type": "construction_costing",
        "layout_type": "table_pdf",
        "flags": {...},
        "reason": "..."
    }
    """
    raw_json = classify_pdf(pdf_path)

    # Removes ```json ... ```
    cleaned = raw_json.strip().strip("```").strip()

    # Sometimes model writes “json” inside the code fence
    cleaned = cleaned.replace("json", "").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"[CLASSIFIER] JSON decode failed: {e}")
        logger.error(f"RAW CONTENT:\n{cleaned}")
        raise e

    logger.success(f"[CLASSIFIER] Final parsed result → {parsed}")
    return parsed


# ============================================================
# TEST HARNESS
# ============================================================

if __name__ == "__main__":
    test_pdf = "documents/Construction planning and costing.pdf"
    result = detect_pdf_type(test_pdf)

    print("\n===== CLEAN STRUCTURED OUTPUT =====\n")
    print(result)
