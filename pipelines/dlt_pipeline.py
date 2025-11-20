import os, sys
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

import json
import uuid
import dlt
from datetime import datetime
from loguru import logger

from etl.chroma_client import get_collection
from etl.pdf_embedding import get_embedding_function


# ================================================================
# 1. CREATE DLT PIPELINE
# ================================================================
def get_dlt_pipeline():
    return dlt.pipeline(
        pipeline_name="pdf_ingestion_pipeline",
        destination="postgres",
        dataset_name="pdf_dataset"
    )


# ================================================================
# 2. INSERT INTO documents_master
# ================================================================
def load_document_record(pipeline, pdf_name, pdf_type):
    logger.info(f"[DLT] Inserting → documents_master ({pdf_name})")

    rows = [{
        "pdf_name": pdf_name,
        "pdf_type": pdf_type,
        "created_at": datetime.utcnow().isoformat()
    }]

    load_info = pipeline.run(
        rows,
        table_name="documents_master",
        write_disposition="append"
    )

    # loads_ids is a list → NOT dict
    try:
        document_id = load_info.loads_ids[0]
    except Exception:
        logger.error(f"[DLT] Unable to extract document_id. load_info={load_info}")
        raise

    logger.success(f"[DLT] document_id = {document_id}")
    return document_id


# ================================================================
# 3. NORMALIZE parsed_data SAFELY
# ================================================================
def normalize_parsed_data(parsed_data):
    """Ensures we always return a list of dictionaries."""
    if isinstance(parsed_data, dict):
        # URA format
        if "structured_data" in parsed_data:
            parsed_data = parsed_data["structured_data"]
        else:
            parsed_data = [parsed_data]

    if not isinstance(parsed_data, list):
        parsed_data = [parsed_data]

    # Only keep dicts
    final_list = []
    for r in parsed_data:
        if isinstance(r, dict):
            final_list.append(r)
        else:
            logger.warning(f"[DLT] Skipping non-dict parsed_data item: {r}")

    return final_list


# ================================================================
# 4. LOAD STRUCTURED DATA INTO POSTGRES
# ================================================================
def load_structured_data(pipeline, pdf_type, document_id, parsed_data):
    logger.info(f"[DLT] Loading structured data for: {pdf_type}")

    parsed_data = normalize_parsed_data(parsed_data)

    # ============================================================
    # A) Construction Costing
    # ============================================================
    if pdf_type == "construction_costing":
        rows = []
        for block in parsed_data:
            for item in block.get("items", []):
                if not isinstance(item, dict):
                    logger.warning(f"[DLT] Skipping bad item: {item}")
                    continue
                rows.append({
                    "document_id": document_id,
                    "item_name": item.get("item_name"),
                    "quantity": item.get("quantity"),
                    "unit_price_yen": item.get("unit_price"),
                    "total_cost_yen": item.get("total_cost"),
                    "cost_type": item.get("cost_type"),
                })

        if rows:
            pipeline.run(rows, table_name="cost_items", write_disposition="append")
            logger.success(f"[DLT] Inserted {len(rows)} construction cost rows")

    # ============================================================
    # B) Project Schedule
    # ============================================================
    elif pdf_type == "project_schedule":
        rows = []
        for t in parsed_data:
            rows.append({
                "document_id": document_id,
                "task_name": t.get("task_name"),
                "duration_days": t.get("duration_days"),
                "start_date": t.get("start_date"),
                "finish_date": t.get("finish_date"),
            })

        if rows:
            pipeline.run(rows, table_name="project_tasks", write_disposition="append")
            logger.success(f"[DLT] Inserted {len(rows)} project tasks")

    # ============================================================
    # C) URA Circular
    # ============================================================
    elif pdf_type == "ura_circular":
        rows = []
        for r in parsed_data:
            rows.append({
                "document_id": document_id,
                "rule_summary": r.get("rule_summary"),
                "measurement_basis": r.get("measurement_basis"),
            })

        if rows:
            pipeline.run(rows, table_name="regulatory_rules", write_disposition="append")
            logger.success(f"[DLT] Inserted {len(rows)} regulatory_rules rows")

    else:
        logger.warning(f"[DLT] Unsupported pdf_type: {pdf_type}")

    logger.success("[DLT] Structured data load complete!")


# ================================================================
# 5. STORE CHUNKS + EMBEDDINGS IN CHROMADB
# ================================================================
def store_chunks_in_chroma_with_doc_id(chunks, document_id):
    logger.info(f"[CHROMA] Preparing {len(chunks)} chunks for DB insertion...")

    collection = get_collection("pdf_chunks")
    embed_fn = get_embedding_function()

    cleaned = []

    for c in chunks:
        if "id" not in c:
            c["id"] = str(uuid.uuid4())

        if "metadata" not in c or not isinstance(c["metadata"], dict):
            c["metadata"] = {}

        c["metadata"]["document_id"] = document_id

        if "text" not in c or not c["text"].strip():
            logger.warning("[CHROMA] Skipping empty chunk")
            continue

        cleaned.append(c)

    if not cleaned:
        logger.warning("[CHROMA] No valid chunks to insert.")
        return

    ids = [c["id"] for c in cleaned]
    texts = [c["text"] for c in cleaned]
    metadatas = [c["metadata"] for c in cleaned]

    vectors = embed_fn(texts)
    vectors = [v.values if hasattr(v, "values") else v for v in vectors]

    collection.add(
        ids=ids,
        embeddings=vectors,
        documents=texts,
        metadatas=metadatas
    )

    logger.success(f"[CHROMA] Stored {len(cleaned)} chunks.")


# ================================================================
# 6. FINAL WRAPPER
# ================================================================
def load_document_into_system(pdf_name, pdf_type, parsed_data, chunks):
    logger.info("[DLT] Starting full ingestion pipeline...")

    pipeline = get_dlt_pipeline()
    document_id = load_document_record(pipeline, pdf_name, pdf_type)

    load_structured_data(pipeline, pdf_type, document_id, parsed_data)
    store_chunks_in_chroma_with_doc_id(chunks, document_id)

    logger.success("🎉 Document stored successfully in Postgres + Chroma!")
    return document_id
