import os
import sys
from typing import List, Dict, Any

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from loguru import logger
from dotenv import load_dotenv

from etl.chroma_client import get_collection
from etl.config import settings

from langchain_openai import OpenAIEmbeddings

load_dotenv()


# ============================================================
#    EMBEDDING CLIENT (LangChain OpenAI)
# ============================================================

def get_embedding_function():
    """
    Returns an embedding function using LangChain's OpenAIEmbeddings.
    Uses:
      - settings.OPENAI_EMBEDDING_MODEL if present
      - else falls back to "text-embedding-3-small"
    """

    model_name = getattr(settings, "OPENAI_EMBEDDING_MODEL", None) or "text-embedding-3-small"

    logger.info(f"Using OpenAIEmbeddings (model={model_name}) for embeddings.")
    emb = OpenAIEmbeddings(model=model_name)

    def embed_fn(texts: List[str]) -> List[List[float]]:
        """
        Embed a list of texts and return list of float vectors.
        """
        return emb.embed_documents(texts)

    return embed_fn


# ============================================================
#    STORE CHUNKS INTO CHROMADB WITH EMBEDDINGS
# ============================================================

def store_chunks_in_chroma(
    chunks: List[Dict[str, Any]],
    collection_name: str = "pdf_chunks",
    batch_size: int = 64,
):
    """
    Takes chunk list:
      [
        { "id": "...", "text": "...", "metadata": {...} },
        ...
      ]

    Computes embeddings (via LangChain OpenAIEmbeddings) → stores in ChromaDB.

    Args:
        chunks: list of chunk dicts from pdf_chunking.chunk_document()
        collection_name: Chroma collection name
        batch_size: number of texts per embedding call
    """

    if not chunks:
        logger.warning("store_chunks_in_chroma called with empty chunk list.")
        return {"stored": 0, "collection": collection_name}

    collection = get_collection(collection_name)
    embed_fn = get_embedding_function()

    ids = [c["id"] for c in chunks]
    texts = [c["text"] for c in chunks]
    metadatas = [c.get("metadata", {}) for c in chunks]

    logger.info(f"[EMBED] Creating embeddings for {len(chunks)} chunks (batch_size={batch_size})...")

    all_vectors: List[List[float]] = []
    total = len(texts)

    # ---- Batched embedding to avoid rate/time issues ----
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_texts = texts[start:end]
        batch_ids = ids[start:end]

        logger.info(f"[EMBED] Embedding batch {start}–{end - 1} (size={len(batch_texts)})...")
        batch_vectors = embed_fn(batch_texts)

        if len(batch_vectors) != len(batch_texts):
            raise ValueError(
                f"Embedding batch size mismatch: got {len(batch_vectors)} vectors for "
                f"{len(batch_texts)} texts (ids {batch_ids[0]}..{batch_ids[-1]})"
            )

        all_vectors.extend(batch_vectors)

    logger.success(f"[EMBED] Generated {len(all_vectors)} embeddings.")

    # ---- Store in Chroma ----
    collection.add(
        ids=ids,
        embeddings=all_vectors,
        documents=texts,
        metadatas=metadatas,
    )

    logger.success(
        f"[CHROMA] Stored {len(chunks)} chunks in ChromaDB collection: {collection_name}"
    )

    return {
        "stored": len(chunks),
        "collection": collection_name,
    }

