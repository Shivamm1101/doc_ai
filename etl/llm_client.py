from openai import OpenAI
import time
from loguru import logger
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------
# MODEL (best for cost-based PDF extraction)
# ---------------------------------------------------------
PRIMARY_MODEL = "gpt-4.1"  

# ---------------------------------------------------------
# API KEY
# ---------------------------------------------------------
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("❌ OPENAI_API_KEY is not set!")

# Initialize client
client = OpenAI(api_key=API_KEY)


# ---------------------------------------------------------
# UNIVERSAL LLM CALLER (OpenAI text-mode)
# ---------------------------------------------------------
def ask_llm(prompt: str, max_retries: int = 6):
    """
    Universal text-mode LLM caller.
    Works for:
      - classification
      - extraction
      - page-wise BOQ parsing
      
    Uses only gpt-4.1-mini to keep cost low.
    Retries on 429/500/503 errors.
    """

    for attempt in range(max_retries):
        try:
            logger.info(f"[LLM] Calling {PRIMARY_MODEL} (Attempt {attempt + 1})...")

            response = client.responses.create(
                model=PRIMARY_MODEL,
                input=prompt
            )

            logger.info("[LLM] Response received.")
            return response.output_text

        except Exception as e:
            err = str(e)

            # Retry for transient API problems
            if (
                "429" in err or
                "503" in err or
                "rate limit" in err.lower() or
                "temporarily" in err.lower()
            ):
                wait = min(2 ** attempt, 15)
                logger.warning(f"[LLM] OpenAI overloaded → retrying in {wait}s...")
                time.sleep(wait)
                continue

            logger.error(f"[LLM] Unexpected error: {e}")
            raise

    # All attempts failed
    raise RuntimeError(f"❌ OpenAI model {PRIMARY_MODEL} failed after all retries.")
