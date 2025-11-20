from unittest.mock import patch
import pytest


@pytest.mark.django_db
def test_search_api(client):
    mock_chroma_result = [
        {
            "text": "Building height must not exceed 12m.",
            "metadata": {"document_id": 1}
        }
    ]

    with patch("django_app.ingestion.api.semantic_search") as mock_chroma:
        mock_chroma.return_value = mock_chroma_result

        with patch("django_app.ingestion.api.llm_answer") as mock_llm:
            mock_llm.return_value = "The maximum height allowed is 12m."

            response = client.post("/api/search/", {"query": "height limit"})

    assert response.status_code == 200
    data = response.json()

    assert "answer" in data
    assert data["answer"] == "The maximum height allowed is 12m."
