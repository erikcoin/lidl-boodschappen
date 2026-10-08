"""Config flow en opties."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_COUNTRY,
    CONF_RESET_ENABLED,
    CONF_RESET_HOUR,
    CONF_RESET_WEEKDAY,
    CONF_USER_AGENT,
    COUNTRIES,
    DEFAULT_COUNTRY,
    DEFAULT_RESET_ENABLED,
    DEFAULT_RESET_HOUR,
    DEFAULT_RESET_WEEKDAY,
    DEFAULT_USER_AGENT,
    DOMAIN,
    WEEKDAYS,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_COUNTRY, default=defaults.get(CONF_COUNTRY, DEFAULT_COUNTRY)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(COUNTRIES), translation_key="country"
                )
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
            vol.Required(
                CONF_USER_AGENT,
                default=defaults.get(CONF_USER_AGENT, DEFAULT_USER_AGENT),
            ): selector.TextSelector(),
        }
    )


class LidlBoodschappenConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            user_input[CONF_RESET_HOUR] = int(user_input[CONF_RESET_HOUR])
            return self.async_create_entry(title="Lidl Boodschappen", data=user_input)

        return self.async_show_form(step_id="user", data_schema=_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return LidlBoodschappenOptionsFlow()


class LidlBoodschappenOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            user_input[CONF_RESET_HOUR] = int(user_input[CONF_RESET_HOUR])
            return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(current))
