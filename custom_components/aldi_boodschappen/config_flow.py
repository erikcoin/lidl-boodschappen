"""Config flow en opties."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AldiApiError, AldiAuthError, AldiClient
from .const import (
    CONF_API_KEY,
    CONF_APP_ID,
    CONF_RESET_ENABLED,
    CONF_RESET_HOUR,
    CONF_RESET_WEEKDAY,
    DEFAULT_APP_ID,
    DEFAULT_RESET_ENABLED,
    DEFAULT_RESET_HOUR,
    DEFAULT_RESET_WEEKDAY,
    DOMAIN,
    WEEKDAYS,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_APP_ID, default=defaults.get(CONF_APP_ID, DEFAULT_APP_ID)
            ): selector.TextSelector(),
            vol.Required(
                CONF_API_KEY, default=defaults.get(CONF_API_KEY, "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Required(
                CONF_RESET_ENABLED,
                default=defaults.get(CONF_RESET_ENABLED, DEFAULT_RESET_ENABLED),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_RESET_WEEKDAY,
                default=defaults.get(CONF_RESET_WEEKDAY, DEFAULT_RESET_WEEKDAY),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=WEEKDAYS, translation_key="weekday"
                )
            ),
            vol.Required(
                CONF_RESET_HOUR,
                default=defaults.get(CONF_RESET_HOUR, DEFAULT_RESET_HOUR),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=23, step=1, mode="box")
            ),
        }
    )


async def _validate(hass, user_input: dict[str, Any]) -> dict[str, str]:
    """Doe een proefzoekopdracht; geeft een foutcode terug of een lege dict."""
    client = AldiClient(
        async_get_clientsession(hass),
        user_input[CONF_APP_ID],
        user_input[CONF_API_KEY],
    )
    try:
        await client.search("appels", limit=1)
    except AldiAuthError:
        return {"base": "invalid_auth"}
    except AldiApiError:
        return {"base": "cannot_connect"}
    return {}


class AldiBoodschappenConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_RESET_HOUR] = int(user_input[CONF_RESET_HOUR])
            errors = await _validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    title="Aldi Boodschappen", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return AldiBoodschappenOptionsFlow()


class AldiBoodschappenOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_RESET_HOUR] = int(user_input[CONF_RESET_HOUR])
            errors = await _validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(data=user_input)

        current = user_input or {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=_schema(current), errors=errors
        )
