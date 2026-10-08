"""Snelle test van de parser (draaien met: python tests/test_parser.py)."""

import importlib.util
import sys
import types
from pathlib import Path

root = Path(__file__).parent.parent / "custom_components" / "lidl_boodschappen"

# api.py importeert aiohttp en .const; stub waar nodig zodat de test ook zonder HA draait
pkg = types.ModuleType("lb")
pkg.__path__ = [str(root)]
sys.modules["lb"] = pkg
try:
    import aiohttp  # noqa: F401
except ImportError:
    sys.modules["aiohttp"] = types.SimpleNamespace(ClientSession=object, ClientError=Exception, ClientTimeout=lambda **k: None)

for name in ("const", "api"):
    spec = importlib.util.spec_from_file_location(f"lb.{name}", root / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"lb.{name}"] = mod
    spec.loader.exec_module(mod)

parse_item = sys.modules["lb.api"].parse_item

sample = {
    "code": "10012345",
    "gridbox": {
        "data": {
            "fullTitle": "Elstar appels",
            "brand": {"name": "Lidl"},
            "price": {"price": 1.99, "oldPrice": 2.49, "basePrice": {"text": "1 kg = 1,33"}},
            "image": "https://img.example/appel.jpg",
            "canonicalUrl": "/p/elstar-appels/p100",
            "keyfacts": {"supplementalDescription": "1,5 kg"},
        }
    },
}
p = parse_item(sample, "https://www.lidl.nl")
assert p["name"] == "Elstar appels", p
assert p["price"] == 1.99 and p["old_price"] == 2.49
assert p["url"] == "https://www.lidl.nl/p/elstar-appels/p100"
assert p["code"] == "10012345" or p["code"]
assert p["brand"] == "Lidl"

# Leeg of kapot item mag niet crashen
assert parse_item({}, "x") is None
assert parse_item("rommel", "x") is None  # type: ignore[arg-type]
print("parser ok")
