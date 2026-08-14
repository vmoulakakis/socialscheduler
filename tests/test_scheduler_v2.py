import unittest

from src.scheduler_v2 import SocialScheduler


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
CHANNELS = {"facebook": {"id": "fb"}}


class SchedulerV2Tests(unittest.TestCase):
    def test_existing_error_is_not_blindly_retried(self):
        backlog = [{
            "id": "x",
            "brand": "Brand",
            "topic": "Topic",
            "target_at": "2099-01-01T10:00:00+02:00",
            "services": ["facebook"],
            "platform_text": {"facebook": "Same execution"},
            "format": {"facebook": "post"},
        }]
        scheduler = SocialScheduler(FakeClient(), SETTINGS, CHANNELS, backlog, mode="dry-run")
        posts = [{
            "id": "post-error",
            "status": "error",
            "channelId": "fb",
            "text": "Same execution",
            "ideaId": None,
        }]
        scheduler.reconcile_and_fill(scheduler.expand(), posts)
        self.assertTrue(any(a["type"] == "existing_error_blocked" for a in scheduler.actions))
        self.assertFalse(any(a["type"] == "would_schedule" for a in scheduler.actions))


if __name__ == "__main__":
    unittest.main()
