"""Constanten voor Aldi Boodschappen."""

from __future__ import annotations

DOMAIN = "aldi_boodschappen"

CONF_RESET_ENABLED = "reset_enabled"
CONF_RESET_WEEKDAY = "reset_weekday"
CONF_RESET_HOUR = "reset_hour"

DEFAULT_RESET_ENABLED = True
DEFAULT_RESET_WEEKDAY = "sat"
DEFAULT_RESET_HOUR = 6

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Aldi publiceert de productpagina's in deze sitemap (robots.txt staat dat toe).
SITEMAP_URL = "https://www.aldi.nl/sitemaps/.aldi-nord-sitemap-products.xml"
USER_AGENT = "HomeAssistant-AldiBoodschappen/0.2 (persoonlijk gebruik)"
CATALOG_MAX_AGE = 7 * 24 * 3600  # catalogus hooguit één keer per week verversen

STORAGE_KEY = f"{DOMAIN}.items"
CATALOG_STORAGE_KEY = f"{DOMAIN}.catalog"
STORAGE_VERSION = 1

SIGNAL_UPDATED = f"{DOMAIN}_updated"

PANEL_URL = "aldi-boodschappen"
PANEL_TITLE = "Boodschappen"
PANEL_ICON = "mdi:cart"
STATIC_URL = "/aldi_boodschappen_static"

SEARCH_LIMIT = 48
