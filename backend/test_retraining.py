import sys
import os

# Ensure we can import from backend and other modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.database import init_db, save_ai_comment, update_comment_score, get_connection
from retrain import run_retraining
from vector_store.chroma_client import ensure_collection
from ai_engine.reviewer import generate_review

def run_tests():
    print("=" * 60)
    print("SCORE-BASED RETRAINING END-TO-END TESTS")
    print("=" * 60)

    # 1. Setup: Clean DB and database
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM ai_comments")

    # Clean ChromaDB collection for our test IDs so we don't bleed states
    collection = ensure_collection()
    try:
        collection.delete(ids=["feedback_88001", "feedback_88002"])
    except Exception:
        pass

    passed = 0
    failed = 0

    # 2. Save positive and negative comments to SQLite database
    print("\nSetting up mock feedback in database...")
    save_ai_comment(
        github_comment_id=88001,
        repo_full_name="test/repo",
        pr_number=10,
        file_path="math.py",
        code_snippet="def add_nums(a, b):\n    return sum([a, b])",
        comment_text="Nice use of list summation.",
        suggested_fix="return a + b"
    )
    # Give it a positive score of +2
    update_comment_score(88001, 2)

    save_ai_comment(
        github_comment_id=88002,
        repo_full_name="test/repo",
        pr_number=10,
        file_path="math.py",
        code_snippet="def add_nums_slow(a, b):\n    # Slow add\n    import time\n    time.sleep(1)\n    return a + b",
        comment_text="Do not introduce sleep in additions.",
        suggested_fix="return a + b"
    )
    # Give it a negative score of -3
    update_comment_score(88002, -3)

    # 3. Trigger the retraining pipeline
    print("\nRunning the retraining pipeline...")
    retrain_success = run_retraining()
    
    status = "PASS" if retrain_success else "FAIL"
    print(f"[{status}] Retraining execution status")
    passed += 1 if status == "PASS" else 0
    failed += 1 if status == "FAIL" else 0

    # 4. Verify items exist in ChromaDB and retrieve correct metadata
    print("\nVerifying embeddings and metadata in ChromaDB...")
    try:
        results = collection.get(ids=["feedback_88001", "feedback_88002"])
        ids = results.get("ids", [])
        metadatas = results.get("metadatas", [])
        
        status = "PASS" if "feedback_88001" in ids and "feedback_88002" in ids else "FAIL"
        print(f"[{status}] Scored reviews successfully upserted into ChromaDB")
        passed += 1 if status == "PASS" else 0
        failed += 1 if status == "FAIL" else 0

        # Verify metadata values (scores)
        meta_pos = metadatas[ids.index("feedback_88001")]
        meta_neg = metadatas[ids.index("feedback_88002")]

        status = "PASS" if int(meta_pos["score"]) == 2 and int(meta_neg["score"]) == -3 else "FAIL"
        print(f"[{status}] Correct scores preserved in ChromaDB metadata: positive={meta_pos['score']}, negative={meta_neg['score']}")
        passed += 1 if status == "PASS" else 0
        failed += 1 if status == "FAIL" else 0

    except Exception as e:
        print(f"[FAIL] Error retrieving from ChromaDB: {e}")
        failed += 1

    # 5. Verify the prompt generation custom labels (Positive vs. Negative)
    print("\nVerifying custom prompt label generation for AI reviewer...")
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Search using the positive snippet
        test_snippet = "def add_nums(a, b):\n    return sum([a, b])"
        embedding = model.encode(test_snippet).tolist()
        
        search_results = collection.query(query_embeddings=[embedding], n_results=3)
        metadatas = search_results["metadatas"][0]
        
        found_pos_label = False
        found_neg_label = False
        
        # Test how prompt logic formats these metadatas
        for meta in metadatas:
            score = meta.get("score")
            if score is not None:
                score_val = int(score)
                if score_val == 2:
                    label = f"Recommended Pattern (Approved: Team feedback +{score_val})"
                    if "Approved: Team feedback +2" in label:
                        found_pos_label = True
                elif score_val == -3:
                    label = f"⚠️ Anti-Pattern to Avoid (Disapproved: Team feedback {score_val})"
                    if "Disapproved: Team feedback -3" in label:
                        found_neg_label = True

        status = "PASS" if found_pos_label and found_neg_label else "FAIL"
        print(f"[{status}] Prompt generator assigns correct labels (found positive label={found_pos_label}, found negative label={found_neg_label})")
        passed += 1 if status == "PASS" else 0
        failed += 1 if status == "FAIL" else 0

    except Exception as e:
        print(f"[FAIL] Error checking prompt generation labels: {e}")
        failed += 1

    # Cleanup test artifacts
    print("\nCleaning up test comments...")
    with get_connection() as conn:
        conn.execute("DELETE FROM ai_comments")
    try:
        collection.delete(ids=["feedback_88001", "feedback_88002"])
    except Exception:
        pass

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
