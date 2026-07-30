"""AI drafted creator bios, in French and English.

A blank bio is the most common reason a new profile looks abandoned, and it is
the one field a creator is least likely to write well about themselves. The
generator turns facts the platform already holds into a short first person bio
the creator then edits.

Two rules shape the whole module:

1. It may only use facts passed to it. A model left to invent creator bios will
   produce brand collaborations that never happened, because that is what
   creator bios usually contain. On a marketplace selling trust to brands, a
   fabricated collaboration is far worse than an empty field, so the prompt
   states the facts explicitly and forbids anything else.
2. No numbers in the prose. Follower counts move, and a bio claiming "over
   10,000 followers" is wrong within a month with no way for anyone to notice.
   Counts belong in the audience block, which is refreshed from the platforms.

Output is always a draft: it is written to the profile only when the creator
accepts it, and it is editable afterwards like any other field.

Generation is off unless ANTHROPIC_API_KEY is set, in which case the endpoint
reports that it is unavailable rather than failing in a confusing way.
"""
import logging
from typing import Protocol

import httpx

from app.core.config import settings

_log = logging.getLogger("kolabo.profiles.bio_ai")

TIMEOUT_SECONDS = 20.0

# A bio longer than this stops being scannable in a search result card.
MAX_CHARS = 400

LANGUAGES = {"fr", "en"}

_LANGUAGE_NAMES = {"fr": "French", "en": "English"}

SYSTEM_PROMPT = """You write short profile bios for creators on Kolabo, an \
influencer marketing marketplace in West and Central Africa. Brands read these \
bios when deciding who to hire.

Rules you must follow exactly:
- Use ONLY the facts given to you. Invent nothing.
- Never mention a brand, client, campaign or collaboration unless it appears \
in the facts. Creator bios often name brands, so you may be tempted. Do not.
- Never state follower counts, view counts, engagement rates or any other \
number. Those are shown elsewhere and change over time.
- Never claim the creator is verified, award winning, top rated, or the best \
at anything.
- Write in the first person, 2 to 3 sentences, at most 400 characters.
- Be concrete and plain. No marketing cliches such as "passionate about" or \
"content creator extraordinaire".
- Write in {language} only. Do not translate or add any other language.
- Return only the bio text. No preamble, no quotation marks, no explanation."""


class BioGenerator(Protocol):
    def generate(self, facts: dict, language: str) -> str | None:
        """Return a draft bio, or None if generation is unavailable."""
        ...


class NoopBioGenerator:
    """Used when no credentials are configured. Never guesses."""

    available = False

    def generate(self, facts: dict, language: str) -> str | None:
        return None


def _format_facts(facts: dict) -> str:
    """Render the facts as labelled lines. Anything absent is omitted rather
    than sent as empty, so the model is never invited to fill a blank."""
    lines: list[str] = []
    if facts.get("display_name"):
        lines.append(f"Name: {facts['display_name']}")
    if facts.get("location"):
        lines.append(f"Based in: {facts['location']}")
    if facts.get("categories"):
        lines.append(f"Content topics: {', '.join(facts['categories'])}")
    if facts.get("platforms"):
        lines.append(f"Active on: {', '.join(facts['platforms'])}")
    if facts.get("recent_titles"):
        titles = "; ".join(facts["recent_titles"][:5])
        lines.append(f"Titles of their recent posts, as a guide to subject and tone: {titles}")
    return "\n".join(lines)


def has_enough_facts(facts: dict) -> bool:
    """Topics or recent posts are the difference between a bio about this
    creator and a bio about any creator. A name alone is not enough."""
    return bool(facts.get("categories") or facts.get("recent_titles"))


class AnthropicBioGenerator:
    """Draft bios via the Anthropic Messages API."""

    API_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    available = True

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, facts: dict, language: str) -> str | None:
        if not self.api_key or language not in LANGUAGES:
            return None
        if not has_enough_facts(facts):
            return None

        system = SYSTEM_PROMPT.format(language=_LANGUAGE_NAMES[language])
        payload = {
            "model": self.model,
            "max_tokens": 400,
            "system": system,
            "messages": [{
                "role": "user",
                "content": f"Write the bio from these facts:\n\n{_format_facts(facts)}",
            }],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
        }
        try:
            response = httpx.post(self.API_URL, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            blocks = response.json().get("content", [])
        except (httpx.HTTPError, ValueError) as exc:
            # A generation failure must never block onboarding: the creator
            # simply writes their own bio, as they would have anyway.
            _log.warning("Bio generation failed: %s", exc)
            return None

        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
        if not text:
            return None
        return text[:MAX_CHARS].strip()


def build_default_generator() -> BioGenerator:
    if settings.anthropic_api_key:
        return AnthropicBioGenerator(settings.anthropic_api_key, settings.bio_model)
    return NoopBioGenerator()


default_generator: BioGenerator = build_default_generator()
