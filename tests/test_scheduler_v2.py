import unittest

from src.scheduler_v2 import SocialScheduler


class FakeClient:
    pass


class FakeRuntimeClient:
    def runtime_snapshot(self, organization_id):
        return {
            "account": {"organizations": [{"id": organization_id, "name": "Org"}]},
            "channels": [{"id": "fb", "name": "FB", "service": "facebook"}],
            "posts": [
                {
                    "id": f"p-{i}",
                    "status": "scheduled",
                    "channelId": "fb",
                    "text": f"existing {i}",
                    "dueAt": "2099-01-01T09:00:00+02:00",
                }
                for i in range(9)
            ],
            "has_next_page": False,
        }


SETTINGS = {
    "organization_id": "org",
    "timezone": "Europe/Athens",
    "queue_limit": 10,
    "queue_limit_per_channel": 10,
    "idea_limit": 100,
    "max_creates_per_run": 30,
    "late_item_policy": "defer",
    "late_item_defer_days": 3,
    "content_source": "socialmarket_outbox",
}
CHANNELS = {"facebook": {"id": "fb"}}


def backlog_item(item_id="x", target_at="2099-01-01T10:00:00+02:00", text="Same execution"):
    return [{"id": item_id,"brand": "Brand","topic": "Topic","target_at": target_at,"services": ["facebook"],"platform_text": {"facebook": text},"format": {"facebook": "post"}}]


class SchedulerV2Tests(unittest.TestCase):
    def test_existing_error_is_not_blindly_retried(self):
        scheduler = SocialScheduler(FakeClient(), SETTINGS, CHANNELS, backlog_item(), mode="dry-run")
        posts = [{"id": "post-error","status": "error","channelId": "fb","text": "Same execution","ideaId": None}]
        scheduler.reconcile_and_fill(scheduler.expand(), posts)
        self.assertTrue(any(a["type"] == "existing_error_blocked" for a in scheduler.actions))
        self.assertTrue(any(a["type"] == "already_error" and a["campaign"] == "x" for a in scheduler.actions))
        self.assertFalse(any(a["type"] == "would_schedule" for a in scheduler.actions))

    def test_existing_buffer_schedule_is_reconciled_not_duplicated(self):
        scheduler = SocialScheduler(FakeClient(), SETTINGS, CHANNELS, backlog_item("migrated"), mode="dry-run")
        posts = [{"id": "buffer-existing","status": "scheduled","channelId": "fb","text": "Same execution","dueAt": "2099-01-01T10:00:00+02:00","sentAt": None,"ideaId": None}]
        scheduler.reconcile_and_fill(scheduler.expand(), posts)
        self.assertTrue(any(a["type"] == "already_scheduled" and a["campaign"] == "migrated" for a in scheduler.actions))
        self.assertFalse(any(a["type"] == "would_schedule" for a in scheduler.actions))

    def test_expired_socialmarket_time_is_never_deferred_by_executor(self):
        scheduler = SocialScheduler(FakeClient(), SETTINGS, CHANNELS, backlog_item("expired", "2020-01-01T10:00:00+02:00", "Expired execution"), mode="dry-run")
        scheduler.reconcile_and_fill(scheduler.expand(), [])
        self.assertTrue(any(a["type"] == "skip_late" and a["campaign"] == "expired" for a in scheduler.actions))
        self.assertFalse(any(a["type"] == "would_schedule" for a in scheduler.actions))

    def test_run_reports_post_write_full_truth(self):
        scheduler = SocialScheduler(FakeRuntimeClient(), SETTINGS, CHANNELS, backlog_item("fill-slot", text="new unique post"), mode="dry-run")
        result = scheduler.run()
        self.assertEqual(result["initial_active_by_service"]["facebook"], 9)
        self.assertEqual(result["scheduled_by_service"]["facebook"], 1)
        self.assertEqual(result["active_by_service"]["facebook"], 10)
        self.assertTrue(result["channel_queue_slo"]["facebook"]["met"])
        self.assertTrue(result["queue_slo"]["met"])
        self.assertEqual(result["full_truth_source"], "single_runtime_snapshot_plus_buffer_create_ack")


if __name__ == "__main__":
    unittest.main()
