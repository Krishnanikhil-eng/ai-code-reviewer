import sys
import os
import json
import sqlite3
import pytest
from fastapi.testclient import TestClient

# Ensure we can import from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.main import app
from backend.core.database import DB_PATH, get_connection

client = TestClient(app)

def test_feedback_loop():
    # 1. Setup: Ensure database is clean
    from backend.core.database import init_db, save_ai_comment, get_connection
    init_db()
    
    with get_connection() as conn:
        conn.execute("DELETE FROM ai_comments")
    
    # 2. Add a dummy AI comment to track
    comment_id = 998877
    save_ai_comment(
        github_comment_id=comment_id,
        repo_full_name="test/repo",
        pr_number=1,
        file_path="test.py",
        code_snippet="print('hello')",
        comment_text="Nice code",
        suggested_fix="print('hi')"
    )
    
    # Verify initial score is 0
    with get_connection() as conn:
        res = conn.execute("SELECT score FROM ai_comments WHERE github_comment_id = ?", (comment_id,)).fetchone()
        assert res[0] == 0
        
    # 3. Simulate a REACTION event (plus_one)
    reaction_payload = {
        "action": "created",
        "comment": {"id": comment_id},
        "reaction": {"content": "plus_one"},
        "repository": {"full_name": "test/repo"}
    }
    
    # We use DEBUG=True in config to bypass signature verification in tests
    headers = {"x-github-event": "reaction"}
    response = client.post("/webhook", json=reaction_payload, headers=headers)
    assert response.status_code == 200
    
    # Verify score is now 1
    with get_connection() as conn:
        res = conn.execute("SELECT score FROM ai_comments WHERE github_comment_id = ?", (comment_id,)).fetchone()
        assert res[0] == 1
        
    # 4. Simulate DELETING a reaction
    reaction_payload["action"] = "deleted"
    response = client.post("/webhook", json=reaction_payload, headers=headers)
    assert response.status_code == 200
    
    # Verify score is back to 0
    with get_connection() as conn:
        res = conn.execute("SELECT score FROM ai_comments WHERE github_comment_id = ?", (comment_id,)).fetchone()
        assert res[0] == 0

    print("\nFeedback loop verification SUCCESSFUL!")

if __name__ == "__main__":
    # Run the test manually
    try:
        test_feedback_loop()
    except Exception as e:
        print(f"\nVerification FAILED: {e}")
        sys.exit(1)
