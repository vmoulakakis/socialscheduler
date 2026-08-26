import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from src.scheduler import Execution, SocialScheduler, normalize_text, text_hash


class FakeClient:
    pass


SETTINGS = {
    "organization_id": "org",
    "timezone": "Europe/Athens",
    "queue_limit": 10,
    "idea_limit": 100,
    "max_creates_per_run": 10,
    "late_item_policy": "defer",
    "late_item_defer_days": 3,
}
CHANNELS = {
    "facebook": {"id": "fb"},
    "instagram": {"id": "ig"},
    "tiktok": {"id": "tt"},
}


class SchedulerTests(unittest.TestCase):
    def test_normalization_stable(self):
        self.assertEqual(normalize_text("  Hello   WORLD "), "hello world")
        self.assertEqual(text_hash("Hello world"), text_hash(" hello   WORLD "))

    def test_forbids_duplicate_sent_caption_same_channel(self):
        backlog = [{
            "id": "x", "brand": "B", "topic": "T", "target_at": "2099-01-01T10:00:00+02:00",
            "services": ["facebook"], "platform_text": {"facebook": "Same caption"},
            "format": {"facebook": "post"}
        }]
        s = SocialScheduler(FakeClient(), SETTINGS, CHANNELS, backlog, mode="dry-run")
        ex = s.expand()
        posts = [{"status": "sent", "channelId": "fb", "text": " same  caption "}]
        s.reconcile_and_fill(ex, posts)
        self.assertFalse(any(a["type"] == "would_schedule" for a in s.actions))

    def test_hold_service_not_scheduled(self):
        backlog = [{
            "id": "x", "brand": "B", "topic": "T", "target_at": "2099-01-01T10:00:00+02:00",
            "services": ["facebook"], "platform_text": {"facebook": "Caption"},
            "format": {"facebook": "post"}, "hold_services": {"facebook": True}
        }]
        s = SocialScheduler(FakeClient(), SETTINGS, CHANNELS, backlog, mode="dry-run")
        s.reconcile_and_fill(s.expand(), [])
        self.assertTrue(any(a["type"] == "hold" for a in s.actions))
        self.assertFalse(any(a["type"] == "would_schedule" for a in s.actions))

    def test_post_input_uses_custom_scheduled(self):
        s = SocialScheduler(FakeClient(), SETTINGS, CHANNELS, [], mode="dry-run")
        ex = Execution("id", "B", "T", "facebook", "fb", datetime(2099,1,1,10,0,tzinfo=ZoneInfo("Europe/Athens")), "Text", None, None, "post", "Idea")
        inp = s._post_input(ex, ex.target_at)
        self.assertEqual(inp["mode"], "customScheduled")
        self.assertNotIn(inp["mode"], {"shareNow", "shareNext"})

    def test_fair_order_round_robins_brands_without_mutating_input(self):
        s = SocialScheduler(FakeClient(), SETTINGS, CHANNELS, [], mode="dry-run")
        executions = [
            Execution("a1", "A", "T", "facebook", "fb", datetime(2099,1,1,9,0,tzinfo=ZoneInfo("Europe/Athens")), "a1", None, None, "post", "a1"),
            Execution("a2", "A", "T", "facebook", "fb", datetime(2099,1,1,10,0,tzinfo=ZoneInfo("Europe/Athens")), "a2", None, None, "post", "a2"),
            Execution("b1", "B", "T", "facebook", "fb", datetime(2099,1,1,9,30,tzinfo=ZoneInfo("Europe/Athens")), "b1", None, None, "post", "b1"),
        ]
        original = list(executions)

        ordered = s._fair_order(executions)

        self.assertEqual([item.campaign_id for item in ordered], ["a1", "b1", "a2"])
        self.assertEqual(executions, original)


if __name__ == "__main__":
    unittest.main()
