import os
import unittest
from unittest.mock import patch

from src.openpost_client import OpenPostAPIError
from src.openpost_native import OpenPostClient, SERVICES, _native_profile


class OpenPostNativeFormatTests(unittest.TestCase):
    def test_services_include_linkedin(self):
        self.assertEqual(SERVICES, ("facebook", "instagram", "tiktok", "linkedin"))

    def test_instagram_feed_reel_story_profiles(self):
        self.assertEqual(_native_profile("instagram", "post"), "post")
        self.assertEqual(_native_profile("instagram", "feed"), "post")
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
