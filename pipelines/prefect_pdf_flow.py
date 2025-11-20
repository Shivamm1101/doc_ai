from prefect import flow, task
from loguru import logger
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

# Import modules
from etl.pdf_classifier import detect_pdf_type
from etl.pdf_extractor import process_single_pdf
from etl.pdf_chunking import chunk_document

# DLT loader
from pipelines.dlt_pipeline import load_document_into_system


# ---------------------------------------------------
# TASK 1 — CLASSIFY PDF
# ---------------------------------------------------
@task
def task_1_classify(pdf_path: str):
    logger.info(f"[TASK 1] Classifying PDF: {pdf_path}")
    return detect_pdf_type(pdf_path)


# ---------------------------------------------------
# TASK 2 — RUN STRUCTURED EXTRACTOR
# ---------------------------------------------------
@task
def task_2_extract(pdf_path: str, classifier: dict):
    pdf_type = classifier["pdf_type"]
    logger.info(f"[TASK 2] Extracting structured data for type = {pdf_type}")

    parsed_output = process_single_pdf(pdf_path, classifier)

    logger.success(f"[TASK 2] Extraction completed. Records = {len(parsed_output)}")
    return parsed_output


# ---------------------------------------------------
# TASK 3 — STORE INTO POSTGRES + CHROMA
# ---------------------------------------------------
@task
def task_3_load(pdf_path: str, pdf_type: str, parsed_data):
    logger.info(f"[TASK 3] Chunking full document + loading into system...")

    # --- Normalize parsed_data ---
    if isinstance(parsed_data, dict):
        if "structured_data" in parsed_data:
            parsed_data = parsed_data["structured_data"]
        else:
            parsed_data = [parsed_data]

    if not isinstance(parsed_data, list):
        parsed_data = [parsed_data]

    # --- Chunk full PDF ---
    chunks = chunk_document(pdf_path, pdf_type)

    # --- Load everything into Postgres + Chroma ---
    document_id = load_document_into_system(
        pdf_name=os.path.basename(pdf_path),
        pdf_type=pdf_type,
        parsed_data=parsed_data,
        chunks=chunks,
    )

    return document_id


# ---------------------------------------------------
# MAIN FLOW ENTRYPOINT
# ---------------------------------------------------
@flow
def pdf_ingestion_flow(pdf_path: str):
    logger.info(f"========== START PIPELINE for {pdf_path} ==========")

    # STEP 1: Classify
    classifier = task_1_classify(pdf_path)

    # STEP 2: Extract
    parsed_data = task_2_extract(pdf_path, classifier)

    # STEP 3: Load
    document_id = task_3_load(pdf_path, classifier["pdf_type"], parsed_data)

    logger.success("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
    return {"document_id": document_id}


