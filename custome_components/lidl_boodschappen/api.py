"""Client voor de zoekfunctie van de Lidl-webshop.

LET OP: dit is een niet-officiële, ongedocumenteerde endpoint van Lidl. De
structuur kan zonder waarschuwing veranderen. De parser is daarom bewust
defensief geschreven en zoekt op meerdere plekken naar de velden.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp

from .const import COUNTRIES, SEARCH_CACHE_SECONDS, SEARCH_LIMIT

_LOGGER = logging.getLogger(__name__)

HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 HomeAssistant-LidlBoodschappen"
    ),
}


class LidlApiError(Exception):
    """Fout bij het ophalen van producten."""


def _first(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_item(raw: dict[str, Any], base_url: str) -> dict[str, Any] | None:
    """Zet één item uit het Lidl-antwoord om naar een compact product."""
    if not isinstance(raw, dict):
        return None

    gridbox = raw.get("gridbox") or {}
    data = _first(gridbox.get("data"), raw.get("data"), raw) or {}
    if not isinstance(data, dict):
        return None

    title = _first(data.get("fullTitle"), data.get("title"), raw.get("title"))
    if not title:
        return None

    # Prijs
    price_obj = data.get("price") if isinstance(data.get("price"), dict) else {}
    price = _as_float(_first(price_obj.get("price"), data.get("price")))
    old_price = _as_float(price_obj.get("oldPrice"))
    base_price = price_obj.get("basePrice") or {}
    base_text = base_price.get("text") if isinstance(base_price, dict) else None
    currency = _first(price_obj.get("currencySymbol"), "€")

    # Afbeelding
    image = _first(data.get("image"), data.get("imageUrl"))
    if not image:
        image_list = data.get("imageList") or []
        if image_list and isinstance(image_list[0], dict):
            image = image_list[0].get("image")
        elif image_list and isinstance(image_list[0], str):
            image = image_list[0]

    # Link
    url = _first(data.get("canonicalUrl"), data.get("canonicalPath"), data.get("url"))
    if url and url.startswith("/"):
        url = f"{base_url}{url}"

    code = _first(
        data.get("productId"),
        data.get("erpNumber"),
        raw.get("code"),
        data.get("itemId"),
        url,
        title,
    )

    brand = data.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")

    keyfacts = data.get("keyfacts") if isinstance(data.get("keyfacts"), dict) else {}
    description = _first(
        keyfacts.get("supplementalDescription"),
        keyfacts.get("description"),
        data.get("subtitle"),
    )

    return {
        "code": str(code),
        "name": str(title).strip(),
        "brand": brand,
        "description": description,
        "price": price,
        "old_price": old_price,
        "base_price": base_text,
        "currency": currency,
        "image": image,
        "url": url,
    }


class LidlClient:
    """Zoekt producten op de Lidl-site, met een kleine cache."""

    def __init__(self, session: aiohttp.ClientSession, country: str) -> None:
        self._session = session
        self._base_url, self._locale, self._assortment = COUNTRIES.get(
            country, COUNTRIES["NL"]
        )
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    async def search(self, query: str, limit: int = SEARCH_LIMIT) -> list[dict[str, Any]]:
        query = query.strip()
        if len(query) < 2:
            return []

        key = f"{query.lower()}|{limit}"
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < SEARCH_CACHE_SECONDS:
            return cached[1]

        params = {
            "q": query,
            "offset": 0,
            "fetchsize": limit,
            "locale": self._locale,
            "assortment": self._assortment,
            "version": "2.1.0",
        }
        try:
            async with self._session.get(
                f"{self._base_url}/q/api/search",
                params=params,
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    raise LidlApiError(f"Lidl gaf status {resp.status}")
                payload = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise LidlApiError(f"Kon Lidl niet bereiken: {err}") from err

        raw_items = payload.get("items") if isinstance(payload, dict) else None
        if raw_items is None:
            _LOGGER.debug("Onverwacht antwoord van Lidl: %s", str(payload)[:500])
            raw_items = []

        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in raw_items:
            product = parse_item(raw, self._base_url)
            if product and product["code"] not in seen:
                seen.add(product["code"])
                results.append(product)

        self._cache[key] = (time.monotonic(), results)
        return results
