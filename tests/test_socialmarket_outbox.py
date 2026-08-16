import unittest
from unittest.mock import Mock

from src.socialmarket_outbox import SocialMarketOutboxClient, jobs_to_backlog


class SocialMarketOutboxTests(unittest.TestCase):
    def test_jobs_preserve_copy_media_link_and_schedule(self):
        jobs=[{"id":"job-1","platform":"instagram","caption":"Approved","hashtags":["#Offer"],"format":"post","media_url":"https://project.supabase.co/storage/v1/object/public/socialmarket-creatives/a.png","tracking_url":"https://affiliate.example/exact","scheduled_for":"2026-08-20T19:00:00+03:00","brand_name":"SocialMarket","title":"Ranked product"}]
        backlog=jobs_to_backlog(jobs)
        self.assertEqual(len(backlog),1);self.assertEqual(backlog[0]["target_at"],jobs[0]["scheduled_for"]);self.assertEqual(backlog[0]["media_url"],jobs[0]["media_url"]);self.assertEqual(backlog[0]["tracking_url"],jobs[0]["tracking_url"]);self.assertIn("#Offer",backlog[0]["platform_text"]["instagram"])

    def test_job_without_explicit_schedule_is_not_executable(self):
        self.assertEqual(jobs_to_backlog([{"id":"job-2","platform":"facebook","caption":"No date","scheduled_for":None}]),[])

    def test_buffer_schedule_is_acked(self):
        client=SocialMarketOutboxClient(endpoint="https://example.test",token_provider=lambda:"token");client.ack=Mock(return_value={"ok":True})
        counts=client.sync_scheduler_actions([{"type":"scheduled","campaign":"job-3","service":"facebook","postId":"buffer-99","dueAt":"2026-08-21T18:00:00+03:00"}])
        self.assertEqual(counts["scheduled"],1)
        client.ack.assert_called_once_with("job-3","scheduled",external_post_id="buffer-99",scheduled_at="2026-08-21T18:00:00+03:00",metadata={"platform":"facebook","reconciled_existing":False})

    def test_existing_sent_post_is_acked_published(self):
        client=SocialMarketOutboxClient(endpoint="https://example.test",token_provider=lambda:"token");client.ack=Mock(return_value={"ok":True})
        counts=client.sync_scheduler_actions([{"type":"already_published","campaign":"job-sent","service":"facebook","postId":"buffer-sent","sentAt":"2026-08-14T18:00:00Z"}])
        self.assertEqual(counts["published"],1)

    def test_expired_job_is_failed_not_rescheduled(self):
        client=SocialMarketOutboxClient(endpoint="https://example.test",token_provider=lambda:"token");client.ack=Mock(return_value={"ok":True})
        counts=client.sync_scheduler_actions([{"type":"skip_late","campaign":"job-expired","service":"tiktok"}])
        self.assertEqual(counts["failed"],1)


if __name__=="__main__":unittest.main()
