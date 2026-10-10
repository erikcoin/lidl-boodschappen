"""Tests voor eenheidsprijzen, Hoogvliet (Checkjebon) en het samenvoegen van winkels.

Draaien met: python tests/test_stores.py

LET OP: het Checkjebon-voorbeeld hieronder is NIET echt. De vorm (lijst winkels met
n/d en producten met n/p/s/l) is een aanname op basis van de projectbeschrijving.
De test bewijst dat de verwerking klopt voor die vorm, niet dat het echte bestand
zo is opgebouwd.
"""

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

root = Path(__file__).parent.parent / "custom_components" / "aldi_boodschappen"

pkg = types.ModuleType("ab2")
pkg.__path__ = [str(root)]
sys.modules["ab2"] = pkg
try:
    import aiohttp  # noqa: F401
except ImportError:
    sys.modules["aiohttp"] = types.SimpleNamespace(
        ClientSession=object, ClientError=Exception, ClientTimeout=lambda **k: None
    )

for name in ("const", "api", "pricing", "hoogvliet", "search"):
    spec = importlib.util.spec_from_file_location(f"ab2.{name}", root / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"ab2.{name}"] = mod
    spec.loader.exec_module(mod)

api = sys.modules["ab2.api"]
pricing = sys.modules["ab2.pricing"]
hoogvliet = sys.modules["ab2.hoogvliet"]
search = sys.modules["ab2.search"]

# ---------------------------------------------------------------- eenheden
ps = pricing.parse_size
assert ps("6 stuks") == (6.0, "stuk")
assert ps("500 g") == (0.5, "kg")
assert ps("1,5 l") == (1.5, "l")
assert ps("75 cl") == (0.75, "l")
assert ps("330 ml") == (0.33, "l")
assert ps("2 x 250 g") == (0.5, "kg")
assert ps("6 × 330 ml") == (1.98, "l") or abs(ps("6 × 330 ml")[0] - 1.98) < 1e-9
assert ps("ca. 1 kg") == (1.0, "kg")
assert ps("per stuk") is None and ps("4 pack") is None and ps(None) is None and ps("") is None
assert ps("0 g") is None

# ---------------------------------------------------------------- eenheidsprijs + goedkoopst
def p(code, price, size, store="aldi", available=True):
    return {"code": code, "price": price, "description": size, "available": available, "store": store}

products = [
    p("a1", 2.99, "6 stuks", "aldi"),        # 0,4983 per stuk
    p("h1", 2.49, "4 stuks", "hoogvliet"),   # 0,6225 per stuk
    p("a2", 1.49, "500 g", "aldi"),          # 2,98 per kg
    p("h2", 2.99, "1 kg", "hoogvliet"),      # 2,99 per kg  -> iets duurder dan a2
    p("a3", 3.00, "1 l", "aldi"),            # enige per liter: geen vergelijking mogelijk
    p("h3", 1.00, "per stuk", "hoogvliet"),  # geen te lezen hoeveelheid
    p("a4", None, "500 g", "aldi"),          # geen prijs
    p("a5", 0.10, "100 stuks", "aldi", available=False),  # niet beschikbaar: doet niet mee
]
pricing.annotate_unit_prices(products)
pricing.mark_cheapest(products)
by = {x["code"]: x for x in products}
assert by["a1"]["unit_label"] == "per stuk" and abs(by["a1"]["unit_price"] - 0.4983) < 1e-4
assert by["a2"]["unit_label"] == "per kg" and by["a2"]["unit_price"] == 2.98
assert by["h3"]["unit_price"] is None and by["a4"]["unit_price"] is None
assert by["a1"]["cheapest"] and not by["h1"]["cheapest"], "per stuk: a1 is goedkoper"
assert by["a2"]["cheapest"] and not by["h2"]["cheapest"], "per kg: a2 is goedkoper"
assert not by["a3"]["cheapest"], "één product per eenheid: niets om mee te vergelijken"
assert not by["a5"]["cheapest"], "niet-beschikbare producten tellen niet mee"

# ---------------------------------------------------------------- Checkjebon-verwerking (aangenomen vorm)
sample = [
    {"n": "Albert Heijn", "d": [{"n": "Melk", "p": 1.0, "s": "1 l", "l": "/ah/melk"}]},
    {
        "n": "Hoogvliet",
        "d": [
            {"n": "Pink Lady appels", "p": 2.49, "s": "4 stuks", "l": "/product/pink-lady-1"},
            {"n": "Volle kwark", "p": 1.19, "s": "500 g", "l": "https://www.hoogvliet.com/product/volle-kwark-2"},
            {"n": "Magere kwark vanille", "p": 1.29, "s": "500 g"},
            {"n": "Kwarkbollen", "p": 1.99, "s": "6 stuks", "l": "/product/kwarkbollen-3"},
            {"n": "Volle kwark", "p": 1.19, "s": "500 g", "l": "https://www.hoogvliet.com/product/volle-kwark-2"},  # dubbel
            {"n": "Gratis ding", "p": 0, "s": "1 stuk"},        # prijs 0: overslaan
            {"n": "Kapot", "p": "veel", "s": "1 stuk"},         # prijs geen getal: overslaan
            {"p": 1.0},                                          # geen naam: overslaan
            "rommel",
        ],
    },
]
parsed = hoogvliet.parse_checkjebon(json.dumps(sample))
assert [x["name"] for x in parsed] == ["Pink Lady appels", "Volle kwark", "Magere kwark vanille", "Kwarkbollen"], parsed
assert parsed[0]["url"] == "https://www.hoogvliet.com/product/pink-lady-1", "relatieve link krijgt het domein"
assert parsed[2]["url"] is None
assert parsed[0]["code"].startswith("hoogvliet:")

