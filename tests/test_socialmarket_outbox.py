import unittest
from unittest.mock import Mock

from src.socialmarket_outbox import SocialMarketOutboxClient, jobs_to_backlog


class SocialMarketOutboxTests(unittest.TestCase):
    def test_jobs_to_backlog_preserves_platform_copy_and_schedule(self):
        jobs = [{
            "id": "job-1",
            "platform": "instagram",
            "caption": "Approved by SocialMarket",
            "hashtags": ["#GreekAI", "#Travel"],
            "format": "post",
            "media_url": "https://example.com/asset.png",
            "tracking_url": "https://example.com/x",
            "scheduled_for": "2026-08-20T19:00:00+03:00",
            "brand_name": "Travel AI / GreekVibes",
            "title": "Late summer escape",
        }]
        backlog = jobs_to_backlog(jobs)
        self.assertEqual(len(backlog), 1)
        self.assertEqual(backlog[0]["id"], "job-1")
        self.assertEqual(backlog[0]["services"], ["instagram"])
        self.assertEqual(backlog[0]["target_at"], "2026-08-20T19:00:00+03:00")
        self.assertIn("Approved by SocialMarket", backlog[0]["platform_text"]["instagram"])
        self.assertIn("#GreekAI", backlog[0]["platform_text"]["instagram"])
        self.assertEqual(backlog[0]["media_url"], "https://example.com/asset.png")

    def test_jobs_without_explicit_schedule_are_not_executed(self):
        jobs = [{"id": "job-2", "platform": "facebook", "caption": "No date", "scheduled_for": None}]
        self.assertEqual(jobs_to_backlog(jobs), [])

    def test_scheduled_action_is_acked_with_buffer_id(self):
        client = SocialMarketOutboxClient(endpoint="https://example.test", token_provider=lambda: "token")
        client.ack = Mock(return_value={"ok": True})
        counts = client.sync_scheduler_actions([{
            "type": "scheduled",
            "campaign": "job-3",
            "service": "facebook",
            "postId": "buffer-99",
            "dueAt": "2026-08-21T18:00:00+03:00",
        }])
        self.assertEqual(counts["scheduled"], 1)
        client.ack.assert_called_once_with(
            "job-3",
            "scheduled",
            external_post_id="buffer-99",
            scheduled_at="2026-08-21T18:00:00+03:00",
            metadata={"platform": "facebook", "reconciled_existing": False},
        )

    def test_existing_buffer_schedule_closes_migration_lease(self):
        client = SocialMarketOutboxClient(endpoint="https://example.test", token_provider=lambda: "token")
        client.ack = Mock(return_value={"ok": True})
        counts = client.sync_scheduler_actions([{
            "type": "already_scheduled",
            "campaign": "job-migrated",
            "service": "instagram",
            "postId": "buffer-existing",
            "dueAt": "2026-08-20T19:00:00+03:00",
        }])
        self.assertEqual(counts["scheduled"], 1)
        client.ack.assert_called_once_with(
            "job-migrated",
            "scheduled",
            external_post_id="buffer-existing",
            scheduled_at="2026-08-20T19:00:00+03:00",
            metadata={"platform": "instagram", "reconciled_existing": True},
        )

    def test_existing_sent_post_is_not_republished(self):
        client = SocialMarketOutboxClient(endpoint="https://example.test", token_provider=lambda: "token")
        client.ack = Mock(return_value={"ok": True})
        counts = client.sync_scheduler_actions([{
            "type": "already_published",
            "campaign": "job-sent",
            "service": "facebook",
            "postId": "buffer-sent",
            "sentAt": "2026-08-14T18:00:00Z",
        }])
        self.assertEqual(counts["published"], 1)
        client.ack.assert_called_once_with(
            "job-sent",
            "published",
            external_post_id="buffer-sent",
            published_at="2026-08-14T18:00:00Z",
            metadata={"platform": "facebook", "reconciled_existing": True},
        )

    def test_expired_job_is_failed_not_rescheduled(self):
        client = SocialMarketOutboxClient(endpoint="https://example.test", token_provider=lambda: "token")
        client.ack = Mock(return_value={"ok": True})
        counts = client.sync_scheduler_actions([{
            "type": "skip_late",
            "campaign": "job-expired",
            "service": "tiktok",
        }])
        self.assertEqual(counts["failed"], 1)
        client.ack.assert_called_once_with(
            "job-expired",
            "failed",
            external_post_id=None,
            error="scheduled_time_elapsed",
            metadata={"platform": "tiktok"},
        )

    def test_buffer_sent_marks_socialmarket_job_published(self):
        client = SocialMarketOutboxClient(endpoint="https://example.test", token_provider=lambda: "token")
        client.ack = Mock(return_value={"ok": True})
        counts = client.sync_buffer_statuses(
            [{"id": "job-4", "external_post_id": "buffer-1", "status": "scheduled", "platform": "tiktok"}],
            [{"id": "buffer-1", "status": "sent", "sentAt": "2026-08-22T18:30:00Z", "dueAt": "2026-08-22T18:30:00Z"}],
        )
        self.assertEqual(counts["published"], 1)
        client.ack.assert_called_once_with(
            "job-4",
            "published",
            external_post_id="buffer-1",
            published_at="2026-08-22T18:30:00Z",
        )


if __name__ == "__main__":
    unittest.main()
