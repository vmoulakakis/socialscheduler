from scripts.reconcile_provider_deliveries import normalize_provider_post


def test_brightbean_published_requires_provider_timestamp():
    payload = {"status": "published", "published_at": None, "platform_posts": [{"platform": "linkedin_personal", "status": "published"}]}
    assert normalize_provider_post("brightbean", payload, "linkedin")["terminal"] is False


def test_brightbean_published_readback_is_terminal_with_real_timestamp():
    payload = {"status": "published", "platform_posts": [{
        "platform": "linkedin_personal", "status": "published",
        "published_at": "2026-08-27T12:00:00Z", "platform_post_id": "li-123",
    }]}
    result = normalize_provider_post("brightbean", payload, "linkedin")
    assert result["status"] == "published"
    assert result["published_at"] == "2026-08-27T12:00:00Z"
    assert result["external_platform_post_id"] == "li-123"


def test_provider_error_is_terminal_but_elapsed_schedule_is_not():
    assert normalize_provider_post("postzen", {"post": {"status": "failed", "error": "denied"}}, "linkedin")["status"] == "failed"
    assert normalize_provider_post("postzen", {"post": {"status": "scheduled"}}, "linkedin")["terminal"] is False
