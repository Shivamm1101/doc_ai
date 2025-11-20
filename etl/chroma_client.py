import os
from dotenv import load_dotenv
from loguru import logger
import chromadb

load_dotenv()

# ------------------------------------------------------
# CHROMA STORAGE DIRECTORY (Render or local)
# ------------------------------------------------------
CHROMA_DISK_PATH = os.environ.get("CHROMA_DISK_PATH", "./vectorstore/chroma")

# Ensure directory exists
os.makedirs(CHROMA_DISK_PATH, exist_ok=True)
logger.info(f"[CHROMA] Using disk path: {CHROMA_DISK_PATH}")

# Create a SINGLE persistent client
client = chromadb.PersistentClient(path=CHROMA_DISK_PATH)


# ------------------------------------------------------
# GET COLLECTION
# ------------------------------------------------------
def get_collection(name="pdf_chunks", recreate=False):
    """
    Returns or creates a persistent Chroma collection.
    Embeddings are supplied manually by your pipeline.
    """

    if recreate:
        try:
            client.delete_collection(name)
            logger.warning(f"[CHROMA] Recreated collection: {name}")
        except Exception:
            logger.warning(f"[CHROMA] Collection did not exist: {name}")

    collection = client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"}
    )

    logger.info(f"[CHROMA] Loaded collection: {name}")
    return collection


# ------------------------------------------------------
# ADD PLAIN DOCUMENT (if needed)
# ------------------------------------------------------
def add_document(collection_name: str, doc_id: str, text: str, metadata=None):
    """
    Adds a text document *without embeddings*.
    Only used for basic storage — embeddings stored separately.
    """

    collection = get_collection(collection_name)

    collection.add(
        ids=[doc_id],
        documents=[text],
        metadatas=[metadata or {}]
    )

    logger.success(f"[CHROMA] Added document {doc_id} to {collection_name}")
