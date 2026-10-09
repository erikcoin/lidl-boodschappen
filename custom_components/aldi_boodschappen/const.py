"""Constanten voor Aldi Boodschappen."""

from __future__ import annotations

DOMAIN = "aldi_boodschappen"

CONF_APP_ID = "app_id"
CONF_API_KEY = "api_key"
CONF_RESET_ENABLED = "reset_enabled"
CONF_RESET_WEEKDAY = "reset_weekday"
CONF_RESET_HOUR = "reset_hour"

# Application ID is geen geheim (het staat in elke zoek-URL van aldi.nl); de
# API-sleutel vul je zelf in bij het instellen.
DEFAULT_APP_ID = "2HU29PF6BH"
ALGOLIA_INDEX = "an_prd_nl_nl_products2"
PRODUCT_BASE_URL = "https://www.aldi.nl/product"
USER_AGENT = "HomeAssistant-AldiBoodschappen/0.3 (persoonlijk gebruik)"

DEFAULT_RESET_ENABLED = True
DEFAULT_RESET_WEEKDAY = "sat"
DEFAULT_RESET_HOUR = 6

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

STORAGE_KEY = f"{DOMAIN}.items"
STORAGE_VERSION = 1

SIGNAL_UPDATED = f"{DOMAIN}_updated"

PANEL_URL = "aldi-boodschappen"
PANEL_TITLE = "Boodschappen"
PANEL_ICON = "mdi:cart"
STATIC_URL = "/aldi_boodschappen_static"

SEARCH_LIMIT = 48
SEARCH_CACHE_SECONDS = 600
