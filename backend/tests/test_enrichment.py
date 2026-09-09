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


# --- Fetching the avatar itself -----------------------------------------
#
# fetch_image is handed a url that arrived inside somebody else's API response
# and then dials it FROM INSIDE THE PROCESS. That is the one place in this
# module where a third party chooses where our network goes, and from in here
# a link-local or RFC1918 address answers in a way it never would from a
# creator's browser. The guards below are not decoration: see the docstring on
# fetch_image, and app/core/urls.py for the rule it shares with the link field
# on a deliverable submission.


class FakeStream:
    """Shaped like the context manager httpx.stream returns.

    It records the chunks it was actually asked for, so a test can assert that
    a ceiling STOPPED the read rather than merely discarding the result once it
    had all arrived. That is the difference between a bound and a formality,
    and it is invisible if you only look at the return value.
    """

    def __init__(self, chunks, content_type="image/png",
                 url="https://img.example/avatar.png", content_length=None):
        self.chunks = chunks
        self.url = url
        self.headers = {"content-type": content_type}
        if content_length is not None:
            self.headers["content-length"] = content_length
        self.served = []

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def raise_for_status(self):
        return None

    def iter_bytes(self):
        for chunk in self.chunks:
            self.served.append(chunk)
            yield chunk


def _no_request(monkeypatch):
    """Patch httpx.stream so that any call to it is recorded, not made.

    Recorded rather than raised: fetch_image catches Exception, so a guard
    written as `raise AssertionError` inside it would be swallowed and the test
    would pass for the wrong reason. A list that must still be empty at the end
    cannot be swallowed.
    """
    calls = []

    def record(*a, **k):
        calls.append((a, k))
        return FakeStream([b"x"])

    monkeypatch.setattr(enrichment.httpx, "stream", record)
    return calls


def test_fetch_image_returns_the_body_and_its_type(monkeypatch):
    stream = FakeStream([b"PNG", b"data"])
    monkeypatch.setattr(enrichment.httpx, "stream", lambda *a, **k: stream)
    assert enrichment.fetch_image("https://img.example/avatar.png") == (b"PNGdata", "image/png")


def test_fetch_image_abandons_a_body_over_the_ceiling(monkeypatch):
    megabyte = b"x" * (1024 * 1024)
    stream = FakeStream([megabyte] * 20)
    monkeypatch.setattr(enrichment.httpx, "stream", lambda *a, **k: stream)
    assert enrichment.fetch_image("https://img.example/huge.png") is None
    # Six megabytes were read and then the read was abandoned, not twenty. The
    # limit is enforced while the body arrives, which is the only place a
    # limit on a body can actually be enforced.
    assert len(stream.served) == enrichment.MAX_FETCHED_IMAGE_BYTES // len(megabyte) + 1


def test_fetch_image_short_circuits_an_oversized_content_length(monkeypatch):
    """A declared length over the ceiling saves reading a byte. It is only ever
    a saving, never the check: Content-Length is a claim, and the running total
    above is what a lying one runs into."""
    stream = FakeStream([b"x"], content_length=str(enrichment.MAX_FETCHED_IMAGE_BYTES + 1))
    monkeypatch.setattr(enrichment.httpx, "stream", lambda *a, **k: stream)
    assert enrichment.fetch_image("https://img.example/huge.png") is None
    assert stream.served == []


def test_fetch_image_refuses_a_private_host_before_any_request(monkeypatch):
    """The metadata endpoint is the single most valuable thing a server-side
    fetch can be pointed at, and a Redis port on a private address is the
    second. Neither is dialled at all: the refusal happens before the request,
    not after the response."""
    calls = _no_request(monkeypatch)
    assert enrichment.fetch_image("http://169.254.169.254/latest/meta-data/") is None
    assert enrichment.fetch_image("http://127.0.0.1:8000/internal") is None
    assert enrichment.fetch_image("http://10.0.0.5:6379/") is None
    assert enrichment.fetch_image("http://localhost/internal") is None
    assert calls == []


def test_fetch_image_refuses_a_url_no_browser_would_follow(monkeypatch):
    calls = _no_request(monkeypatch)
    assert enrichment.fetch_image("file:///etc/passwd") is None
    assert enrichment.fetch_image("javascript:alert(1)") is None
    assert enrichment.fetch_image("") is None
    assert calls == []


def test_fetch_image_refuses_a_non_image_content_type(monkeypatch):
    """Checked BEFORE the body, so an HTML error page is not paid for first."""
    stream = FakeStream([b"<html>"], content_type="text/html")
    monkeypatch.setattr(enrichment.httpx, "stream", lambda *a, **k: stream)
    assert enrichment.fetch_image("https://img.example/not-an-image") is None
    assert stream.served == []


def test_fetch_image_rechecks_where_a_redirect_landed(monkeypatch):
    """A guard on the first hop only is not a guard. Redirects are still
    followed, because avatar urls redirect constantly, but a public url that
    answers 302 to the metadata endpoint must not walk the request there."""
    stream = FakeStream([b"x"], url="http://169.254.169.254/latest/meta-data/")
    monkeypatch.setattr(enrichment.httpx, "stream", lambda *a, **k: stream)
    assert enrichment.fetch_image("https://img.example/redirects") is None
    assert stream.served == []
