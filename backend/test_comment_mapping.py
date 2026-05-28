"""
Test script to verify the comment-reply feedback mapping works end-to-end.
Tests: database queries, sentiment detection, and AI comment mapping.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.database import (
    init_db, save_ai_comment, is_ai_comment,
    get_latest_ai_comment_for_pr, get_all_ai_comments_for_pr,
    update_comment_score, get_connection
)
from backend.services.reaction_handler import _detect_sentiment, _find_target_ai_comment

def run_tests():
    print("=" * 50)
    print("COMMENT-REPLY FEEDBACK MAPPING TESTS")
    print("=" * 50)

    # Setup: Clean DB
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM ai_comments")

    # Save 2 AI comments on the same PR (different files)
    save_ai_comment(1001, "test/repo", 5, "src/main.py", "code1", "Review for main.py", "fix1")
    save_ai_comment(1002, "test/repo", 5, "src/utils.py", "code2", "Review for utils.py", "fix2")

    passed = 0
    failed = 0

    # Test 1: is_ai_comment
    r1 = is_ai_comment(1001)
    r2 = is_ai_comment(9999)
    status = "PASS" if r1 == True and r2 == False else "FAIL"
    print(f"\n[{status}] Test 1 - is_ai_comment: AI=1001 -> {r1}, Random=9999 -> {r2}")
    passed += 1 if status == "PASS" else 0
    failed += 1 if status == "FAIL" else 0

    # Test 2: get_latest_ai_comment_for_pr
    latest = get_latest_ai_comment_for_pr("test/repo", 5)
    status = "PASS" if latest and latest["github_comment_id"] == 1002 else "FAIL"
    print(f"[{status}] Test 2 - Latest AI comment on PR #5: id={latest['github_comment_id']}, file={latest['file_path']}")
    passed += 1 if status == "PASS" else 0
    failed += 1 if status == "FAIL" else 0

    # Test 3: get_all_ai_comments_for_pr
    all_comments = get_all_ai_comments_for_pr("test/repo", 5)
    status = "PASS" if len(all_comments) == 2 else "FAIL"
    print(f"[{status}] Test 3 - Total AI comments on PR #5: {len(all_comments)}")
    passed += 1 if status == "PASS" else 0
    failed += 1 if status == "FAIL" else 0

    # Test 4: Sentiment detection
    s1 = _detect_sentiment("good bot, thanks!")
    s2 = _detect_sentiment("wrong suggestion")
    s3 = _detect_sentiment("just a question")
    status = "PASS" if s1 == 1 and s2 == -1 and s3 == 0 else "FAIL"
    print(f"[{status}] Test 4 - Sentiment: positive={s1}, negative={s2}, neutral={s3}")
    passed += 1 if status == "PASS" else 0
    failed += 1 if status == "FAIL" else 0

    # Test 5: Comment mapping - mention specific file
    target_main = _find_target_ai_comment("the review on main.py is correct", "test/repo", 5)
    status = "PASS" if target_main and target_main["file_path"] == "src/main.py" else "FAIL"
    print(f"[{status}] Test 5a - File match 'main.py': -> {target_main['file_path'] if target_main else None}")
    passed += 1 if status == "PASS" else 0
    failed += 1 if status == "FAIL" else 0

    target_utils = _find_target_ai_comment("utils.py fix looks wrong", "test/repo", 5)
    status = "PASS" if target_utils and target_utils["file_path"] == "src/utils.py" else "FAIL"
    print(f"[{status}] Test 5b - File match 'utils.py': -> {target_utils['file_path'] if target_utils else None}")
    passed += 1 if status == "PASS" else 0
    failed += 1 if status == "FAIL" else 0

    # Test 6: Comment mapping - no file mentioned (falls back to latest)
    target_fallback = _find_target_ai_comment("good bot", "test/repo", 5)
    status = "PASS" if target_fallback and target_fallback["github_comment_id"] == 1002 else "FAIL"
    print(f"[{status}] Test 6 - Fallback to latest: -> id={target_fallback['github_comment_id'] if target_fallback else None}")
    passed += 1 if status == "PASS" else 0
    failed += 1 if status == "FAIL" else 0

    # Test 7: No AI comments on a different PR
    target_none = _find_target_ai_comment("good bot", "test/repo", 99)
    status = "PASS" if target_none is None else "FAIL"
    print(f"[{status}] Test 7 - No AI comments on PR #99: -> {target_none}")
    passed += 1 if status == "PASS" else 0
    failed += 1 if status == "FAIL" else 0

    # Test 8: End-to-end score update via comment feedback
    target = _find_target_ai_comment("main.py looks great, good catch!", "test/repo", 5)
    if target:
        update_comment_score(target["github_comment_id"], 1)
    with get_connection() as conn:
        row = conn.execute("SELECT score FROM ai_comments WHERE github_comment_id = 1001").fetchone()
    status = "PASS" if row and row[0] == 1 else "FAIL"
    print(f"[{status}] Test 8 - E2E: Feedback on main.py updated score to {row[0] if row else 'N/A'}")
    passed += 1 if status == "PASS" else 0
    failed += 1 if status == "FAIL" else 0

    # Cleanup
    with get_connection() as conn:
        conn.execute("DELETE FROM ai_comments")

    print("\n" + "=" * 50)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 50)

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
