import io
import os
import unittest
from unittest.mock import patch

from PIL import Image

from src.openpost_client import OpenPostAPIError
from src.openpost_native import OpenPostClient, SERVICES, _native_profile


class FakeNormalizationClient(OpenPostClient):
    def __init__(self, png_bytes):
        super().__init__(
            api_url="https://openpost.example/api/v1",
            api_token="token",
            workspace_id="workspace-1",
            media_ready_timeout_seconds=0,
        )
        self.png_bytes = png_bytes
        self.uploaded = None

    def _download_media(self, media_url):
        return self.png_bytes, "creative.png", "image/png", "unused"

    def _upload_bytes(self, content, filename, mime_type):
        self.uploaded = (content, filename, mime_type)
        return "media-webp"


class OpenPostNativeFormatTests(unittest.TestCase):
    def test_services_include_linkedin(self):
        self.assertEqual(SERVICES, ("facebook", "instagram", "tiktok", "linkedin"))

    def test_instagram_feed_reel_story_profiles(self):
        self.assertEqual(_native_profile("instagram", "post"), "post")
        self.assertEqual(_native_profile("instagram", "feed"), "post")
        # Reel execution remains supported for a real approved video job.
        self.assertEqual(_native_profile("instagram", "reel"), "short_video")
        self.assertEqual(_native_profile("instagram", "story"), "story")

    def test_linkedin_feed_and_video_profiles(self):
        self.assertEqual(_native_profile("linkedin", "post"), "post")
        self.assertEqual(_native_profile("linkedin", "video"), "short_video")

    def test_tiktok_feed_and_photo_are_supported_but_story_fails_closed(self):
        self.assertEqual(_native_profile("tiktok", "post"), "post")
        self.assertEqual(_native_profile("tiktok", "photo"), "post")
        self.assertEqual(_native_profile("tiktok", "video"), "short_video")
        with self.assertRaises(OpenPostAPIError):
            _native_profile("tiktok", "story")

    def test_tiktok_png_is_losslessly_normalized_to_webp_before_openpost(self):
        source = io.BytesIO()
        Image.new("RGBA", (8, 8), (20, 40, 60, 128)).save(source, format="PNG")
        client = FakeNormalizationClient(source.getvalue())
        media_id = client.upload_tiktok_photo_from_url("https://example.test/creative.png")
        self.assertEqual(media_id, "media-webp")
        content, filename, mime_type = client.uploaded
        self.assertEqual(filename, "creative.webp")
        self.assertEqual(mime_type, "image/webp")
        with Image.open(io.BytesIO(content)) as converted:
            self.assertEqual(converted.format, "WEBP")
            self.assertEqual(converted.size, (8, 8))

    def test_linkedin_account_mapping_is_explicit(self):
        with patch.dict(os.environ, {
            "OPENPOST_ACCOUNT_FACEBOOK": "fb",
            "OPENPOST_ACCOUNT_INSTAGRAM": "ig",
            "OPENPOST_ACCOUNT_TIKTOK": "tt",
            "OPENPOST_ACCOUNT_LINKEDIN": "li",
        }, clear=False):
            accounts = OpenPostClient.account_ids_from_env()
        self.assertEqual(accounts["linkedin"], "li")
        self.assertEqual(set(accounts), {"facebook", "instagram", "tiktok", "linkedin"})


if __name__ == "__main__":
    unittest.main()
