"""Zoeken in het Aldi-assortiment via de zoekdienst die aldi.nl zelf gebruikt.

De webshop zoekt via Algolia. We sturen dezelfde zoekopdracht als de site naar
de producten-index en vragen een beperkt aantal resultaten op. De sleutel is de
(openbare, alleen-zoeken) sleutel die aldi.nl naar elke bezoeker stuurt; die
stel je in bij het instellen van de integratie en staat niet in deze code.

Dit is niet-officieel: Aldi kan de sleutel vervangen of de index hernoemen.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp

from .const import (
    ALGOLIA_INDEX,
    PRODUCT_BASE_URL,
    SEARCH_CACHE_SECONDS,
    SEARCH_LIMIT,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


class AldiApiError(Exception):
    """Fout bij het zoeken."""


class AldiAuthError(AldiApiError):
    """Sleutel of Application ID wordt niet geaccepteerd."""


def _pretty_brand(brand: Any) -> str | None:
    """'PINK LADY' -> 'Pink Lady'; laat merken met kleine letters ongemoeid."""
    if not isinstance(brand, str) or not brand.strip():
        return None
    brand = brand.strip()
    return brand.title() if brand.isupper() else brand


def _primary_image(assets: Any) -> str | None:
    if not isinstance(assets, list):
        return None
    urls = [a for a in assets if isinstance(a, dict) and a.get("url")]
    for asset in urls:
        if asset.get("type") == "primary":
            return asset["url"]
    return urls[0]["url"] if urls else None


def parse_hit(hit: Any) -> dict[str, Any] | None:
    """Zet één Algolia-hit om naar een compact product."""
    if not isinstance(hit, dict):
        return None
    base_name = hit.get("name")
    if not isinstance(base_name, str) or not base_name.strip():
        return None

    brand = _pretty_brand(hit.get("brandName"))
    name = f"{base_name.strip()} {brand}" if brand else base_name.strip()

    slug = hit.get("productSlug")
    code = hit.get("objectID") or slug or name
    url = f"{PRODUCT_BASE_URL}/{slug}.html" if slug else None

    price_obj = hit.get("currentPrice")
    price = None
    if isinstance(price_obj, dict):
        try:
            price = float(price_obj["priceValue"])
        except (KeyError, TypeError, ValueError):
            price = None

    unit = hit.get("salesUnit")
    return {
        "code": str(code),
        "name": name,
        "brand": None,  # zit al in de naam
        "description": unit if isinstance(unit, str) and unit else None,
        "price": price,
        "old_price": None,
        "base_price": None,
        "currency": "€",
        "image": _primary_image(hit.get("assets")),
        "url": url,
        "available": hit.get("isAvailable") is not False,
    }


def parse_response(payload: Any) -> list[dict[str, Any]]:
    """Haal de producten uit het Algolia-antwoord (results[0].hits)."""
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        raise AldiApiError("Onverwacht antwoord van de Aldi-zoekdienst")
    hits = results[0].get("hits")
    if not isinstance(hits, list):
        raise AldiApiError("Onverwacht antwoord van de Aldi-zoekdienst")

    products: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in hits:
        product = parse_hit(hit)
        if product and product["code"] not in seen:
            seen.add(product["code"])
            products.append(product)
    # Beschikbare producten eerst (sorteren is stabiel; de volgorde van Aldi blijft)
    products.sort(key=lambda p: not p["available"])
    return products


class AldiClient:
    """Zoekt producten bij Aldi, met een kleine cache."""

    def __init__(
        self, session: aiohttp.ClientSession, app_id: str, api_key: str
    ) -> None:
        self._session = session
        self._app_id = app_id.strip()
        self._url = f"https://{self._app_id.lower()}-dsn.algolia.net/1/indexes/*/queries"
        self._headers = {
            "X-Algolia-Application-Id": self._app_id,
            "X-Algolia-API-Key": api_key.strip(),
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    async def search(self, query: str, limit: int = SEARCH_LIMIT) -> list[dict[str, Any]]:
        query = query.strip()
        if len(query) < 2:
            return []

        key = f"{query.lower()}|{limit}"
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < SEARCH_CACHE_SECONDS:
            return cached[1]

        body = {
            "requests": [
                {"indexName": ALGOLIA_INDEX, "query": query, "hitsPerPage": limit}
            ]
        }
        try:
            async with self._session.post(
                self._url,
                json=body,
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    text = (await resp.text())[:300].replace("\n", " ")
                    _LOGGER.warning(
                        "Aldi-zoekdienst gaf status %s: %r", resp.status, text
                    )
                    if resp.status in (401, 403):
                        raise AldiAuthError(
                            f"Sleutel of Application ID geweigerd (status {resp.status})"
                        )
                    raise AldiApiError(f"Aldi-zoekdienst gaf status {resp.status}")
                payload = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise AldiApiError(f"Kon de Aldi-zoekdienst niet bereiken: {err}") from err

        products = parse_response(payload)
        self._cache[key] = (time.monotonic(), products)
        return products
