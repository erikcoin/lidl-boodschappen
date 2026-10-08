"""Todo-entiteit zodat de lijst ook in HA-dashboards en automatiseringen werkt."""

from __future__ import annotations

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_UPDATED
from .manager import ShoppingManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    manager: ShoppingManager = hass.data[DOMAIN]["runtime"]["manager"]
    async_add_entities([LidlShoppingList(entry, manager)])


class LidlShoppingList(TodoListEntity):
    _attr_has_entity_name = True
    _attr_name = "Boodschappen"
    _attr_icon = "mdi:cart"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, entry: ConfigEntry, manager: ShoppingManager) -> None:
        self._manager = manager
        self._attr_unique_id = f"{entry.entry_id}_list"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self._refresh)
        )
        self._refresh()

    @callback
    def _refresh(self) -> None:
        items = []
        for item in self._manager.items:
            name = item["name"]
            if item.get("quantity", 1) > 1:
                name = f"{item['quantity']}x {name}"
            description_parts = []
            if item.get("recurring"):
                description_parts.append("🔁 Wekelijks terugkerend")
            if item.get("price") is not None:
                description_parts.append(f"€ {item['price']:.2f}")
            items.append(
                TodoItem(
                    uid=item["id"],
                    summary=name,
                    status=TodoItemStatus.COMPLETED
                    if item["checked"]
                    else TodoItemStatus.NEEDS_ACTION,
                    description=" · ".join(description_parts) or None,
                )
            )
        self._attr_todo_items = items
        self.async_write_ha_state()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        self._manager.add(item.summary or "")

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if item.uid is None:
            return
        changes = {"checked": item.status == TodoItemStatus.COMPLETED}
        existing = self._manager.get(item.uid)
        # Naam alleen overnemen als die niet door ons "2x ..." is aangepast
        if existing and item.summary and item.summary != self._display_name(existing):
            changes["name"] = item.summary
        self._manager.update(item.uid, **changes)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            self._manager.remove(uid)

    @staticmethod
    def _display_name(item: dict) -> str:
        if item.get("quantity", 1) > 1:
            return f"{item['quantity']}x {item['name']}"
        return item["name"]
