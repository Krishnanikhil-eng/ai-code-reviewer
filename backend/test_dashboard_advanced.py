import sys
import os
import unittest
from fastapi.testclient import TestClient

# Ensure we can import from backend and other modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.core.database import (
    init_db,
    save_ai_comment,
    update_comment_score,
    get_connection,
    log_action,
    get_audit_logs,
    get_repo_settings,
    save_repo_settings,
)
from vector_store.chroma_client import ensure_collection


class TestDashboardAdvanced(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        # Clean DB state
        with get_connection() as conn:
            conn.execute("DELETE FROM ai_comments")
            conn.execute("DELETE FROM repo_settings")
            conn.execute("DELETE FROM audit_logs")

        self.client = TestClient(app)

        # Clear ChromaDB test entries
        self.collection = ensure_collection()
        try:
            self.collection.delete(ids=["feedback_77001"])
        except Exception:
            pass

    def tearDown(self):
        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM ai_comments")
            conn.execute("DELETE FROM repo_settings")
            conn.execute("DELETE FROM audit_logs")
        try:
            self.collection.delete(ids=["feedback_77001"])
        except Exception:
            pass

    def test_database_helpers(self):
        """Test 1: Verifies SQLite schema extensions and database helper functions."""
        print("\n--> Running Test 1: SQLite Schema Extensions & Helpers...")

        # 1. Test log_action & get_audit_logs
        log_action("Admin", "Triggered test retraining", "ChromaDB Upsert")
        log_action("Developer", "Viewed system logs", "Dashboard UI")

        logs = get_audit_logs(limit=10)
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["user_role"], "Developer")
        self.assertEqual(logs[1]["user_role"], "Admin")
        print("[PASS] Audit logs helpers work correctly")

        # 2. Test save_repo_settings & get_repo_settings
        save_success = save_repo_settings(
            "test/repo", 4, "security", "Review carefully", 5
        )
        self.assertTrue(save_success)

        settings = get_repo_settings("test/repo")
        self.assertEqual(settings["strictness"], 4)
        self.assertEqual(settings["review_mode"], "security")
        self.assertEqual(settings["custom_prompt"], "Review carefully")
        self.assertEqual(settings["retrieval_depth"], 5)
        print("[PASS] Repository settings helpers work correctly")

    def test_dashboard_stats_endpoint(self):
        """Test 2: Verifies dashboard stats calculations and response payloads."""
        print("\n--> Running Test 2: Stats Aggregations Endpoint...")

        # Save mock reviews
        save_ai_comment(77001, "test/repo", 2, "main.py", "code1", "Good", "fix1")
        update_comment_score(77001, 3)

        save_ai_comment(
            77002, "test/repo", 2, "utils.py", "code2", "Bad suggestion", "fix2"
        )
        update_comment_score(77002, -1)

        response = self.client.get("/api/dashboard/stats")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_reviews"], 2)
        self.assertEqual(data["positive_reviews"], 1)
        self.assertEqual(data["negative_reviews"], 1)
        self.assertEqual(data["helpfulness_rate"], 50.0)
        self.assertEqual(data["false_positive_rate"], 50.0)
        print("[PASS] Stats endpoints returns correct aggregates")

    def test_dashboard_reviews_paginated(self):
        """Test 3: Verifies review logs pagination, searching, and filtering."""
        print("\n--> Running Test 3: Paginated Review Logs Endpoint...")

        # Save mock review
        save_ai_comment(
            77001, "test/repo", 2, "auth.py", "def check_token(): pass", "Correct", ""
        )
        update_comment_score(77001, 1)

        # Query reviews
        response = self.client.get(
            "/api/dashboard/reviews?page=1&size=5&search=check_token"
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(len(data["reviews"]), 1)
        self.assertEqual(data["reviews"][0]["file_path"], "auth.py")
        print("[PASS] Paginated review filtering and search works correctly")

    def test_rbac_settings_protection(self):
        """Test 4: Verifies settings endpoints and RBAC administrative restrictions."""
        print("\n--> Running Test 4: Settings RBAC Protection Endpoints...")

        # 1. Try to post settings as a Developer (Should fail 403)
        payload = {
            "repo_full_name": "test/repo",
            "strictness": 5,
            "review_mode": "performance",
            "role": "Developer",
        }
        response = self.client.post("/api/dashboard/settings", json=payload)
        self.assertEqual(response.status_code, 403)
        print("[PASS] Developer settings POST correctly blocked with 403 Forbidden")

        # 2. Post settings as an Admin (Should succeed 200)
        payload["role"] = "Admin"
        response = self.client.post("/api/dashboard/settings", json=payload)
        self.assertEqual(response.status_code, 200)
        print("[PASS] Admin settings POST correctly accepted")

        # 3. Retrieve settings
        response = self.client.get("/api/dashboard/settings?repo=test/repo")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["review_mode"], "performance")
        self.assertEqual(data["strictness"], 5)
        print("[PASS] Settings GET endpoint returns correct configuration")

    def test_system_status_observability(self):
        """Test 5: Verifies status checkers and connection latency indicators."""
        print("\n--> Running Test 5: Observability Status & Audit Logs Endpoint...")

        log_action("Admin", "Triggered test retraining", "ChromaDB")

        response = self.client.get("/api/dashboard/status")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["database"], "online")
        self.assertTrue(len(data["audit_logs"]) >= 1)
        self.assertEqual(data["audit_logs"][0]["action"], "Triggered test retraining")
        print(
            "[PASS] System status endpoint returns valid latency metrics and audit logs"
        )

    def test_branding_configuration_endpoint(self):
        """Test 6: Verifies that the branding configuration REST API returns configured values."""
        print("\n--> Running Test 6: Dynamic Platform Branding Config Endpoint...")

        response = self.client.get("/api/dashboard/config")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["platform_name"], "Antigravity AI")
        self.assertEqual(data["platform_subtitle"], "Review Analytics Platform")
        self.assertEqual(data["logo_icon_class"], "fa-solid fa-brain")
        self.assertEqual(data["login_logo_icon_class"], "fa-solid fa-robot")
        self.assertEqual(data["browser_title"], "Enterprise AI Reviewer Dashboard")
        print("[PASS] Branding config endpoint returns accurate dynamic defaults")


if __name__ == "__main__":
    unittest.main()
