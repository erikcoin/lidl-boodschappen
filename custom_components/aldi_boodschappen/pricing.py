"""Eenheidsprijzen, zodat producten uit verschillende winkels vergelijkbaar zijn.

'6 stuks' voor 2,99 en '500 g' voor 1,49 zeggen op zich niets over welke
goedkoper is. Daarom rekenen we om naar een prijs per kg, per liter of per stuk.
"""

from __future__ import annotations

import re
from typing import Any

_UNIT_RE = re.compile(
    r"(?:(\d+)\s*[x×]\s*)?"  # optioneel: '6 x ' of '2×'
    r"(\d+(?:[.,]\d+)?)\s*"  # hoeveelheid
    r"(kg|kilo|gram|gr|g|ml|cl|dl|ltr|liter|l|stuks|stuk|stk|st)"  # eenheid
    r"(?![a-z])"
)

# eenheid -> (basiseenheid, factor naar die basis)
_FACTORS: dict[str, tuple[str, float]] = {
    "kg": ("kg", 1.0),
    "kilo": ("kg", 1.0),
    "g": ("kg", 0.001),
    "gr": ("kg", 0.001),
    "gram": ("kg", 0.001),
    "l": ("l", 1.0),
    "ltr": ("l", 1.0),
    "liter": ("l", 1.0),
    "dl": ("l", 0.1),
    "cl": ("l", 0.01),
    "ml": ("l", 0.001),
    "stuk": ("stuk", 1.0),
    "stuks": ("stuk", 1.0),
    "stk": ("stuk", 1.0),
    "st": ("stuk", 1.0),
}

UNIT_LABELS = {"kg": "per kg", "l": "per liter", "stuk": "per stuk"}


def parse_size(text: Any) -> tuple[float, str] | None:
    """'2 x 250 g' -> (0.5, 'kg'); '6 stuks' -> (6.0, 'stuk'); anders None."""
    if not isinstance(text, str):
        return None
    match = _UNIT_RE.search(text.lower())
    if not match:
        return None
    multiplier, number, unit = match.groups()
    try:
        value = float(number.replace(",", "."))
    except ValueError:
        return None
    base, factor = _FACTORS[unit]
    quantity = value * factor * (int(multiplier) if multiplier else 1)
    if quantity <= 0:
        return None
    return quantity, base


def annotate_unit_prices(products: list[dict[str, Any]]) -> None:
    """Zet unit_price en unit_label op elk product (None als het niet kan)."""
    for product in products:
        product["unit_price"] = None
        product["unit_label"] = None
        price = product.get("price")
        size = parse_size(product.get("description"))
        if price is None or size is None:
            continue
        quantity, base = size
        product["unit_price"] = round(price / quantity, 4)
        product["unit_label"] = UNIT_LABELS[base]


def mark_cheapest(products: list[dict[str, Any]]) -> None:
    """Markeer per eenheid (kg/liter/stuk) het product met de laagste eenheidsprijs.

    Alleen als er minstens twee producten te vergelijken zijn; niet-beschikbare
    producten doen niet mee.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for product in products:
        product["cheapest"] = False
        if product.get("unit_price") is None or product.get("available") is False:
            continue
        groups.setdefault(product["unit_label"], []).append(product)
    for members in groups.values():
        if len(members) < 2:
            continue
        lowest = min(p["unit_price"] for p in members)
        for p in members:
            if p["unit_price"] == lowest:
                p["cheapest"] = True
