import os
import unittest
from unittest.mock import patch

from src.brightbean_client import BrightBeanAPIError, BrightBeanClient, _compose_caption


class FakeBrightBeanClient(BrightBeanClient):
    def __init__(self):
        super().__init__(api_url="https://studio.example/api/v1", api_key="token")
        self.accounts = []
        self.calls = []

    def list_accounts(self):
        return list(self.accounts)

    def _request(self, method, path, **kwargs):
        self.calls.append({"method": method, "path": path, **kwargs})
        return {"id": "post-1"}

    def upload_media_url(self, media_url, *, job_id):
        self.calls.append({"method": "UPLOAD", "url": media_url, "job_id": job_id})
        return "media-1"


class BrightBeanClientTests(unittest.TestCase):
    def test_compose_caption_preserves_tracking_and_hashtags_once(self):
        job = {
            "caption": "Useful product #deal",
            "hashtags": ["#deal", "#greece"],
            "tracking_url": "https://example.test/track",
        }
        rendered = _compose_caption(job)
        self.assertEqual(rendered.count("#deal"), 1)
        self.assertIn("#greece", rendered)
        self.assertEqual(rendered.count("https://example.test/track"), 1)

    def test_resolve_single_linkedin_personal_account(self):
        client = FakeBrightBeanClient()
        client.accounts = [{
            "id": "li-1",
            "platform": "linkedin_personal",
            "account_name": "Vassilis",
            "connection_status": "connected",
        }]
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BRIGHTBEAN_ACCOUNT_LINKEDIN", None)
            account = client.resolve_account("linkedin")
        self.assertEqual(account["id"], "li-1")

    def test_resolve_linkedin_requires_mapping_when_ambiguous(self):
        client = FakeBrightBeanClient()
        client.accounts = [
            {"id": "li-1", "platform": "linkedin_personal", "connection_status": "connected"},
            {"id": "li-2", "platform": "linkedin_company", "connection_status": "connected"},
        ]
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BRIGHTBEAN_ACCOUNT_LINKEDIN", None)
            with self.assertRaises(BrightBeanAPIError):
                client.resolve_account("linkedin")

    def test_schedule_job_targets_account_and_uses_idempotency(self):
        client = FakeBrightBeanClient()
        account = {
            "id": "li-1",
            "platform": "linkedin_personal",
            "char_limit": 3000,
            "escaped_chars": "",
            "needs_title": False,
        }
        result = client.schedule_job({
            "id": "job-1",
            "caption": "Approved copy",
            "hashtags": ["#AI"],
            "tracking_url": "https://example.test/t",
            "media_url": "https://example.test/image.png",
            "scheduled_for": "2026-08-19T10:00:00Z",
        }, account)
        self.assertEqual(result["id"], "post-1")
        post_call = self.calls_post(client)
        payload = post_call["payload"]
        self.assertEqual(payload["social_account_id"], "li-1")
        self.assertEqual(payload["action"], "schedule")
        self.assertEqual(payload["media_asset_ids"], ["media-1"])
        self.assertIn("#AI", payload["caption"])
        self.assertIn("https://example.test/t", payload["caption"])
        self.assertTrue(payload["idempotency_key"].startswith("socialscheduler-job-1-"))

    def test_get_post_is_read_only_and_url_safe(self):
        client = FakeBrightBeanClient()
        client.get_post("post id")
        self.assertEqual(client.calls[-1]["method"], "GET")
        self.assertEqual(client.calls[-1]["path"], "posts/post%20id")

    @staticmethod
    def calls_post(client):
        return next(call for call in client.calls if call.get("method") == "POST" and call.get("path") == "posts/")


if __name__ == "__main__":
    unittest.main()
