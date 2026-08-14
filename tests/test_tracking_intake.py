import unittest

from scripts.tracking_content_factory import platform_copy, slugify
from scripts.tracking_intake import parse_form, parse_platforms, parse_target, require_https


class TrackingIntakeTests(unittest.TestCase):
    def test_tracking_url_is_preserved_exactly(self):
        url = "https://example.com/click?token=abc123%2Fxyz&sig=A-B_C"
        self.assertEqual(require_https(url), url)

    def test_target_uses_real_athens_dst_offset(self):
        self.assertTrue(parse_target("2026-09-20 19:00").endswith("+03:00"))
        self.assertTrue(parse_target("2026-11-01 19:00").endswith("+02:00"))

    def test_platforms_are_validated_and_deduped(self):
        self.assertEqual(parse_platforms("instagram,facebook,instagram"), ["instagram", "facebook"])
        with self.assertRaises(ValueError):
            parse_platforms("instagram,linkedin")

    def test_issue_form_parser(self):
        body = "### Tracking URL\n\nhttps://example.com/x\n\n### Brand\n\nCoffeeGo AI\n"
        parsed = parse_form(body)
        self.assertEqual(parsed["Tracking URL"], "https://example.com/x")
        self.assertEqual(parsed["Brand"], "CoffeeGo AI")

    def test_platform_copy_is_platform_specific_and_keeps_url(self):
        url = "https://example.com/opaque?sig=123"
        copies = platform_copy("Brand", "Useful angle", "Landing page", url)
        self.assertEqual(set(copies), {"instagram", "facebook", "tiktok"})
        self.assertEqual(len(set(copies.values())), 3)
        self.assertTrue(all(url in text for text in copies.values()))

    def test_slug_is_deterministic(self):
        self.assertEqual(slugify("CoffeeGo AI / Summer"), "coffeego-ai-summer")


if __name__ == "__main__":
    unittest.main()
