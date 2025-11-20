import pytest
from django.db import connection

@pytest.fixture(autouse=True)
def _setup_test_tables(db):
    """
    Auto-create minimal tables needed for tests (SQLite).
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents_master (
                _dlt_load_id INTEGER PRIMARY KEY,
                pdf_name TEXT,
                pdf_type TEXT,
                created_at TEXT
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cost_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                item_name TEXT
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                task_name TEXT
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS regulatory_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                rule_summary TEXT
            );
        """)

    yield
