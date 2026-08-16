import unittest
from unittest.mock import Mock

from src.socialmarket_outbox import SocialMarketOutboxClient, jobs_to_backlog


class SocialMarketOutboxTests(unittest.TestCase):
    def test_jobs_to_backlog_preserves_platform_copy_media_link_and_schedule(self):
        jobs = [{
            "id": "job-1",
            "platform": "instagram",
            "caption": "Approved by SocialMarket",
            "hashtags": ["#GreekAI", "#Offer"],
            "format": "post",
            "media_url": "https://project.supabase.co/storage/v1/object/public/socialmarket-creatives/a.png",
            "tracking_url": "https://affiliate.example/exact",
            "scheduled_for": "2026-08-20T19:00:00+03:00",
            "brand_name": "Λύσεις που Αξίζουν / Biz Box Solver",
            "title": "Ranked product",
        }]
        backlog = jobs_to_backlog(jobs)
        self.assertEqual(len(backlog), 1)
        self.assertEqual(backlog[0]["id"], "job-1")
        self.assertEqual(backlog[0]["services"], ["instagram"])
        self.assertEqual(backlog[0]["target_at"], "2026-08-20T19:00:00+03:00")
        self.assertIn("Approved by SocialMarket", backlog[0]["platform_text"]["instagram"])
        self.assertIn("#GreekAI", backlog[0]["platform_text"]["instagram"])
        self.assertEqual(backlog[0]["media_url"], jobs[0]["media_url"])
        self.assertEqual(backlog[0]["tracking_url"], "https://affiliate.example/exact")

    def test_job_without_explicit_schedule_is_not_executable(self):
        jobs = [{"id": "job-2", "platform": "facebook", "caption": "No date", "scheduled_for": None}]
        self.assertEqual(jobs_to_backlog(jobs), [])

    def test_scheduled_buffer_action_is_acked_to_socialmarket(self):
        client = SocialMarketOutboxClient(endpoint="https://example.test", token_provider=lambda: "token")
        client.ack = Mock(return_value={"ok": True})
        counts = client.sync_scheduler_actions([{
            "type": "scheduled", "campaign": "job-3", "service": "facebook",
            "postId": "buffer-99", "dueAt": "2026-08-21T18:00:00+03:00",
        }])
        self.assertEqual(counts["scheduled"], 1)
        client.ack.assert_called_once_with(
            "job-3", "scheduled", external_post_id="buffer-99",
            scheduled_at="2026-08-21T18:00:00+03:00",
            metadata={"platform": "facebook", "reconciled_existing": False},
        )

    def test_existing_sent_buffer_post_is_acked_published_not_republished(self):
        client = SocialMarketOutboxClient(endpoint="https://example.test", token_provider=lambda: "token")
        client.ack = Mock(return_value={"ok": True})
        counts = client.sync_scheduler_actions([{
            "type": "already_published", "campaign": "job-sent", "service": "facebook",
            "postId": "buffer-sent", "sentAt": "2026-08-14T18:00:00Z",
        }])
        self.assertEqual(counts["published"], 1)
        client.ack.assert_called_once_with(
            "job-sent", "published", external_post_id="buffer-sent",
            published_at="2026-08-14T18:00:00Z",
            metadata={"platform": "facebook", "reconciled_existing": True},
        )

    def test_expired_job_is_failed_not_rescheduled(self):
        client = SocialMarketOutboxClient(endpoint="https://example.test", token_provider=lambda: "token")
        client.ack = Mock(return_value={"ok": True})
        counts = client.sync_scheduler_actions([{"type": "skip_late", "campaign": "job-expired", "service": "tiktok"}])
        self.assertEqual(counts["failed"], 1)
        client.ack.assert_called_once_with(
            "job-expired", "failed", external_post_id=None,
            error="scheduled_time_elapsed", metadata={"platform": "tiktok"},
        )


if __name__ == "__main__":
    unittest.main()
