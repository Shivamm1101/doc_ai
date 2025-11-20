import pytest
from django.db import connection


@pytest.mark.django_db
def test_documents_list(client):
    # Insert fake document_master entry
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO pdf_dataset.documents_master (_dlt_load_id, pdf_name, pdf_type, created_at)
            VALUES (999999, 'sample.pdf', 'ura_circular', NOW());
        """)

        cursor.execute("""
            INSERT INTO pdf_dataset.regulatory_rules (document_id, rule_summary, measurement_basis)
            VALUES (999999, 'Sample Rule', 'Basis');
        """)

    response = client.get("/api/documents/")
    assert response.status_code == 200

    data = response.json()
    assert len(data) > 0

    first = data[0]
    assert first["document_id"] == 999999
    assert first["pdf_name"] == "sample.pdf"
