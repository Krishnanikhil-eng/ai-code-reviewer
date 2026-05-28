import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "database", "feedback_loop.db")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "database", "schema.sql")

def get_connection():
    """Returns a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initializes the database using the schema file."""
    if not os.path.exists(SCHEMA_PATH):
        logger.error(f"Schema file not found at {SCHEMA_PATH}")
        return
        
    with get_connection() as conn:
        with open(SCHEMA_PATH, 'r') as f:
            conn.executescript(f.read())
    logger.info("Feedback loop database initialized.")

def save_ai_comment(github_comment_id, repo_full_name, pr_number, file_path, code_snippet, comment_text, suggested_fix):
    """Saves an AI generated comment to the audit log."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO ai_comments 
                (github_comment_id, repo_full_name, pr_number, file_path, code_snippet, comment_text, suggested_fix)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (github_comment_id, repo_full_name, pr_number, file_path, code_snippet, comment_text, suggested_fix))
            logger.info(f"Saved AI comment {github_comment_id} to tracking database.")
            return True
    except Exception as e:
        logger.error(f"Failed to save AI comment to DB: {e}")
        return False

def update_comment_score(github_comment_id, delta):
    """Updates the score of a comment based on reactions."""
    try:
        with get_connection() as conn:
            conn.execute("""
                UPDATE ai_comments 
                SET score = score + ? 
                WHERE github_comment_id = ?
            """, (delta, github_comment_id))
            logger.info(f"Updated score for comment {github_comment_id} by {delta}.")
            return True
    except Exception as e:
        logger.error(f"Failed to update comment score: {e}")
        return False

# Initialize the DB on module import
if not os.path.exists(DB_PATH):
    init_db()
