import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "database",
    "feedback_loop.db",
)
SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "database",
    "schema.sql",
)


def get_connection():
    """Returns a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)


def init_db():
    """Initializes the database using the schema file."""
    if not os.path.exists(SCHEMA_PATH):
        logger.error(f"Schema file not found at {SCHEMA_PATH}")
        return

    with get_connection() as conn:
        with open(SCHEMA_PATH, "r") as f:
            conn.executescript(f.read())
    logger.info("Feedback loop database initialized.")


def save_ai_comment(
    github_comment_id,
    repo_full_name,
    pr_number,
    file_path,
    code_snippet,
    comment_text,
    suggested_fix,
):
    """Saves an AI generated comment to the audit log."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO ai_comments 
                (github_comment_id, repo_full_name, pr_number, file_path, code_snippet, comment_text, suggested_fix)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    github_comment_id,
                    repo_full_name,
                    pr_number,
                    file_path,
                    code_snippet,
                    comment_text,
                    suggested_fix,
                ),
            )
            logger.info(f"Saved AI comment {github_comment_id} to tracking database.")
            return True
    except Exception as e:
        logger.error(f"Failed to save AI comment to DB: {e}")
        return False


def update_comment_score(github_comment_id, delta):
    """Updates the score of a comment based on reactions."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE ai_comments 
                SET score = score + ? 
                WHERE github_comment_id = ?
            """,
                (delta, github_comment_id),
            )
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
                (github_comment_id,),
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
            result = conn.execute(
                """
                SELECT id, github_comment_id, file_path, comment_text, score
                FROM ai_comments 
                WHERE repo_full_name = ? AND pr_number = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
            """,
                (repo_full_name, pr_number),
            ).fetchone()

            if result:
                return {
                    "id": result[0],
                    "github_comment_id": result[1],
                    "file_path": result[2],
                    "comment_text": result[3],
                    "score": result[4],
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
            results = conn.execute(
                """
                SELECT id, github_comment_id, file_path, comment_text, score
                FROM ai_comments 
                WHERE repo_full_name = ? AND pr_number = ?
                ORDER BY created_at DESC, id DESC
            """,
                (repo_full_name, pr_number),
            ).fetchall()

            return [
                {
                    "id": row[0],
                    "github_comment_id": row[1],
                    "file_path": row[2],
                    "comment_text": row[3],
                    "score": row[4],
                }
                for row in results
            ]
    except Exception as e:
        logger.error(f"Failed to fetch AI comments for PR #{pr_number}: {e}")
        return []


def log_action(user_role, action, target):
    """Logs an administrative action to the audit logs."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (user_role, action, target)
                VALUES (?, ?, ?)
            """,
                (user_role, action, target),
            )
            return True
    except Exception as e:
        logger.error(f"Failed to save audit log: {e}")
        return False


def get_audit_logs(limit=50):
    """Retrieves recent audit logs."""
    try:
        with get_connection() as conn:
            results = conn.execute(
                """
                SELECT id, user_role, action, target, timestamp
                FROM audit_logs
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
            """,
                (limit,),
            ).fetchall()
            return [
                {
                    "id": row[0],
                    "user_role": row[1],
                    "action": row[2],
                    "target": row[3],
                    "timestamp": row[4],
                }
                for row in results
            ]
    except Exception as e:
        logger.error(f"Failed to fetch audit logs: {e}")
        return []


def get_repo_settings(repo_full_name):
    """Retrieves repository-level review configurations."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT strictness, review_mode, custom_prompt, retrieval_depth
                FROM repo_settings
                WHERE repo_full_name = ?
            """,
                (repo_full_name,),
            ).fetchone()
            if row:
                return {
                    "repo_full_name": repo_full_name,
                    "strictness": row[0],
                    "review_mode": row[1],
                    "custom_prompt": row[2],
                    "retrieval_depth": row[3],
                }
    except Exception as e:
        logger.error(f"Failed to fetch repo settings: {e}")

    # Return defaults if not configured
    return {
        "repo_full_name": repo_full_name,
        "strictness": 3,
        "review_mode": "standard",
        "custom_prompt": "",
        "retrieval_depth": 3,
    }


def save_repo_settings(
    repo_full_name, strictness, review_mode, custom_prompt, retrieval_depth
):
    """Saves or updates repository-level review configurations."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO repo_settings (repo_full_name, strictness, review_mode, custom_prompt, retrieval_depth)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(repo_full_name) DO UPDATE SET
                    strictness = excluded.strictness,
                    review_mode = excluded.review_mode,
                    custom_prompt = excluded.custom_prompt,
                    retrieval_depth = excluded.retrieval_depth
            """,
                (
                    repo_full_name,
                    strictness,
                    review_mode,
                    custom_prompt,
                    retrieval_depth,
                ),
            )
            return True
    except Exception as e:
        logger.error(f"Failed to save repo settings: {e}")
        return False


# Initialize the DB on module import (idempotent table creations)
init_db()
