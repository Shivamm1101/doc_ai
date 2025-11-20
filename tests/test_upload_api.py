import io
import pytest
from unittest.mock import patch


@pytest.mark.django_db
def test_upload_pdf(client):
    fake_pdf = io.BytesIO(b"%PDF-1.4 test pdf")
    fake_pdf.name = "test_file.pdf"

    with patch("django_app.ingestion.api.pdf_ingestion_flow") as mock_flow:
        mock_flow.return_value = {"state": "success"}

        response = client.post(
            "/api/upload-pdf/",
            {"file": fake_pdf},
            format="multipart"
        )

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "Ingestion triggered"
