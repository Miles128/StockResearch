"""Short-timeout URL excerpt fetch for news / announcement enrichment."""

from __future__ import annotations

import logging
import re
from html import unescape

import httpx

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT_SEC = 4.0
_MAX_EXCERPT_CHARS = 800
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
)


def _strip_html(raw: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    # Prefer meta description / og:description when present.
    meta_match = re.search(
        r'(?is)<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+'
        r'content=["\']([^"\']+)["\']',
        raw,
    )
    if not meta_match:
        meta_match = re.search(
            r'(?is)<meta[^>]+content=["\']([^"\']+)["\'][^>]+'
            r'(?:name|property)=["\'](?:description|og:description)["\']',
            raw,
        )
    if meta_match:
        candidate = unescape(meta_match.group(1)).strip()
        if len(candidate) >= 20:
            return re.sub(r"\s+", " ", candidate)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_url_excerpt_sync(url: str, *, max_chars: int = _MAX_EXCERPT_CHARS) -> str:
    """Fetch a short plain-text excerpt from an http(s) URL. Empty on failure."""
    cleaned = (url or "").strip()
    if not cleaned.startswith(("http://", "https://")):
        return ""
    try:
        with httpx.Client(
            timeout=_FETCH_TIMEOUT_SEC,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = client.get(cleaned)
            resp.raise_for_status()
            ctype = (resp.headers.get("content-type") or "").lower()
            if "html" not in ctype and "text" not in ctype and ctype:
                return ""
            text = _strip_html(resp.text[:80_000])
            if not text:
                return ""
            return text[:max_chars]
    except Exception as exc:
        logger.debug("URL excerpt fetch failed for %s: %s", cleaned[:80], exc)
        return ""


async def fetch_url_excerpt(url: str, *, max_chars: int = _MAX_EXCERPT_CHARS) -> str:
    """Async wrapper around sync fetch (thread offload)."""
    import asyncio

    return await asyncio.to_thread(fetch_url_excerpt_sync, url, max_chars=max_chars)
