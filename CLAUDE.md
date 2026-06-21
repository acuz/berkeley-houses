# CLAUDE.md — Berkeley House Search

A private two-person web app for tracking Berkeley rentals.
Repurposed from a triathlon-coaching app; ignore any stale academic references.

## Architecture

- **App:** single-file `berkeley-houses.html` (vanilla JS, no build). Firebase
  compat SDK + Leaflet, both from CDN.
- **Deployed copy:** `docs/index.html` (GitHub Pages serves `/docs` on `main`).
  Keep it in sync: `cp berkeley-houses.html docs/index.html`.
- **Backend:** Firebase project `berkeley-houses` — Auth (email/password) +
  Firestore. Both users are equal (no roles).
- **Data model:**
  - `houses/{id}` — title, url, source, address, neighborhood, rent, beds,
    baths, sqft, availableDate, leaseTerm, parking, laundry, pets, photo,
    status, ratings{uid:stars}, pros, cons, notes, lat, lng, timestamps.
  - `houses/{id}/interactions/{id}` — type, date, withWhom, summary, followUpDate.
- **Map:** Leaflet + OpenStreetMap; geocoding via Nominatim (no key).

## Conventions

- After editing `berkeley-houses.html`, copy it to `docs/index.html` before commit.
- Status values: interested, contacted, tourScheduled, toured, applied,
  accepted, rejected, dropped (see `STATUSES` in the HTML).
- Firebase **web config** is public-safe (in the HTML). The **service-account
  key** (`*-firebase-adminsdk-*.json`) is git-ignored — never commit it.

## Commands

```bash
# Local preview
python -m http.server 8000 --directory docs   # open http://localhost:8000/

# Add a listing to Firestore (also used by the /add-listing skill)
python scripts/add_listing.py --json '{"title":"...","url":"...","address":"..."}'
python scripts/add_listing.py --file listing.json   # Windows-friendly

# Backup Firestore -> JSON
python scripts/backup_houses.py
```

## Skill

`/add-listing <url>` — scrape a rental listing and write it to Firestore.
Scraping is blocked by Zillow/Apartments.com; Craigslist/HotPads/property
sites work. See `.claude/skills/add-listing/SKILL.md`.
