"""API-szerződés tesztjei leválasztott adatbázissal (nem Swarm-bizonyíték).

Futtatás a projekt gyökeréből:
  python -m pip install -r backend/requirements-test.txt
  python -m unittest discover -s tests -v

A valódi PostgreSQL/Swarm teszteket a scripts/ könyvtár és a dokumentáció írja le.
"""

import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from backend.main import app, get_repository
from backend.repository import DatabaseUnavailable, MissionRepository


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.key = "unit-test-only-" + "a" * 48
        key_path = Path(self.temp.name) / "admin_token"
        key_path.write_text(self.key, encoding="utf-8")
        self.environment = patch.dict(os.environ, {"ADMIN_TOKEN_FILE": str(key_path)})
        self.environment.start()
        self.repository = Mock(spec=MissionRepository)
        self.repository.health.return_value = None
        self.repository.list.return_value = {"items": [], "count": 0}
        app.dependency_overrides[get_repository] = lambda: self.repository
        self.client = TestClient(app, raise_server_exceptions=False)
        self.headers = {"X-Admin-Token": self.key}
        self.payload = {
            "title": "Új tesztfeladat",
            "location": "Fiktív tesztmező",
            "aircraft": "DemoQuad 01",
            "mission_date": "2026-11-20",
            "flight_minutes": 12,
            "status": "planned",
            "notes": "Kitalált adat.",
        }

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.environment.stop()
        self.temp.cleanup()

    def stored_mission(self, **changes):
        return {
            **self.payload,
            "id": 1,
            "mission_date": date(2026, 11, 20),
            "created_at": datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc),
            **changes,
        }

    def test_reads_are_public_and_include_instance_header(self):
        response = self.client.get("/api/missions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": [], "count": 0})
        self.assertTrue(response.headers["X-Instance-ID"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_all_mutations_require_valid_key_before_repository_call(self):
        for method, url, payload in [
            ("POST", "/api/missions", self.payload),
            ("PATCH", "/api/missions/1", {"status": "completed"}),
            ("DELETE", "/api/missions/1", None),
        ]:
            for headers in ({}, {"X-Admin-Token": "incorrect"}):
                with self.subTest(method=method, missing=not headers):
                    response = self.client.request(method, url, json=payload, headers=headers)
                    self.assertEqual(response.status_code, 401)
        self.repository.create.assert_not_called()
        self.repository.update.assert_not_called()
        self.repository.delete.assert_not_called()

    def test_create_returns_record_and_accepts_hungarian_text(self):
        self.repository.create.return_value = self.stored_mission()
        response = self.client.post("/api/missions", json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["title"], self.payload["title"])
        self.assertEqual(response.json()["mission_date"], "2026-11-20")
        self.assertEqual(self.repository.create.call_args.args[0]["mission_date"], date(2026, 11, 20))

    def test_admin_check_verifies_key_without_database_write(self):
        self.assertEqual(self.client.get("/api/admin/check").status_code, 401)
        self.assertEqual(self.client.get("/api/admin/check", headers={"X-Admin-Token": "wrong"}).status_code, 401)
        response = self.client.get("/api/admin/check", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"authorized": True})
        self.repository.create.assert_not_called()
        self.repository.update.assert_not_called()
        self.repository.delete.assert_not_called()

    def test_invalid_create_inputs_cannot_reach_repository(self):
        cases = [
            {"title": "   "}, {"title": "x" * 121}, {"location": " "},
            {"aircraft": "x"}, {"flight_minutes": -1}, {"flight_minutes": 601},
            {"flight_minutes": True}, {"flight_minutes": 3.5}, {"flight_minutes": "12"},
            {"mission_date": "invalid"}, {"mission_date": "1999-12-31"},
            {"status": "unknown"}, {"notes": "x" * 2001}, {"unexpected": "field"},
        ]
        for changes in cases:
            with self.subTest(changes=repr(changes)[:100]):
                response = self.client.post("/api/missions", json={**self.payload, **changes}, headers=self.headers)
                self.assertEqual(response.status_code, 422, response.text)
        self.repository.create.assert_not_called()

    def test_patch_accepts_partial_valid_change(self):
        self.repository.update.return_value = self.stored_mission(status="completed")
        response = self.client.patch("/api/missions/1", json={"status": "completed"}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "completed")
        self.repository.update.assert_called_once_with(1, {"status": "completed"})

    def test_patch_rejects_empty_null_and_out_of_range_date(self):
        for payload in ({}, {"title": None}, {"id": 7}, {"mission_date": "2101-01-01"}):
            with self.subTest(payload=payload):
                response = self.client.patch("/api/missions/1", json=payload, headers=self.headers)
                self.assertEqual(response.status_code, 422, response.text)
        self.repository.update.assert_not_called()

    def test_update_unknown_id_returns_404(self):
        self.repository.update.return_value = None
        response = self.client.patch("/api/missions/999", json={"status": "active"}, headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_delete_success_has_no_body(self):
        self.repository.delete.return_value = True
        response = self.client.delete("/api/missions/1", headers=self.headers)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")

    def test_delete_unknown_id_returns_404(self):
        self.repository.delete.return_value = False
        self.assertEqual(self.client.delete("/api/missions/999", headers=self.headers).status_code, 404)

    def test_pagination_rejects_unbounded_requests(self):
        for query in ("limit=501", "limit=0", "offset=-1"):
            self.assertEqual(self.client.get("/api/missions?" + query).status_code, 422)
        self.repository.list.assert_not_called()

    def test_pagination_parameters_are_forwarded(self):
        self.assertEqual(self.client.get("/api/missions?limit=25&offset=50").status_code, 200)
        self.repository.list.assert_called_once_with(25, 50)

    def test_health_is_based_on_database_readiness(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "ok")
        self.repository.health.side_effect = DatabaseUnavailable("private connection detail")
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["database"], "unavailable")
        self.assertNotIn("private connection detail", response.text)

    def test_database_errors_are_generic_and_retryable(self):
        self.repository.list.side_effect = DatabaseUnavailable("private password")
        response = self.client.get("/api/missions")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Retry-After"], "5")
        self.assertNotIn("private password", response.text)

    def test_missing_or_short_admin_secret_fails_closed(self):
        for path, content in (("missing", None), ("short", "tiny")):
            file_path = Path(self.temp.name) / path
            if content is not None:
                file_path.write_text(content, encoding="utf-8")
            with patch.dict(os.environ, {"ADMIN_TOKEN_FILE": str(file_path)}):
                response = self.client.post("/api/missions", json=self.payload, headers=self.headers)
                self.assertEqual(response.status_code, 503)
        self.repository.create.assert_not_called()

    def test_stats_contract(self):
        stats = {"total": 3, "planned": 1, "active": 1, "completed": 1, "flight_minutes": 24}
        self.repository.stats.return_value = stats
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), stats)

    def test_instance_is_not_a_claim_about_total_replicas(self):
        response = self.client.get("/api/instance")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"instance", "version"})
        self.assertNotIn(self.key, response.text)


if __name__ == "__main__":
    unittest.main()
