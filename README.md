# Aldi Boodschappen voor Home Assistant

Boodschappenlijst met producten uit het Aldi-assortiment (aldi.nl).

- Typ een zoekterm (bijv. *kwark*) en kies uit alle gevonden Aldi-producten.
- Markeer per product of het **elke week** terug moet komen.
- Eigen paneel **Boodschappen** in de zijbalk (live gesynchroniseerd tussen apparaten).
- Dezelfde lijst is beschikbaar als `todo.boodschappen`, dus ook bruikbaar in dashboards, automatiseringen en via Assist.
- **Nieuwe week**: afgevinkte eenmalige producten verdwijnen, terugkerende producten staan weer op "te halen". Dit gebeurt automatisch op een dag/tijd naar keuze, of via de knop/service.

> Dit is een onofficiële integratie en staat los van Aldi.

## Hoe het zoeken werkt

Aldi heeft geen zoek-API. aldi.nl publiceert wel een sitemap met alle productpagina's, en `robots.txt` staat het ophalen daarvan toe. De integratie:

1. haalt die sitemap op (één verzoek) en bewaart de productlijst lokaal; daarna hooguit één keer per week opnieuw;
2. zoekt zelf in die lijst terwijl je typt, dus het zoekveld doet **geen** verzoeken naar Aldi;
3. haalt pas bij **Toevoegen** de ene productpagina op voor de foto en de merknaam (best effort).

Beperkingen:

- **Geen prijzen.** Aldi toont die niet op de productpagina's.
- De zoeknaam komt uit de URL van de productpagina (bijv. *Volle kwark*). Na het toevoegen wordt dit de volledige titel inclusief merk, als die opgehaald kon worden.
- Een product staat er alleen in als Aldi de pagina in de sitemap zet. Wat je niet vindt, voeg je toe als losse tekst.
- De sitemap en pagina-indeling zijn niet gegarandeerd stabiel. Gaat er iets mis, zet dan logging aan (`custom_components.aldi_boodschappen: debug` onder `logger:`).

## Installatie via HACS

1. Zet deze map in een eigen GitHub-repository en vervang `JOUW_GEBRUIKERSNAAM` in `manifest.json`.
2. HACS → ⋮ → **Aangepaste repositories** → voeg de repo-URL toe, categorie **Integratie**.
3. Download **Aldi Boodschappen** en herstart Home Assistant.
4. Instellingen → Apparaten & services → **Integratie toevoegen** → *Aldi Boodschappen*.

Had je eerder de Lidl-versie (`lidl_boodschappen`) geïnstalleerd? Verwijder die integratie en de map in HACS eerst; dit is een aparte integratie met een andere naam.

### Updates uitbrengen

```bash
git tag v0.2.1
git push origin v0.2.1
```

De workflow `release.yml` zet de versie in `manifest.json` gelijk aan de tag en maakt een GitHub-release. HACS laat dat daarna als update zien.

## Services

| Service | Doel |
| --- | --- |
| `aldi_boodschappen.new_week` | Nieuwe week starten (zie hierboven) |
| `aldi_boodschappen.add_item` | Product toevoegen (`name`, `quantity`, `recurring`) |
