import os
import unittest
from unittest.mock import patch

from src.postiz_client import PostizAPIError, PostizClient, _iso_utc, _post_type, _render_content


class PostizClientTests(unittest.TestCase):
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
        self.assertEqual(_iso_utc("2026-08-17T12:00:00+03:00"), "2026-08-17T09:00:00.000Z")

    def test_instagram_format_mapping(self):
        self.assertEqual(_post_type("reel"), "reel")
        self.assertEqual(_post_type("video"), "reel")
        self.assertEqual(_post_type("story"), "story")
        self.assertEqual(_post_type("post"), "post")

    def test_auto_discovery_requires_explicit_id_when_multiple(self):
        client = PostizClient(api_url="https://example.test/public/v1", api_key="x")
        client.integrations = lambda: [
            {"id": "fb-1", "identifier": "facebook", "disabled": False},
            {"id": "fb-2", "identifier": "facebook", "disabled": False},
        ]
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("POSTIZ_INTEGRATION_FACEBOOK", None)
            with self.assertRaises(PostizAPIError):
                client.resolve_integrations()

    def test_explicit_integration_wins(self):
        client = PostizClient(api_url="https://example.test/public/v1", api_key="x")
        client.integrations = lambda: []
        with patch.dict(os.environ, {"POSTIZ_INTEGRATION_FACEBOOK": "fb-explicit"}, clear=False):
            resolved = client.resolve_integrations()
        self.assertEqual(resolved["facebook"], "fb-explicit")


if __name__ == "__main__":
    unittest.main()
