import unittest

from src.direct_browser import BrowserPublisherError, CampaignDraft, load_recipes, run_campaign


class DirectBrowserSafetyTests(unittest.TestCase):
    def test_recipes_cover_required_socials(self):
        recipes = load_recipes()
        self.assertEqual(set(recipes), {"meta", "tiktok", "linkedin"})
        for platform, recipe in recipes.items():
            self.assertTrue(recipe["composer_url"].startswith("https://"), platform)
            self.assertTrue(recipe["final_labels"], platform)

    def test_live_requires_explicit_allow(self):
        draft = CampaignDraft(platform="linkedin", caption="test")
        with self.assertRaisesRegex(BrowserPublisherError, "explicit allow_live"):
            run_campaign(draft, "dummy-context", mode="live", allow_live=False)

    def test_invalid_mode_fails_before_network(self):
        draft = CampaignDraft(platform="meta", caption="test")
        with self.assertRaisesRegex(BrowserPublisherError, "mode must be"):
            run_campaign(draft, "dummy-context", mode="publish-now", allow_live=False)


if __name__ == "__main__":
    unittest.main()
