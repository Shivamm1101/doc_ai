from django.contrib import admin
from .models import DocumentMaster, CostItem, ProjectTask, RegulatoryRule

admin.site.register(DocumentMaster)
admin.site.register(CostItem)
admin.site.register(ProjectTask)
admin.site.register(RegulatoryRule)
