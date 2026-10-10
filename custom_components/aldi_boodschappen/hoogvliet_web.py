"""Live zoeken via de zoekpagina van hoogvliet.nl (optioneel, staat standaard uit).

LET OP: hoogvliet.nl verbiedt in robots.txt het zoekpad (/search) voor bots. Deze
module doet toch, alleen als de gebruiker dat zelf kiest, één verzoek per zoekopdracht
naar die pagina. Zie de waarschuwing in de README. We beperken het zo veel mogelijk:
nooit sneller dan één verzoek per paar seconden, resultaten tien minuten onthouden,
niets op de achtergrond, en een eerlijke User-Agent.

De opbouw van de zoekpagina is niet getest tegen de echte site, daarom is de verwerking
bewust ruim: eerst ingebedde JSON (zoals __NEXT_DATA__) doorzoeken op producten, en pas
daarna de links in de HTML. Lukt geen van beide, dan valt de integratie terug op
Checkjebon en schrijft ze in het log wat ze zag.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from html import unescape
from typing import Any
from urllib.parse import quote, urljoin

import aiohttp

from .const import HOOGVLIET_SEARCH_URL, SEARCH_CACHE_SECONDS, USER_AGENT
from .hoogvliet import IMAGE_URL, HoogvlietError, image_url, product_id

_LOGGER = logging.getLogger(__name__)

MIN_INTERVAL = 3.0  # seconden tussen twee verzoeken
MAX_PAGE_BYTES = 3_000_000

_NAME_KEYS = ("name", "title", "productName", "displayName")
_PRICE_KEYS = ("price", "currentPrice", "salesPrice", "sellingPrice", "priceValue", "regularPrice", "nowPrice")
_URL_KEYS = ("url", "link", "href", "productUrl", "productURL", "path", "slug", "seoUrl")
_ID_KEYS = ("productNumber", "productId", "sku", "articleNumber", "code", "id")
_SIZE_KEYS = ("packSize", "unit", "unitSize", "content", "contentDescription", "quantity", "size", "packaging", "weight")
_IMAGE_KEYS = ("image", "imageUrl", "imageURL", "thumbnail", "picture")
_SCRIPT_JSON_RE = re.compile(
    r"<script[^>]*type=[\"']application/(?:ld\+)?json[\"'][^>]*>(.*?)</script>", re.S | re.I
)
_PRICE_TEXT_RE = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)")
_ANCHOR_RE = re.compile(
    r"<a\b[^>]*href=[\"']([^\"']*?/product/[^\"']*?-(\d{6,}))[\"'][^>]*>(.*?)</a>", re.S | re.I
)
_TAG_RE = re.compile(r"<[^>]+>")


def _to_price(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    if isinstance(value, str):
        match = _PRICE_TEXT_RE.search(value.replace("€", " ").replace(",", "."))
        if match:
            try:
                number = float(match.group(1))
            except ValueError:
                return None
            return number if number > 0 else None
    if isinstance(value, dict):
        for key in ("value", "amount", "current", "now", "price", "selling"):
            if key in value:
                found = _to_price(value[key])
                if found:
                    return found
    return None


def _str(item: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)) and not isinstance(value, bool) and key in _ID_KEYS:
            return str(int(value))
    return None


def _candidate(item: dict[str, Any]) -> dict[str, Any] | None:
    name = _str(item, _NAME_KEYS)
    if not name or len(name) < 2:
        return None
    price = next((p for k in _PRICE_KEYS if (p := _to_price(item.get(k)))), None)
    if price is None and isinstance(item.get("prices"), (dict, list)):
        prices = item["prices"]
        price = _to_price(prices if isinstance(prices, dict) else (prices[0] if prices else None))
    if price is None:
        return None

    raw_url = _str(item, _URL_KEYS)
    raw_id = _str(item, _ID_KEYS)
    url = None
    if raw_url:
        url = urljoin("https://hoogvliet.nl/", raw_url if "/" in raw_url else f"/product/{raw_url}")
    pid = product_id(url) or (raw_id if raw_id and raw_id.isdigit() and 6 <= len(raw_id) <= 12 else None)
    if not pid and not url:
        return None  # zonder link of nummer kunnen we er niets mee

    image = None
    for key in _IMAGE_KEYS:
        value = item.get(key)
        if isinstance(value, dict):
            value = value.get("url") or value.get("src")
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            image = value
            break
    if pid:
        image = image or IMAGE_URL.format(id=pid)
    return {
        "name": " ".join(name.split()),
        "price": price,
        "size": _str(item, _SIZE_KEYS),
        "url": url,
        "pid": pid,
        "image": image,
    }


def _walk(node: Any, out: list[dict[str, Any]], depth: int = 0) -> None:
    if depth > 40:
        return
    if isinstance(node, dict):
        found = _candidate(node)
        if found:
            out.append(found)
        for value in node.values():
            if isinstance(value, (dict, list)):
                _walk(value, out, depth + 1)
    elif isinstance(node, list):
        for value in node:
            if isinstance(value, (dict, list)):
                _walk(value, out, depth + 1)


def _json_blobs(page: str) -> list[Any]:
    blobs: list[Any] = []
    for match in _SCRIPT_JSON_RE.finditer(page):
        try:
            blobs.append(json.loads(unescape(match.group(1))))
        except ValueError:
            continue
    return blobs


def _from_anchors(page: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for match in _ANCHOR_RE.finditer(page):
        href, pid, inner = match.groups()
        text = unescape(_TAG_RE.sub(" ", inner))
        text = " ".join(text.split())
        # De naam is de tekst vóór de eerste prijs, en de prijs de eerste € in het blok
        euro = re.search(r"€\s*(\d+(?:[.,]\d{1,2})?)", text)
        if not euro:
            continue
        name = text[: euro.start()].strip(" -–")
        price = _to_price(euro.group(1))
        if len(name) < 2 or not price:
            continue
        found.append(
            {
                "name": name,
                "price": price,
                "size": None,
                "url": urljoin("https://hoogvliet.nl/", href),
                "pid": pid,
                "image": IMAGE_URL.format(id=pid),
            }
        )
    return found


def parse_search_page(page: str) -> list[dict[str, Any]]:
    """Producten uit de HTML van de zoekpagina. Lege lijst als er niets herkend wordt."""
    found: list[dict[str, Any]] = []
    for blob in _json_blobs(page):
        _walk(blob, found)
    if not found:
        found = _from_anchors(page)
    unique: dict[str, dict[str, Any]] = {}
    for product in found:
        key = product["pid"] or product["url"] or product["name"]
        unique.setdefault(key, product)
    return list(unique.values())


class HoogvlietWebSearch:
    """Eén verzoek per zoekopdracht naar hoogvliet.nl, vertraagd en onthouden."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._lock = asyncio.Lock()
        self._last_request = 0.0
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    async def search(self, query: str) -> list[dict[str, Any]]:
        key = " ".join(query.lower().split())
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < SEARCH_CACHE_SECONDS:
            return cached[1]

        async with self._lock:
            wait = MIN_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
            page = await self._fetch(key)

        products = parse_search_page(page)
        if not products:
            _LOGGER.warning(
                "Geen producten herkend op de Hoogvliet-zoekpagina (%d tekens). Begin van de pagina: %r",
                len(page),
                page[:400],
            )
            raise HoogvlietError("De zoekpagina van Hoogvliet had een onbekende opbouw")
        self._cache[key] = (time.monotonic(), products)
        return products

    async def _fetch(self, query: str) -> str:
        url = HOOGVLIET_SEARCH_URL.format(query=quote(query, safe=""))
        try:
            async with self._session.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    raise HoogvlietError(f"Hoogvliet gaf status {resp.status} op de zoekpagina")
                data = await resp.content.read(MAX_PAGE_BYTES)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HoogvlietError(f"Hoogvliet niet bereikbaar: {err}") from err
        return data.decode("utf-8", "ignore")
