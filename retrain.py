import os
import sys
import logging

# Ensure we can import backend and vector_store modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.core.database import get_connection
from vector_store.chroma_client import upsert_embedding

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("retrainer")


def run_retraining():
    logger.info("Starting score-based retraining pipeline...")

    # 1. Fetch scored comments from SQLite database
    scored_comments = []
    try:
        with get_connection() as conn:
            import sqlite3

            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT github_comment_id, code_snippet, comment_text, suggested_fix, score, created_at "
                "FROM ai_comments WHERE score != 0"
            )
            scored_comments = cursor.fetchall()
    except Exception as e:
        logger.error(f"Failed to query scored comments from SQLite database: {e}")
        return False

    if not scored_comments:
        logger.info(
            "No AI comments with developer feedback (non-zero score) were found in the database. Skipping retraining."
        )
        return True

    logger.info(f"Found {len(scored_comments)} scored comments to process.")

    # 2. Load the sentence transformer model
    try:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading sentence-transformers model 'all-MiniLM-L6-v2'...")
        model = SentenceTransformer("all-MiniLM-L6-v2")
    except ImportError:
        logger.error(
            "sentence-transformers is not installed. Please run `pip install sentence-transformers`"
        )
        return False
    except Exception as e:
        logger.error(f"Failed to load sentence-transformers model: {e}")
        return False

    # 3. Embed and upsert comments
    success_count = 0
    from datetime import datetime

    for row in scored_comments:
        github_comment_id = row["github_comment_id"]
        code_snippet = row["code_snippet"]
        comment_text = row["comment_text"]
        suggested_fix = row["suggested_fix"]
        score = row["score"]
        created_at_str = row["created_at"]

        # Validate that the code snippet is non-empty
        if not code_snippet or not code_snippet.strip():
            logger.warning(
                f"Skipping comment {github_comment_id} due to empty code snippet."
            )
            continue

        # Parse date and compute score decay
        try:
            created_time = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
            age_days = (datetime.utcnow() - created_time).days
            if age_days < 0:
                age_days = 0
        except Exception:
            age_days = 0

        # Exponential decay: weight decreases by 2% per day
        decayed_score = float(score) * (0.98**age_days)

        try:
            # Generate vector embedding for the code snippet
            embedding = model.encode(code_snippet).tolist()

            # Construct structured metadata for retrieval customization
            metadata = {
                "problematic_code": code_snippet,
                "review_comment": comment_text if comment_text else "",
                "fixed_code": suggested_fix if suggested_fix else "",
                "score": float(decayed_score),
                "source": "feedback_loop",
            }

            # Upsert into ChromaDB with unique ID to avoid duplicates
            item_id = f"feedback_{github_comment_id}"
            upsert_embedding(id=item_id, embedding=embedding, metadata=metadata)
            success_count += 1
            logger.info(
                f"[{success_count}/{len(scored_comments)}] Upserted feedback comment {github_comment_id} (Score: {score:+d}, Decayed: {decayed_score:.2f}, Age: {age_days}d)"
            )

        except Exception as e:
            logger.error(f"Failed to process feedback comment {github_comment_id}: {e}")

    logger.info(
        f"Retraining complete. Successfully upserted {success_count} feedback-driven embeddings into ChromaDB."
    )
    return True


if __name__ == "__main__":
    success = run_retraining()
    sys.exit(0 if success else 1)
