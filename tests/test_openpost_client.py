import os
import unittest
from unittest.mock import patch

from src.openpost_client import OpenPostAPIError, OpenPostClient, _content_profile, _iso_utc, _render_content


class FakeOpenPostClient(OpenPostClient):
    def __init__(self):
        super().__init__(
            api_url="https://openpost.example/api/v1",
            api_token="token",
            workspace_id="workspace-1",
            media_ready_timeout_seconds=0,
        )
        self.calls = []
        self.existing = []

    def _request_json(self, method, path_or_url, payload=None, *, query=None, write=False):
        self.calls.append({
            "method": method,
            "path": path_or_url,
            "payload": payload,
            "query": query,
            "write": write,
        })
        if method == "GET" and path_or_url == "/publications":
            return list(self.existing)
        if method == "POST" and path_or_url == "/publications":
            return {
                "id": "publication-1",
                "revision": 1,
                "status": "draft",
                "scheduled_at": payload["scheduled_at"],
                "metadata": payload["metadata"],
                "renditions": [],
            }
        if method == "POST" and path_or_url == "/publications/publication-1/schedule":
            return {"message": "publication scheduled", "publication_id": "publication-1", "job_id": "job-1", "revision": 2}
        if method == "GET" and path_or_url == "/publications/publication-1":
            return {
                "id": "publication-1",
                "revision": 2,
                "status": "scheduled",
                "scheduled_at": "2026-08-18T09:00:00.000Z",
                "renditions": [],
            }
        raise AssertionError(f"Unexpected request: {method} {path_or_url}")


class OpenPostClientTests(unittest.TestCase):
    def test_render_content_preserves_tracking_and_hashtags_once(self):
        job = {
            "caption": "Useful product #deal",
            "hashtags": ["#deal", "#greece"],
            "tracking_url": "https://example.test/track",
        }
        rendered = _render_content(job)
        self.assertEqual(rendered.count("#deal"), 1)
        self.assertIn("#greece", rendered)
        self.assertEqual(rendered.count("https://example.test/track"), 1)

    def test_iso_utc_normalizes_offset(self):
        self.assertEqual(_iso_utc("2026-08-18T12:00:00+03:00"), "2026-08-18T09:00:00.000Z")

    def test_content_profile_mapping(self):
        self.assertEqual(_content_profile("instagram", "story"), "story")
        self.assertEqual(_content_profile("instagram", "reel"), "short_video")
        self.assertEqual(_content_profile("tiktok", "post"), "short_video")
        self.assertEqual(_content_profile("facebook", "post"), "post")

    def test_account_ids_are_explicit_and_provider_neutral(self):
        with patch.dict(os.environ, {
            "OPENPOST_ACCOUNT_FACEBOOK": "fb-1",
            "OPENPOST_ACCOUNT_INSTAGRAM": "ig-1",
            "OPENPOST_ACCOUNT_TIKTOK": "tt-1",
        }, clear=False):
            accounts = OpenPostClient.account_ids_from_env()
        self.assertEqual(accounts, {"facebook": "fb-1", "instagram": "ig-1", "tiktok": "tt-1"})

    def test_schedule_job_uses_native_publication_then_schedule_action(self):
        client = FakeOpenPostClient()
        job = {
            "id": "sm-job-1",
            "platform": "facebook",
            "title": "Approved item",
            "caption": "Approved caption",
            "hashtags": ["#approved"],
            "tracking_url": "https://example.test/t",
            "scheduled_for": "2026-08-18T12:00:00+03:00",
            "format": "post",
        }
        result = client.schedule_job(job, "fb-account")
        self.assertEqual(result["publicationId"], "publication-1")
        self.assertEqual(result["status"], "scheduled")
        creates = [call for call in client.calls if call["method"] == "POST" and call["path"] == "/publications"]
        self.assertEqual(len(creates), 1)
        payload = creates[0]["payload"]
        self.assertEqual(payload["workspace_id"], "workspace-1")
        self.assertEqual(payload["social_account_ids"], ["fb-account"])
        self.assertEqual(payload["random_delay_minutes"], 0)
        self.assertEqual(payload["metadata"]["socialmarket_job_id"], "sm-job-1")
        self.assertEqual(payload["scheduled_at"], "2026-08-18T09:00:00.000Z")
        schedules = [call for call in client.calls if call["path"].endswith("/schedule")]
        self.assertEqual(len(schedules), 1)
        self.assertEqual(schedules[0]["payload"]["expected_revision"], 1)
        self.assertEqual(schedules[0]["payload"]["execution_intent"], "production")

    def test_existing_scheduled_publication_is_reconciled_without_write(self):
        client = FakeOpenPostClient()
        client.existing = [{
            "id": "publication-existing",
            "revision": 2,
            "status": "scheduled",
            "scheduled_at": "2026-08-18T09:00:00Z",
            "metadata": {"socialmarket_job_id": "sm-job-2", "platform": "facebook"},
            "renditions": [],
        }]
        result = client.schedule_job({"id": "sm-job-2", "platform": "facebook", "scheduled_for": "2026-08-18T09:00:00Z"}, "fb-account")
        self.assertTrue(result["reconciled"])
        writes = [call for call in client.calls if call["write"]]
        self.assertEqual(writes, [])

    def test_duplicate_existing_publications_fail_closed(self):
        client = FakeOpenPostClient()
        duplicate = {
            "id": "p",
            "revision": 1,
            "status": "scheduled",
            "metadata": {"socialmarket_job_id": "sm-job-3", "platform": "facebook"},
            "renditions": [],
        }
        client.existing = [dict(duplicate, id="p1"), dict(duplicate, id="p2")]
        with self.assertRaises(OpenPostAPIError):
            client.find_job_publication("sm-job-3", "facebook")


if __name__ == "__main__":
    unittest.main()
