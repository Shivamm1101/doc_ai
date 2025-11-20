from django.db import models


class DocumentMaster(models.Model):
    document_id = models.FloatField(primary_key=True)
    pdf_name = models.CharField(max_length=255)
    pdf_type = models.CharField(max_length=100)
    created_at = models.DateTimeField()

    class Meta:
        db_table = 'pdf_dataset"."documents_master'
        managed = False

    def __str__(self):
        return self.pdf_name


class CostItem(models.Model):
    cost_id = models.BigAutoField(primary_key=True)
    document = models.ForeignKey(DocumentMaster, on_delete=models.CASCADE)
    item_name = models.TextField()
    quantity = models.FloatField(null=True)
    unit_price_yen = models.FloatField(null=True)
    total_cost_yen = models.FloatField(null=True)
    cost_type = models.CharField(max_length=50)

    class Meta:
        db_table = 'pdf_dataset"."cost_items'
        managed = False


class ProjectTask(models.Model):
    task_id = models.BigAutoField(primary_key=True)
    document = models.ForeignKey(DocumentMaster, on_delete=models.CASCADE)
    task_name = models.CharField(max_length=255)
    duration_days = models.IntegerField(null=True)
    start_date = models.DateField(null=True)
    finish_date = models.DateField(null=True)

    class Meta:
        db_table = 'pdf_dataset"."project_tasks'
        managed = False


class RegulatoryRule(models.Model):
    rule_id = models.BigAutoField(primary_key=True)
    document = models.ForeignKey(DocumentMaster, on_delete=models.CASCADE)
    rule_summary = models.TextField()
    measurement_basis = models.TextField()

    class Meta:
        db_table = 'pdf_dataset"."regulatory_rules'
        managed = False
