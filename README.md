# Lidl Boodschappen voor Home Assistant

Boodschappenlijst met producten uit de Lidl-webshop.

- Typ een zoekterm (bijv. *appels*) en kies uit alle gevonden Lidl-producten, met foto, prijs en literprijs/kiloprijs.
- Markeer per product of het **elke week** terug moet komen.
- Eigen paneel **Boodschappen** in de zijbalk (live gesynchroniseerd tussen apparaten).
- Dezelfde lijst is beschikbaar als `todo.boodschappen`, dus ook bruikbaar in dashboards, automatiseringen en via Assist.
- **Nieuwe week**: afgevinkte eenmalige producten verdwijnen, terugkerende producten staan weer op "te halen". Dit gebeurt automatisch op een dag/tijd naar keuze, of via de knop/service.

## Installatie via HACS

1. Zet deze map in een eigen GitHub-repository (zie hieronder).
2. HACS → ⋮ → **Aangepaste repositories** → voeg de repo-URL toe, categorie **Integratie**.
3. Download **Lidl Boodschappen** en herstart Home Assistant.
4. Instellingen → Apparaten & services → **Integratie toevoegen** → *Lidl Boodschappen*.

### Updates uitbrengen

Pas de code aan, commit en push, en maak daarna een tag:

```bash
git tag v0.1.1
git push origin v0.1.1
```

De workflow `release.yml` zet de versie in `manifest.json` gelijk aan de tag en maakt een GitHub-release. HACS laat dat daarna als update zien.

## Services

| Service | Doel |
| --- | --- |
| `lidl_boodschappen.new_week` | Nieuwe week starten (zie hierboven) |
| `lidl_boodschappen.add_item` | Product toevoegen (`name`, `quantity`, `recurring`) |

Voorbeeld automatisering: elke zaterdag om 06:00 een melding sturen met de lijst `todo.boodschappen`.

## Belangrijk om te weten

- De integratie gebruikt de **niet-officiële zoek-endpoint van de Lidl-site** (`/q/api/search`). Lidl heeft hier geen publieke API-belofte voor; als de site verandert, kan zoeken stoppen met werken. Zoekresultaten worden 10 minuten in het geheugen gecachet om het aantal verzoeken laag te houden.
- Lidl.nl heeft in `robots.txt` automatisch ophalen beperkt. Gebruik dit voor persoonlijk gebruik, met het lage aantal verzoeken dat een handmatig zoekveld oplevert.
- Lidl verkoopt online niet het hele winkelassortiment; verse producten als appels staan er niet altijd tussen. Wat je niet vindt, kun je als losse tekst toevoegen.
- Als zoeken een fout geeft: zet logging aan met `custom_components.lidl_boodschappen: debug` in `logger:`. Het ruwe antwoord van Lidl staat dan in het log, zodat de parser in `api.py` aangepast kan worden.
