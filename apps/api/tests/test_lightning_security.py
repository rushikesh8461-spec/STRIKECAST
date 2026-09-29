from strikecast_core.data.lightning import get_lightning


def test_live_feed_url_requires_allowlisted_https_host(monkeypatch):
    monkeypatch.setenv("LIGHTNING_MODE", "live")
    monkeypatch.setenv("LIGHTNING_FEED_URL", "http://127.0.0.1:8000/admin")
    monkeypatch.setenv("LIGHTNING_FEED_ALLOWED_HOSTS", "127.0.0.1")
    result = get_lightning(12, 77)
    assert result["mode"] == "none"
    assert "127.0.0.1" not in result["source"]


def test_live_feed_is_unavailable_without_explicit_host_allowlist(monkeypatch):
    monkeypatch.setenv("LIGHTNING_MODE", "live")
    monkeypatch.setenv("LIGHTNING_FEED_URL", "https://feed.example.invalid/api")
    monkeypatch.delenv("LIGHTNING_FEED_ALLOWED_HOSTS", raising=False)
    result = get_lightning(12, 77)
    assert result["mode"] == "none"
    assert result["strikes"] == []
