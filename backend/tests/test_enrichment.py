"""Social enrichment: parsing, guards, and selection by configuration.

Covers the YouTube enricher (API key), and the two Meta Graph enrichers,
Instagram (Business Discovery) and Facebook (Page node). None of these calls a
live API: httpx.get is monkeypatched with canned responses shaped like the real
ones, the same way the whole suite treats the Mobile Money provider.
"""
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


# --- Instagram (Meta Graph Business Discovery) --------------------------

# Shaped like a Business Discovery response: the target creator's public data
# nested under business_discovery, keyed by the field expression sent.
IG_PAYLOAD = {
    "business_discovery": {
        "username": "odo",
        "name": "Meditation with Odo",
        "biography": "Daily guided meditation." + ("x" * 900),
        "followers_count": 4200,
        "profile_picture_url": "https://img.example/ig-avatar.jpg",
    },
    "id": "17841400000000000",
}


def test_instagram_enricher_maps_fields(monkeypatch):
    monkeypatch.setattr(enrichment.httpx, "get", lambda *a, **k: FakeResponse(IG_PAYLOAD))
    data = enrichment.InstagramEnricher("token", "17841400000000000", "v19.0").fetch("instagram", "@odo")
    assert data["display_name"] == "Meditation with Odo"
    assert data["follower_count"] == 4200
    assert data["avatar_image_url"] == "https://img.example/ig-avatar.jpg"
    assert len(data["bio"]) <= 500  # long bios are trimmed


def test_instagram_enricher_falls_back_to_username_for_name(monkeypatch):
    payload = {"business_discovery": {"username": "odo", "followers_count": 10, "biography": "hi"}}
    monkeypatch.setattr(enrichment.httpx, "get", lambda *a, **k: FakeResponse(payload))
    data = enrichment.InstagramEnricher("token", "biz", "v19.0").fetch("instagram", "odo")
    # A creator who left the name field blank is still better shown by their
    # handle than by an empty display name.
    assert data["display_name"] == "odo"


def test_instagram_enricher_ignores_other_platforms(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("should not call the API for another platform")
    monkeypatch.setattr(enrichment.httpx, "get", boom)
    assert enrichment.InstagramEnricher("token", "biz", "v19.0").fetch("facebook", "odo") is None


def test_instagram_enricher_needs_the_querying_business_id(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("should not call the API without the querying account id")
    monkeypatch.setattr(enrichment.httpx, "get", boom)
    # Business Discovery only answers a business that is asking; no id, no call.
    assert enrichment.InstagramEnricher("token", "", "v19.0").fetch("instagram", "odo") is None


def test_instagram_enricher_handles_unknown_or_personal_account(monkeypatch):
    # A missing handle, or one on a personal account, comes back with no
    # business_discovery block rather than an error.
    monkeypatch.setattr(enrichment.httpx, "get", lambda *a, **k: FakeResponse({"id": "biz"}))
    assert enrichment.InstagramEnricher("token", "biz", "v19.0").fetch("instagram", "nobody") is None


def test_instagram_enricher_survives_api_failure(monkeypatch):
    def fail(*a, **k):
        raise RuntimeError("graph down")
    monkeypatch.setattr(enrichment.httpx, "get", fail)
    # A platform outage must never break account connection.
    assert enrichment.InstagramEnricher("token", "biz", "v19.0").fetch("instagram", "odo") is None


# --- Facebook (Meta Graph Page node) ------------------------------------

FB_PAYLOAD = {
    "name": "Odo Media",
    "followers_count": 5400,
    "fan_count": 5000,
    "about": "Wellness and meditation." + ("y" * 900),
    "picture": {"data": {"url": "https://img.example/fb-avatar.jpg"}},
    "id": "123456",
}


def test_facebook_enricher_maps_fields(monkeypatch):
    monkeypatch.setattr(enrichment.httpx, "get", lambda *a, **k: FakeResponse(FB_PAYLOAD))
    data = enrichment.FacebookEnricher("token", "v19.0").fetch("facebook", "odomedia")
    assert data["display_name"] == "Odo Media"
    # followers_count is the number to show, not fan_count (likes).
    assert data["follower_count"] == 5400
    assert data["avatar_image_url"] == "https://img.example/fb-avatar.jpg"
    assert len(data["bio"]) <= 500


def test_facebook_enricher_falls_back_to_fan_count(monkeypatch):
    payload = {"name": "Odo Media", "fan_count": 800, "picture": {"data": {"url": "u"}}}
    monkeypatch.setattr(enrichment.httpx, "get", lambda *a, **k: FakeResponse(payload))
    data = enrichment.FacebookEnricher("token", "v19.0").fetch("facebook", "odomedia")
    # Older Pages that only report fan_count still get a follower number.
    assert data["follower_count"] == 800


def test_facebook_enricher_ignores_other_platforms(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("should not call the API for another platform")
    monkeypatch.setattr(enrichment.httpx, "get", boom)
    assert enrichment.FacebookEnricher("token", "v19.0").fetch("instagram", "odo") is None


def test_facebook_enricher_handles_unresolved_page(monkeypatch):
    # An unknown vanity, or one the token cannot read, returns no name.
    monkeypatch.setattr(enrichment.httpx, "get", lambda *a, **k: FakeResponse({"id": "0"}))
    assert enrichment.FacebookEnricher("token", "v19.0").fetch("facebook", "nobody") is None


def test_facebook_enricher_survives_api_failure(monkeypatch):
    def fail(*a, **k):
        raise RuntimeError("graph down")
    monkeypatch.setattr(enrichment.httpx, "get", fail)
    assert enrichment.FacebookEnricher("token", "v19.0").fetch("facebook", "odomedia") is None


# --- Selection by configuration -----------------------------------------


def test_meta_token_and_business_id_enable_both(monkeypatch):
    monkeypatch.setattr(enrichment.settings, "youtube_api_key", "")
    monkeypatch.setattr(enrichment.settings, "meta_graph_token", "token")
    monkeypatch.setattr(enrichment.settings, "instagram_business_account_id", "biz")
    built = enrichment.build_default_enricher()
    assert isinstance(built, enrichment.CompositeEnricher)
    kinds = [type(e) for e in built.enrichers]
    assert enrichment.InstagramEnricher in kinds
    assert enrichment.FacebookEnricher in kinds


def test_meta_token_without_business_id_enables_facebook_only(monkeypatch):
    monkeypatch.setattr(enrichment.settings, "youtube_api_key", "")
    monkeypatch.setattr(enrichment.settings, "meta_graph_token", "token")
    monkeypatch.setattr(enrichment.settings, "instagram_business_account_id", "")
    built = enrichment.build_default_enricher()
    kinds = [type(e) for e in built.enrichers]
    # Facebook runs on the token alone; Instagram cannot without the querying id.
    assert enrichment.FacebookEnricher in kinds
    assert enrichment.InstagramEnricher not in kinds
