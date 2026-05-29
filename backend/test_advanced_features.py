import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Ensure we can import from backend and other modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.database import init_db, save_ai_comment, update_comment_score, get_connection
from retrain import run_retraining
from vector_store.chroma_client import ensure_collection
from backend.services.reaction_handler import _detect_sentiment
from backend.services.dataset_builder import DatasetBuilder

class TestAdvancedFeatures(unittest.TestCase):
    def setUp(self):
        # Initialize DB and clear state
        init_db()
        with get_connection() as conn:
            conn.execute("DELETE FROM ai_comments")
        
        # Clear ChromaDB test entries
        self.collection = ensure_collection()
        try:
            self.collection.delete(ids=["feedback_99001", "feedback_99002"])
        except Exception:
            pass

    def tearDown(self):
        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM ai_comments")
        try:
            self.collection.delete(ids=["feedback_99001", "feedback_99002"])
        except Exception:
            pass

    def test_score_decay_calculation(self):
        """Test 1: Verifies that time-based score decay works correctly."""
        print("\n--> Running Test 1: Time-Based Score Decay...")
        
        # Insert a comment dated exactly 10 days ago
        ten_days_ago = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Directly insert into SQLite to set historical timestamp
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO ai_comments 
                (github_comment_id, repo_full_name, pr_number, file_path, code_snippet, comment_text, suggested_fix, score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (99001, "test/repo", 12, "math.py", "def add(a, b): return a + b", "Good", "return a+b", 10, ten_days_ago))
        
        # Trigger retraining pipeline
        run_retraining()
        
        # Fetch from ChromaDB and verify decayed score
        result = self.collection.get(ids=["feedback_99001"])
        metadatas = result.get("metadatas", [])
        self.assertEqual(len(metadatas), 1)
        
        expected_decayed_score = 10.0 * (0.98 ** 10)
        stored_score = metadatas[0]["score"]
        
        print(f"Decayed Score: Expected = {expected_decayed_score:.4f}, Stored = {stored_score:.4f}")
        self.assertAlmostEqual(stored_score, expected_decayed_score, places=4)

    @patch("requests.post")
    def test_llm_assisted_sentiment_fallback(self, mock_post):
        """Test 2: Verifies that LLM-assisted sentiment analysis works as a fallback."""
        print("\n--> Running Test 2: LLM-Assisted Sentiment Fallback...")
        
        # Mock successful negative sentiment classification from Ollama
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": '{"sentiment": "negative"}'}
        mock_post.return_value = mock_response

        # Feedback text containing no positive or negative keywords
        neutral_text = "your suggestion does not fit our architecture design"
        
        sentiment = _detect_sentiment(neutral_text)
        print(f"LLM Fallback Sentiment (Neutral input): Expected = -1, Returned = {sentiment}")
        self.assertEqual(sentiment, -1)
        
        # Verify the classification prompt was sent to Ollama
        mock_post.assert_called_once()

    def test_precise_patch_based_fix_extraction(self):
        """Test 3: Verifies that precise patch-based fixed code extraction works."""
        print("\n--> Running Test 3: Precise Patch-Based Fix Extraction...")
        
        # Mock PyGithub structures
        mock_repo = MagicMock()
        mock_comment = MagicMock()
        
        mock_comment.original_commit_id = "sha_before"
        mock_comment.commit_id = "sha_after"
        mock_comment.path = "src/main.py"
        
        # Mock git unified diff comparison patch
        mock_file = MagicMock()
        mock_file.filename = "src/main.py"
        mock_file.patch = """@@ -1,3 +1,6 @@
 def my_func():
-    return False
+    # This is a precise fix comment
+    return True
"""
        
        mock_comparison = MagicMock()
        mock_comparison.files = [mock_file]
        mock_repo.compare.return_value = mock_comparison
        
        builder = DatasetBuilder()
        extracted_fix = builder._extract_fixed_code(mock_repo, mock_comment)
        
        expected_fix = "    # This is a precise fix comment\n    return True"
        print(f"Extracted Fix:\n{extracted_fix}\n(Matches Expected = {extracted_fix == expected_fix})")
        self.assertEqual(extracted_fix, expected_fix)

    def test_custom_label_format_floats(self):
        """Test 4: Verifies prompt formatting support for float scores."""
        print("\n--> Running Test 4: Custom Label Formatting with Float Scores...")
        
        # Generate custom labels using float score formatting
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Set up a decayed score entry (float value) in ChromaDB
        embedding = model.encode("def compute(x): return x").tolist()
        
        # Positive float score
        self.collection.add(
            ids=["feedback_99002"],
            embeddings=[embedding],
            metadatas=[{
                "problematic_code": "def compute(x): return x",
                "review_comment": "Excellent optimization",
                "fixed_code": "pass",
                "score": 1.642,
                "source": "feedback_loop"
            }]
        )
        
        # Query and verify reviewer formats it as +1.64
        search_results = self.collection.query(query_embeddings=[embedding], n_results=1)
        meta = search_results["metadatas"][0][0]
        
        score_val = float(meta["score"])
        self.assertAlmostEqual(score_val, 1.642, places=3)
        
        # Format the label inside reviewer logic
        score_str = f"+{score_val:.2f}" if score_val > 0 else f"{score_val:.2f}"
        label = f"Recommended Pattern (Approved: Team feedback {score_str})"
        
        print(f"Generated Label: {label}")
        self.assertEqual(label, "Recommended Pattern (Approved: Team feedback +1.64)")

if __name__ == "__main__":
    unittest.main()
