"""Productcatalogus van aldi.nl.

Aldi heeft geen zoek-API. Wel publiceert aldi.nl een sitemap met alle
productpagina's (toegestaan volgens robots.txt). We halen die lijst hooguit
één keer per week op, bewaren hem lokaal en zoeken daar zelf in. Het zoekveld
doet dus geen verzoeken naar Aldi. Pas bij het toevoegen van een product halen
we die ene pagina op voor foto en merknaam.

Aldi toont op de productpagina's geen prijzen; die nemen we dus niet mee.
"""

from __future__ import annotations

import html
import logging
import re
import time
import unicodedata
from typing import Any, Protocol

import aiohttp

from .const import CATALOG_MAX_AGE, SEARCH_LIMIT, SITEMAP_URL, USER_AGENT

_LOGGER = logging.getLogger(__name__)

_LOC_RE = re.compile(
    r"<loc>\s*(https?://[^<\s]+/product/([^<\s/]+?)-(\d{5,})\.html)\s*</loc>"
)
_OG_RE = re.compile(
    r'<meta[^>]+property=["\']og:(title|image)["\'][^>]+content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_OG_RE_REVERSED = re.compile(
    r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']og:(title|image)["\']',
    re.IGNORECASE,
)


class AldiApiError(Exception):
    """Fout bij het ophalen van de Aldi-catalogus."""


class StoreLike(Protocol):
    async def async_load(self) -> Any: ...
    async def async_save(self, data: Any) -> None: ...


def normalize(text: str) -> str:
    """Kleine letters, zonder accenten, leestekens als spatie."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def name_from_slug(slug: str) -> str:
    """'volle-kwark' -> 'Volle kwark'."""
    words = slug.replace("-", " ").strip()
    return words[:1].upper() + words[1:]


def parse_sitemap(xml: str) -> list[dict[str, str]]:
    """Haal product-URL's uit de sitemap en leid de naam af uit de slug."""
    products: list[dict[str, str]] = []
    seen: set[str] = set()
    for url, slug, code in _LOC_RE.findall(xml):
        if code in seen:
            continue
        seen.add(code)
        name = name_from_slug(slug)
        products.append(
            {"code": code, "name": name, "url": url, "norm": normalize(name)}
        )
    return products


def parse_product_page(page: str) -> dict[str, str]:
    """Lees og:title en og:image uit een productpagina."""
    found: dict[str, str] = {}
    for kind, value in _OG_RE.findall(page):
        found.setdefault(kind.lower(), html.unescape(value).strip())
    for value, kind in _OG_RE_REVERSED.findall(page):
        found.setdefault(kind.lower(), html.unescape(value).strip())
    return found


def _score(norm_name: str, terms: list[str]) -> int | None:
    """Lager = beter. None = geen match (alle zoekwoorden moeten voorkomen)."""
    words = norm_name.split()
    score = 0
    for term in terms:
        if term not in norm_name:
            return None
        if any(w == term for w in words):
            score += 0  # heel woord
        elif any(w.startswith(term) for w in words):
            score += 2  # begin van een woord
        else:
            score += 4  # komt alleen midden in een woord voor
    if words and not words[0].startswith(terms[0]):
        score += 1
    return score


class AldiClient:
    """Catalogus + lokaal zoeken + details per product."""

    def __init__(
        self, session: aiohttp.ClientSession, store: StoreLike | None = None
    ) -> None:
        self._session = session
        self._store = store
        self._catalog: list[dict[str, str]] = []
        self._fetched_at: float = 0.0
        self._loaded = False
        self._details: dict[str, dict[str, str]] = {}

    @property
    def catalog_size(self) -> int:
        return len(self._catalog)

    async def _load_from_store(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if self._store is None:
            return
        data = await self._store.async_load()
        if isinstance(data, dict) and data.get("products"):
            self._catalog = data["products"]
            self._fetched_at = float(data.get("fetched_at", 0))

    async def _get_text(self, url: str) -> str:
        try:
            async with self._session.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    body = (await resp.text())[:200].replace("\n", " ")
                    _LOGGER.warning(
                        "Aldi gaf status %s voor %s (server=%s, antwoord=%r)",
                        resp.status,
                        url,
                        resp.headers.get("Server", "?"),
                        body,
                    )
                    raise AldiApiError(f"Aldi gaf status {resp.status}")
                return await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise AldiApiError(f"Kon Aldi niet bereiken: {err}") from err

    async def async_refresh(self, force: bool = False) -> None:
        """Ververs de catalogus als die ontbreekt of ouder is dan een week."""
        await self._load_from_store()
        age = time.time() - self._fetched_at
        if self._catalog and not force and age < CATALOG_MAX_AGE:
            return
        try:
            xml = await self._get_text(SITEMAP_URL)
            products = parse_sitemap(xml)
            if not products:
                raise AldiApiError("Geen producten gevonden in de Aldi-sitemap")
        except AldiApiError:
            if self._catalog:
                _LOGGER.warning("Verversen mislukt, ik gebruik de oude catalogus")
                return
            raise
        self._catalog = products
        self._fetched_at = time.time()
        _LOGGER.debug("Aldi-catalogus ververst: %s producten", len(products))
        if self._store is not None:
            await self._store.async_save(
                {"fetched_at": self._fetched_at, "products": products}
            )

    async def search(self, query: str, limit: int = SEARCH_LIMIT) -> list[dict[str, Any]]:
        terms = normalize(query).split()
        if not terms or len(normalize(query)) < 2:
            return []
        await self.async_refresh()

        scored: list[tuple[int, str, dict[str, str]]] = []
        for product in self._catalog:
            score = _score(product["norm"], terms)
            if score is not None:
                scored.append((score, product["name"], product))
        scored.sort(key=lambda t: (t[0], len(t[1]), t[1]))

        return [self._public(p) for _, _, p in scored[:limit]]

    @staticmethod
    def _public(product: dict[str, str]) -> dict[str, Any]:
        return {
            "code": product["code"],
            "name": product["name"],
            "brand": None,
            "description": None,
            "price": None,
            "old_price": None,
            "base_price": None,
            "currency": "€",
            "image": None,
            "url": product["url"],
        }

    async def enrich(self, product: dict[str, Any]) -> dict[str, Any]:
        """Vul foto en naam aan vanuit de productpagina (best effort)."""
        url = product.get("url")
        code = str(product.get("code") or "")
        if not url or not url.startswith("https://www.aldi.nl/product/"):
            return product

        details = self._details.get(code)
        if details is None:
            try:
                page = await self._get_text(url)
            except AldiApiError:
                return product  # geen foto is niet erg; het product blijft bruikbaar
            details = parse_product_page(page)
            self._details[code] = details

        result = dict(product)
        if details.get("image") and not result.get("image"):
            result["image"] = details["image"]
        title = details.get("title")
        if title:
            # Titel is "MERK Productnaam"; bewaar de volledige titel als naam.
            result["name"] = title
        return result
