import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    PG_HOST = os.getenv("PG_HOST")
    PG_PORT = os.getenv("PG_PORT")
    PG_USER = os.getenv("PG_USER")
    PG_PASSWORD = os.getenv("PG_PASSWORD")
    PG_DATABASE = os.getenv("PG_DATABASE")

    CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR")
    CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME")
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER")

settings = Settings()
