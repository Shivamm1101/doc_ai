import os
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response

from pipelines.prefect_pdf_flow import pdf_ingestion_flow
from etl.chroma_client import get_collection
from etl.pdf_embedding import get_embedding_function

from django.db import connection
from .serializers import DocumentListSerializer

@api_view(["POST"])
def upload_pdf(request):
    """
    Upload a PDF → Save to documents/ → Trigger Prefect pipeline
    """
    try:
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No PDF file uploaded"}, status=400)

        # Ensure /documents directory exists
        documents_dir = os.path.join(settings.BASE_DIR, "documents")
        os.makedirs(documents_dir, exist_ok=True)

        # Full path where file will be saved
        save_path = os.path.join(documents_dir, file.name)

        # Save the PDF file
        with open(save_path, "wb+") as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        # Trigger Prefect Flow
        state = pdf_ingestion_flow(save_path)

        return Response({
            "status": "ok",
            "message": "PDF uploaded and ingestion started",
            "file_saved_as": save_path,
            "prefect_state": str(state)
        })
    except Exception as e:
        return Response(
            {"error": f"Failed to process file: {str(e)}"},
            status=500
        )


@api_view(["POST"])
def semantic_search(request):
    """
    Semantic vector search across all PDF chunks stored in ChromaDB.
    Request:
        { "query": "your search question" }

    Returns top 5 most relevant chunks with metadata.
    """

    query = request.data.get("query")
    if not query:
        return Response({"error": "Missing 'query' field"}, status=400)

    # Load vector DB
    collection = get_collection("pdf_chunks")
    embed_fn = get_embedding_function()

    # Convert query into embedding
    query_embedding = embed_fn([query])[0]
    if hasattr(query_embedding, "values"):
        query_embedding = query_embedding.values  # fix for Gemini/OpenAI

    # Perform semantic search
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=5,
        include=["documents", "metadatas", "distances"]
    )

    # Format the response
    output = []
    for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]):

        output.append({
            "text": doc,
            "metadata": meta,
            "score": float(dist)
        })

    return Response({"results": output})



@api_view(["GET"])
def list_documents(request):
    with connection.cursor() as cursor:
        query = """
            SELECT
                dm._dlt_load_id AS document_id,
                dm.pdf_name,
                dm.pdf_type,
                dm.created_at,
                COALESCE(ci.cost_items_count, 0) AS cost_items,
                COALESCE(pt.project_tasks_count, 0) AS project_tasks,
                COALESCE(ur.ura_rules_count, 0) AS ura_rules
            FROM pdf_dataset.documents_master dm
            LEFT JOIN (
                SELECT document_id, COUNT(*) AS cost_items_count
                FROM pdf_dataset.cost_items
                GROUP BY document_id
            ) ci ON dm._dlt_load_id = ci.document_id
            LEFT JOIN (
                SELECT document_id, COUNT(*) AS project_tasks_count
                FROM pdf_dataset.project_tasks
                GROUP BY document_id
            ) pt ON dm._dlt_load_id = pt.document_id
            LEFT JOIN (
                SELECT document_id, COUNT(*) AS ura_rules_count
                FROM pdf_dataset.regulatory_rules
                GROUP BY document_id
            ) ur ON dm._dlt_load_id = ur.document_id
            ORDER BY dm._dlt_load_id DESC;
        """

        try:
            cursor.execute(query)
        except Exception as e:
            return Response({"sql_error": str(e)}, status=500)

        if cursor.description is None:
            return Response({"error": "Query returned no columns"}, status=500)

        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()

    return Response([dict(zip(columns, row)) for row in rows])
