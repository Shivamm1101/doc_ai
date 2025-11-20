from django.urls import path
from .api import upload_pdf, semantic_search,list_documents

urlpatterns = [
    path("upload-pdf/", upload_pdf, name="upload_pdf"),
    path("search/", semantic_search,name="semantic_search"),
    path("documents/", list_documents,name="list_documents"),
]