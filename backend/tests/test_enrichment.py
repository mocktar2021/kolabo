"""YouTube enrichment: parsing, guards, and selection by configuration."""
from app.modules.profiles import enrichment


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.headers = {"content-type": "application/json"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")

    def json(self):
        return self._payload


CHANNEL_PAYLOAD = {
    "items": [{
        "snippet": {
            "title": "Meditation with Odo",
            "description": "Daily guided meditation." + ("x" * 900),
            "thumbnails": {"high": {"url": "https://img.example/avatar.jpg"}},
        },
        "statistics": {"subscriberCount": "2100"},
    }]
}


def test_youtube_enricher_maps_fields(monkeypatch):
    monkeypatch.setattr(enrichment.httpx, "get", lambda *a, **k: FakeResponse(CHANNEL_PAYLOAD))
    data = enrichment.YouTubeEnricher("key").fetch("youtube", "meditationwithodo")
    assert data["display_name"] == "Meditation with Odo"
    assert data["follower_count"] == 2100
    assert data["avatar_image_url"] == "https://img.example/avatar.jpg"
    assert len(data["bio"]) <= 500  # long channel descriptions are trimmed


def test_youtube_enricher_ignores_other_platforms(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("should not call the API for another platform")
    monkeypatch.setattr(enrichment.httpx, "get", boom)
    assert enrichment.YouTubeEnricher("key").fetch("tiktok", "ama") is None


def test_youtube_enricher_handles_unknown_channel(monkeypatch):
    monkeypatch.setattr(enrichment.httpx, "get", lambda *a, **k: FakeResponse({"items": []}))
    assert enrichment.YouTubeEnricher("key").fetch("youtube", "nobody") is None


def test_youtube_enricher_survives_api_failure(monkeypatch):
    def fail(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(enrichment.httpx, "get", fail)
    # A platform outage must never break account connection.
    assert enrichment.YouTubeEnricher("key").fetch("youtube", "ama") is None


def test_no_credentials_means_no_enrichment(monkeypatch):
    monkeypatch.setattr(enrichment.settings, "youtube_api_key", "")
    built = enrichment.build_default_enricher()
    assert isinstance(built, enrichment.NoopEnricher)
    assert built.fetch("youtube", "ama") is None


def test_api_key_enables_youtube(monkeypatch):
    monkeypatch.setattr(enrichment.settings, "youtube_api_key", "test-key")
    built = enrichment.build_default_enricher()
    assert isinstance(built, enrichment.CompositeEnricher)
    assert any(isinstance(e, enrichment.YouTubeEnricher) for e in built.enrichers)
