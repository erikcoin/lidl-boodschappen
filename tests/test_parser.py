"""Test van het verwerken van het Aldi-zoekantwoord (python tests/test_parser.py)."""

import importlib.util
import sys
import types
from pathlib import Path

root = Path(__file__).parent.parent / "custom_components" / "aldi_boodschappen"

pkg = types.ModuleType("ab")
pkg.__path__ = [str(root)]
sys.modules["ab"] = pkg
try:
    import aiohttp  # noqa: F401
except ImportError:
    sys.modules["aiohttp"] = types.SimpleNamespace(
        ClientSession=object, ClientError=Exception, ClientTimeout=lambda **k: None
    )

for name in ("const", "api"):
    spec = importlib.util.spec_from_file_location(f"ab.{name}", root / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"ab.{name}"] = mod
    spec.loader.exec_module(mod)

api = sys.modules["ab.api"]

# Hit uit het echte antwoord van aldi.nl (zoeken op "Pink lady"), plus twee varianten
pink_lady = {
    "objectID": "1204033",
    "isAvailable": True,
    "brandName": "PINK LADY",
    "categoryIDs": ["fruit"],
    "assets": [
        {"type": "gallery", "url": "https://s7g10.scene7.com/is/image/aldinord/variant_1204033_1"},
        {"type": "primary", "url": "https://s7g10.scene7.com/is/image/aldinord/product_1204033_main_cms_20_nl_nl_appels_cw01_2024"},
    ],
    "salesUnit": "6 stuks",
    "productReferences": [{"type": "KVArticleNumber", "value": "0004555"}],
    "name": "Appels",
    "currentPrice": {"priceValue": 2.99, "validFrom": 1791151200, "validUntil": 1792706399},
    "shortDescription": "Pink Lady appels bij ALDI: knapperige en zoete smaak.",
    "productSlug": "appels-1204033",
    "mainCategoryID": "fruit",
}
unavailable = {"name": "Elstar appels", "isAvailable": False, "productSlug": "elstar-1", "objectID": "1"}
no_brand_no_price = {"name": "Volle kwark", "productSlug": "volle-kwark-91244809", "brandName": "Almhof"}

payload = {"results": [{"hits": [unavailable, pink_lady, no_brand_no_price, pink_lady, {"x": 1}, "rommel"]}]}
products = api.parse_response(payload)

# dubbele hit en kapotte hits verdwijnen; beschikbare producten staan voorop
assert [p["code"] for p in products] == ["1204033", "volle-kwark-91244809", "1"], products

p = products[0]
assert p["name"] == "Appels Pink Lady", p["name"]
assert p["description"] == "6 stuks"
assert p["price"] == 2.99
assert p["price_valid_until"] == 1792706399
assert p["image"].endswith("appels_cw01_2024"), "primaire foto gaat voor galerij"
assert p["url"] == "https://www.aldi.nl/product/appels-1204033.html"

assert products[1]["name"] == "Volle kwark Almhof"  # merk met kleine letters blijft zoals het is
assert products[1]["price"] is None and products[1]["image"] is None
assert products[2]["available"] is False

# Onverwachte antwoorden geven een nette fout in plaats van een crash
for bad in ({}, {"results": []}, {"results": [{}]}, [], None):
    try:
        api.parse_response(bad)
    except api.AldiApiError:
        pass
    else:
        raise AssertionError(f"verwachtte AldiApiError voor {bad!r}")


# ---- manager: prijzen bijwerken (HA-modules worden hier nagebootst) ----
for mod in ("homeassistant", "homeassistant.core", "homeassistant.helpers",
            "homeassistant.helpers.dispatcher", "homeassistant.helpers.storage"):
    sys.modules[mod] = types.ModuleType(mod)
sys.modules["homeassistant.core"].HomeAssistant = object
sys.modules["homeassistant.helpers.dispatcher"].async_dispatcher_send = lambda *a, **k: None


class FakeStore:
    def __init__(self, *a, **k): pass
    def async_delay_save(self, *a, **k): pass


sys.modules["homeassistant.helpers.storage"].Store = FakeStore
spec = importlib.util.spec_from_file_location("ab.manager", root / "manager.py")
manager_mod = importlib.util.module_from_spec(spec)
sys.modules["ab.manager"] = manager_mod
spec.loader.exec_module(manager_mod)

m = manager_mod.ShoppingManager(hass=None)
a = m.add("Appels Pink Lady", products[0], quantity=2, recurring=True)
b = m.add("Melk")  # losse tekst, geen code
assert a["price"] == 2.99 and a["price_valid_until"] == 1792706399 and b.get("price") is None

n = m.update_prices({"1204033": {"price": 3.49, "price_valid_until": 1793000000}, "onbekend": {"price": 9.99}})
assert n == 2, n
assert m.get(a["id"])["price"] == 3.49 and m.get(a["id"])["price_valid_until"] == 1793000000
assert m.get(b["id"]).get("price") is None  # losse tekst blijft ongemoeid
assert m.update_prices({"1204033": {"price": 3.49, "price_valid_until": 1793000000}}) == 0  # niets nieuws

# totaal zoals het paneel dat rekent: prijs x aantal, alleen producten die nog gehaald moeten worden
m.update(a["id"], quantity=3)
total = sum(i["price"] * i["quantity"] for i in m.items if not i["checked"] and i.get("price") is not None)
assert round(total, 2) == 10.47, total

# bestaande items zonder foto krijgen er een als die afleidbaar is; bestaande foto's blijven
m2 = manager_mod.ShoppingManager(hass=None)
m2.items = [
    {"id": "1", "name": "a", "url": "https://hoogvliet.nl/product/x-726992000", "image": None, "store": "hoogvliet"},
    {"id": "2", "name": "b", "url": "https://hoogvliet.nl/product/y-111111111", "image": "https://al.eens/foto.jpg", "store": "hoogvliet"},
    {"id": "3", "name": "c", "url": "https://www.aldi.nl/product/z-1.html", "image": None, "store": "aldi"},
    {"id": "4", "name": "d", "image": None},
]
n = m2.backfill_images(lambda i: "IMG:" + i["id"] if i.get("store") == "hoogvliet" else None)
assert n == 1 and m2.items[0]["image"] == "IMG:1" and m2.items[1]["image"] == "https://al.eens/foto.jpg"
assert m2.items[2]["image"] is None and m2.items[3]["image"] is None
assert m2.backfill_images(lambda i: None) == 0

# ontbrekende link en foto aanvullen via productcode; bestaande waarden blijven
m3 = manager_mod.ShoppingManager(hass=None)
m3.items = [
    {"id": "1", "code": "a|1", "url": None, "image": None},
    {"id": "2", "code": "b|1", "url": "oud", "image": None},
    {"id": "3", "code": "zzz", "url": None, "image": None},
]
n = m3.backfill_missing({"a|1": {"url": "U", "image": "I"}, "b|1": {"url": "nieuw", "image": "J"}})
assert n == 3 and m3.items[0]["url"] == "U" and m3.items[1]["url"] == "oud" and m3.items[1]["image"] == "J"
assert m3.items[2]["url"] is None

print("ok:", len(products), "producten uit antwoord verwerkt, prijzen en totaal kloppen")
