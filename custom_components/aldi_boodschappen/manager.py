"""Beheert de boodschappenlijst en slaat die op."""

from __future__ import annotations

import uuid
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import SIGNAL_UPDATED, STORAGE_KEY, STORAGE_VERSION

PRODUCT_FIELDS = (
    "code",
    "brand",
    "description",
    "price",
    "price_valid_until",
    "old_price",
    "base_price",
    "currency",
    "image",
    "url",
    "store",
    "store_name",
)


class ShoppingManager:
    """Lijst met items. Elk item is een dict."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.items: list[dict[str, Any]] = []

    async def async_load(self) -> None:
        data = await self._store.async_load()
        self.items = (data or {}).get("items", [])

    def _changed(self) -> None:
        self._store.async_delay_save(lambda: {"items": self.items}, 1)
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)

    def get(self, item_id: str) -> dict[str, Any] | None:
        return next((i for i in self.items if i["id"] == item_id), None)

    def add(
        self,
        name: str,
        product: dict[str, Any] | None = None,
        quantity: int = 1,
        recurring: bool = False,
    ) -> dict[str, Any]:
        """Voeg een item toe. Hetzelfde product (zelfde winkel en code) wordt samengevoegd."""
        code = product.get("code") if product else None
        if code:
            existing = next((i for i in self.items if i.get("code") == code), None)
            if existing:
                if existing["checked"]:
                    existing["checked"] = False
                    existing["quantity"] = quantity
                else:
                    existing["quantity"] += quantity
                existing["recurring"] = existing["recurring"] or recurring
                self._changed()
                return existing

        item: dict[str, Any] = {
            "id": uuid.uuid4().hex,
            "name": name.strip(),
            "quantity": max(1, int(quantity)),
            "checked": False,
            "recurring": bool(recurring),
        }
        if product:
            item["name"] = product.get("name") or item["name"]
            for field in PRODUCT_FIELDS:
                item[field] = product.get(field)
        self.items.append(item)
        self._changed()
        return item

    def update(self, item_id: str, **changes: Any) -> dict[str, Any] | None:
        item = self.get(item_id)
        if not item:
            return None
        for key in ("name", "checked", "recurring"):
            if key in changes and changes[key] is not None:
                item[key] = changes[key]
        if changes.get("quantity") is not None:
            item["quantity"] = max(1, int(changes["quantity"]))
        self._changed()
        return item

    def remove(self, item_id: str) -> bool:
        before = len(self.items)
        self.items = [i for i in self.items if i["id"] != item_id]
        if len(self.items) != before:
            self._changed()
            return True
        return False

    def update_prices(self, updates: dict[str, dict[str, Any]]) -> int:
        """Werk prijzen bij op basis van productcode. Geeft het aantal wijzigingen."""
        changed = 0
        for item in self.items:
            new = updates.get(item.get("code") or "")
            if not new:
                continue
            for field in ("price", "price_valid_until"):
                if field in new and item.get(field) != new[field]:
                    item[field] = new[field]
                    changed += 1
        if changed:
            self._changed()
        return changed

    def backfill_images(self, image_for) -> int:
        """Geef bestaande items zonder foto er een, als `image_for(item)` die kan bepalen."""
        changed = 0
        for item in self.items:
            if item.get("image") or not item.get("url"):
                continue
            image = image_for(item)
            if image:
                item["image"] = image
                changed += 1
        if changed:
            self._changed()
        return changed

    def new_week(self) -> None:
        """Nieuwe week: afgevinkte eenmalige items weg, terugkerende weer 'te halen'."""
        self.items = [
            i for i in self.items if not (i["checked"] and not i["recurring"])
        ]
        for item in self.items:
            if item["recurring"]:
                item["checked"] = False
        self._changed()
