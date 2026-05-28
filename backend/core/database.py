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

def is_ai_comment(github_comment_id):
    """Checks if a given GitHub comment ID belongs to an AI-generated comment."""
    try:
        with get_connection() as conn:
            result = conn.execute(
                "SELECT 1 FROM ai_comments WHERE github_comment_id = ? LIMIT 1",
                (github_comment_id,)
            ).fetchone()
            return result is not None
    except Exception as e:
        logger.error(f"Failed to check AI comment status: {e}")
        return False

def get_latest_ai_comment_for_pr(repo_full_name, pr_number):
    """
    Retrieves the most recent AI comment for a specific PR.
    Returns a dict with comment details, or None if no AI comment exists.
    """
    try:
        with get_connection() as conn:
            result = conn.execute("""
                SELECT id, github_comment_id, file_path, comment_text, score
                FROM ai_comments 
                WHERE repo_full_name = ? AND pr_number = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
            """, (repo_full_name, pr_number)).fetchone()
            
            if result:
                return {
                    "id": result[0],
                    "github_comment_id": result[1],
                    "file_path": result[2],
                    "comment_text": result[3],
                    "score": result[4]
                }
            return None
    except Exception as e:
        logger.error(f"Failed to fetch latest AI comment for PR #{pr_number}: {e}")
        return None

def get_all_ai_comments_for_pr(repo_full_name, pr_number):
    """
    Retrieves all AI comments for a specific PR.
    Returns a list of dicts, ordered by most recent first.
    """
    try:
        with get_connection() as conn:
            results = conn.execute("""
                SELECT id, github_comment_id, file_path, comment_text, score
                FROM ai_comments 
                WHERE repo_full_name = ? AND pr_number = ?
                ORDER BY created_at DESC, id DESC
            """, (repo_full_name, pr_number)).fetchall()
            
            return [
                {
                    "id": row[0],
                    "github_comment_id": row[1],
                    "file_path": row[2],
                    "comment_text": row[3],
                    "score": row[4]
                }
                for row in results
            ]
    except Exception as e:
        logger.error(f"Failed to fetch AI comments for PR #{pr_number}: {e}")
        return []

# Initialize the DB on module import
if not os.path.exists(DB_PATH):
    init_db()