# andere vormen en fouten geven een nette fout, geen crash
for bad in ("{niet json", json.dumps({"x": 1}), json.dumps([{"n": "Jumbo", "d": []}]),
            json.dumps([{"n": "Hoogvliet", "d": []}]), json.dumps("tekst")):
    try:
        hoogvliet.parse_checkjebon(bad)
    except api.AldiApiError:
        pass
    else:
        raise AssertionError(f"verwachtte fout voor {bad!r}")
# varianten van de sleutels worden ook herkend
alt = json.dumps({"supermarkets": [{"name": "Hoogvliet", "products": [{"name": "Melk", "price": 1.1, "size": "1 l"}]}]})
assert hoogvliet.parse_checkjebon(alt)[0]["name"] == "Melk"

# ---------------------------------------------------------------- zoeken in Hoogvliet
client = hoogvliet.HoogvlietClient(session=None)
client._products = parsed
client._fetched_at = 10**12
client._loaded = True
client._kick_refresh = lambda: None


def hv(q):
    return [x["name"] for x in asyncio.run(client.search(q))]


assert hv("kwark") == ["Volle kwark", "Magere kwark vanille", "Kwarkbollen"], hv("kwark")
assert hv("PINK lady") == ["Pink Lady appels"]
assert hv("volle kwark") == ["Volle kwark"] and hv("x") == [] and hv("bestaatniet") == []
res = asyncio.run(client.search("pink"))[0]
assert res["store"] == "hoogvliet" and res["store_name"] == "Hoogvliet" and res["price"] == 2.49
assert res["description"] == "4 stuks" and res["image"] is None

empty = hoogvliet.HoogvlietClient(session=None)
empty._loaded = True
empty._kick_refresh = lambda: None
try:
    asyncio.run(empty.search("kwark"))
except hoogvliet.HoogvlietError as err:
    assert "opgehaald" in str(err)
else:
    raise AssertionError("zonder data moet er een duidelijke fout komen")


# ---------------------------------------------------------------- winkels samenvoegen
class Fake:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    async def search(self, query, limit=48):
        self.calls.append((query, limit))
        if self.error:
            raise self.error
        return [dict(x) for x in self.result]


def mk(code, price, size, store):
    return {"code": code, "name": code, "price": price, "description": size, "available": True,
            "store": store, "store_name": store.title()}


aldi_items = [mk("a1", 2.99, "6 stuks", "aldi"), mk("a2", 1.49, "500 g", "aldi"), mk("a3", 9.0, "1 l", "aldi")]
hv_items = [mk("h1", 2.49, "4 stuks", "hoogvliet"), mk("h2", 2.99, "1 kg", "hoogvliet")]
svc = search.SearchService({"aldi": Fake(aldi_items), "hoogvliet": Fake(hv_items)})

merged, warnings = asyncio.run(svc.search("x1", limit=48))
assert warnings == []
assert [m["code"] for m in merged] == ["a1", "h1", "a2", "h2", "a3"], "om en om, op relevantie"
flags = {m["code"]: m["cheapest"] for m in merged}
assert flags == {"a1": True, "h1": False, "a2": True, "h2": False, "a3": False}, flags
assert len(asyncio.run(svc.search("x1", limit=3))[0]) == 3, "limiet geldt voor het totaal"

# één winkel valt uit: de andere resultaten blijven, met een waarschuwing
svc = search.SearchService({"aldi": Fake(error=api.AldiApiError("sleutel geweigerd")), "hoogvliet": Fake(hv_items)})
merged, warnings = asyncio.run(svc.search("x1"))
assert [m["code"] for m in merged] == ["h1", "h2"]
assert warnings == ["Aldi: sleutel geweigerd"], warnings

# alle winkels vallen uit: duidelijke fout in plaats van "niets gevonden"
svc = search.SearchService({"aldi": Fake(error=api.AldiApiError("a stuk")), "hoogvliet": Fake(error=api.AldiApiError("h stuk"))})
try:
    asyncio.run(svc.search("x1"))
except api.AldiApiError as err:
    assert "a stuk" in str(err) and "h stuk" in str(err)
else:
    raise AssertionError("verwachtte een fout als alles faalt")

# een onverwachte fout in één winkel breekt het zoeken ook niet af
svc = search.SearchService({"aldi": Fake(error=RuntimeError("boem")), "hoogvliet": Fake(hv_items)})
merged, warnings = asyncio.run(svc.search("x1"))
assert len(merged) == 2 and warnings == ["Aldi: onverwachte fout"], warnings

# lookup (prijzen bijwerken) kapt niet af en geeft alles van alle winkels
svc = search.SearchService({"aldi": Fake(aldi_items), "hoogvliet": Fake(hv_items)})
assert {x["code"] for x in asyncio.run(svc.lookup("x1"))} == {"a1", "a2", "a3", "h1", "h2"}

print("ok: eenheden, goedkoopst, Checkjebon-verwerking, zoeken en samenvoegen kloppen")
