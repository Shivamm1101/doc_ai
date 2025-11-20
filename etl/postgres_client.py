import psycopg
from psycopg.rows import dict_row
from loguru import logger
from etl.config import settings   


class PostgresClient:
    def __init__(
        self,
        host=None,
        port=None,
        dbname=None,
        user=None,
        password=None,
    ):
        self.conn_params = {
            "host": host or settings.PG_HOST,
            "port": port or settings.PG_PORT,
            "dbname": dbname or settings.PG_DATABASE,
            "user": user or settings.PG_USER,
            "password": password or settings.PG_PASSWORD
        }

        logger.info(f"Initialized Postgres client for DB={self.conn_params['dbname']}")

    def get_conn(self):
        """Return a fresh psycopg connection."""
        try:
            return psycopg.connect(**self.conn_params, row_factory=dict_row)
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def create_tables(self):
        ddl_statements = [
            """
            CREATE TABLE IF NOT EXISTS documents_master (
                document_id SERIAL PRIMARY KEY,
                document_name VARCHAR(255),
                document_type VARCHAR(100),
                uploaded_at TIMESTAMP DEFAULT NOW()
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS project_tasks (
                task_id SERIAL PRIMARY KEY,
                document_id INT REFERENCES documents_master(document_id) ON DELETE CASCADE,
                task_name VARCHAR(255),
                duration_days INT,
                start_date DATE,
                finish_date DATE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS cost_items (
                cost_id SERIAL PRIMARY KEY,
                document_id INT REFERENCES documents_master(document_id) ON DELETE CASCADE,
                item_name TEXT,
                quantity NUMERIC,
                unit_price_yen NUMERIC,
                total_cost_yen NUMERIC,
                cost_type VARCHAR(50)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS regulatory_rules (
                rule_id SERIAL PRIMARY KEY,
                document_id INT REFERENCES documents_master(document_id) ON DELETE CASCADE,
                rule_summary TEXT,
                measurement_basis TEXT
            );
            """
        ]

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                for ddl in ddl_statements:
                    logger.debug(f"Executing DDL:\n{ddl}")
                    cur.execute(ddl)
            conn.commit()

        logger.success("All PostgreSQL tables created successfully")

    def insert_document(self, document_name, document_type):
        sql = """
        INSERT INTO documents_master (document_name, document_type)
        VALUES (%s, %s)
        RETURNING document_id;
        """

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (document_name, document_type))
                row = cur.fetchone()
                document_id = row["document_id"]
                conn.commit()

        logger.success(f"Inserted document '{document_name}' → id={document_id}")
        return document_id

    def insert_project_tasks(self, document_id, records):
        sql = """
        INSERT INTO project_tasks (document_id, task_name, duration_days, start_date, finish_date)
        VALUES (%s, %s, %s, %s, %s);
        """

        clean_records = []
        for r in records:
            clean_records.append((
                document_id,
                r.get("task_name"),
                r.get("duration_days"),
                r.get("start_date"),
                r.get("finish_date")
            ))

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, clean_records)
                conn.commit()

        logger.success(f"Inserted {len(records)} project tasks")

    def insert_cost_items(self, document_id, records):
        sql = """
        INSERT INTO cost_items (document_id, item_name, quantity, unit_price_yen, total_cost_yen, cost_type)
        VALUES (%s, %s, %s, %s, %s, %s);
        """

        clean_records = []
        for r in records:
            clean_records.append((
                document_id,
                r.get("item_name"),
                r.get("quantity"),
                r.get("unit_price_yen"),
                r.get("total_cost_yen"),
                r.get("cost_type"),
            ))

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, clean_records)
                conn.commit()

        logger.success(f"Inserted {len(records)} cost items")

    def insert_regulatory_rules(self, document_id, records):
        sql = """
        INSERT INTO regulatory_rules (document_id, rule_summary, measurement_basis)
        VALUES (%s, %s, %s);
        """

        clean_records = []
        for r in records:
            clean_records.append((
                document_id,
                r.get("rule_summary"),
                r.get("measurement_basis")
            ))

        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, clean_records)
                conn.commit()

        logger.success(f"Inserted {len(records)} regulatory rules")
