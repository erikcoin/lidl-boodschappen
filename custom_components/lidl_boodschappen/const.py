"""Constanten voor Lidl Boodschappen."""

from __future__ import annotations

DOMAIN = "lidl_boodschappen"

CONF_COUNTRY = "country"
CONF_USER_AGENT = "user_agent"
CONF_RESET_ENABLED = "reset_enabled"
CONF_RESET_WEEKDAY = "reset_weekday"
CONF_RESET_HOUR = "reset_hour"

DEFAULT_COUNTRY = "NL"
# Lidl's WAF (Myra) weigert onbekende User-Agents maar laat curl door.
# Instelbaar in de opties, voor het geval Lidl dit aanpast.
DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
DEFAULT_RESET_ENABLED = True
DEFAULT_RESET_WEEKDAY = "sat"
DEFAULT_RESET_HOUR = 6

# Land -> (basis-URL, locale, assortment)
COUNTRIES: dict[str, tuple[str, str, str]] = {
    "NL": ("https://www.lidl.nl", "nl_NL", "NL"),
    "BE": ("https://www.lidl.be", "nl_BE", "BE"),
    "DE": ("https://www.lidl.de", "de_DE", "DE"),
}

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

STORAGE_KEY = f"{DOMAIN}.items"
STORAGE_VERSION = 1

SIGNAL_UPDATED = f"{DOMAIN}_updated"

PANEL_URL = "lidl-boodschappen"
PANEL_TITLE = "Boodschappen"
PANEL_ICON = "mdi:cart"
STATIC_URL = "/lidl_boodschappen_static"

SEARCH_LIMIT = 36
SEARCH_CACHE_SECONDS = 600
