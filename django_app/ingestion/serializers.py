from rest_framework import serializers
from .models import DocumentMaster


class DocumentListSerializer(serializers.ModelSerializer):
    structured_rows = serializers.IntegerField()
    chunk_count = serializers.IntegerField()

    class Meta:
        model = DocumentMaster
        fields = [
            "document_id",
            "pdf_name",
            "pdf_type",
            "created_at",
            "structured_rows",
            "chunk_count"
        ]
