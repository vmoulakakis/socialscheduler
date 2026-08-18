from __future__ import annotations

import pytest

from src.postzen_client import PostZenAPIError, PostZenClient


class FakePostZen(PostZenClient):
    def __init__(self, accounts):
        super().__init__(api_url="https://api.postzen.dev", api_key="test")
        self.accounts = accounts
        self.calls = []

    def list_accounts(self):
        return list(self.accounts)

    def _request(self, method, path, payload=None, *, extra_headers=None):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "payload": payload,
                "headers": extra_headers or {},
            }
        )
        return {
            "post": {
                "_id": "postzen-post-1",
                "status": "scheduled",
                "platforms": [
                    {
                        "platform": "linkedin",
                        "platformPostUrl": "https://www.linkedin.com/feed/update/test",
                    }
                ],
            },
            "message": "Post scheduled successfully",
        }


def account(platform="linkedin", account_id="pz-linkedin-1"):
    return {
        "_id": account_id,
        "platform": platform,
        "status": "connected",
        "isActive": True,
        "username": "tester",
    }


def test_schedule_job_uses_current_platforms_account_id_contract(monkeypatch):
    monkeypatch.delenv("POSTZEN_ACCOUNT_LINKEDIN", raising=False)
    client = FakePostZen([account()])
    job = {
        "id": "job-123",
        "title": "A useful post",
        "platform": "linkedin",
        "caption": "Useful copy",
        "hashtags": ["#Useful", "#AI"],
        "tracking_url": "https://example.com/?utm_source=linkedin",
        "media_url": "https://example.com/poster.png",
        "scheduled_for": "2026-08-20T05:45:00Z",
    }

    result = client.schedule_job(job)

    assert result["post"]["status"] == "scheduled"
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "POST"
    assert call["path"] == "/v1/posts"
    assert "channels" not in call["payload"]
    assert call["payload"]["platforms"] == [
        {"platform": "linkedin", "accountId": "pz-linkedin-1"}
    ]
    assert call["payload"]["scheduledFor"] == "2026-08-20T05:45:00Z"
    assert call["payload"]["timezone"] == "UTC"
    assert call["payload"]["mediaItems"] == [
        {"url": "https://example.com/poster.png", "title": "A useful post"}
    ]
    assert call["headers"]["X-Request-Id"] == "job-123"
    assert call["payload"]["content"].count("https://example.com/?utm_source=linkedin") == 1
    assert "#Useful" in call["payload"]["content"]


def test_resolve_account_refuses_ambiguous_platform(monkeypatch):
    monkeypatch.delenv("POSTZEN_ACCOUNT_LINKEDIN", raising=False)
    client = FakePostZen([account(account_id="one"), account(account_id="two")])

    with pytest.raises(PostZenAPIError, match="Multiple connected PostZen accounts"):
        client.resolve_account("linkedin")


def test_configured_account_mapping_resolves_exact_account(monkeypatch):
    monkeypatch.setenv("POSTZEN_ACCOUNT_LINKEDIN", "two")
    client = FakePostZen([account(account_id="one"), account(account_id="two")])

    assert client.resolve_account("linkedin")["_id"] == "two"


def test_extracts_current_create_response_identifiers():
    response = {
        "post": {
            "_id": "postzen-post-1",
            "platforms": [
                {
                    "platform": "linkedin",
                    "platformPostUrl": "https://www.linkedin.com/feed/update/test",
                }
            ],
        }
    }

    assert PostZenClient.extract_post_id(response) == "postzen-post-1"
    assert (
        PostZenClient.extract_permalink(response)
        == "https://www.linkedin.com/feed/update/test"
    )
