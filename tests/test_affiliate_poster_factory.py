import unittest

from scripts.affiliate_poster_factory import SIZES, platform_caption


class AffiliatePosterFactoryTests(unittest.TestCase):
    def test_platform_copy_is_unique_and_disclosed(self):
        url = "https://example.supabase.co/functions/v1/socialscheduler-go/item?p=x&c=y"
        captions = {p: platform_caption(p, "Product", "Merchant", url) for p in SIZES}
        self.assertEqual(len(set(captions.values())), 4)
        for caption in captions.values():
            self.assertIn("affiliate link", caption)

    def test_platform_dimensions_match_delivery_format(self):
        self.assertEqual(SIZES["instagram"], (1080, 1350))
        self.assertEqual(SIZES["tiktok"], (1080, 1920))
        self.assertEqual(SIZES["linkedin"], (1200, 1500))


if __name__ == "__main__":
    unittest.main()

