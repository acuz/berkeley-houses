# 🏡 Berkeley House Search

A private, two-person web app for tracking and comparing Berkeley rentals —
house details, an interaction log (calls/emails/tours), a map of every address,
a status pipeline, and per-partner ratings.

**Live app:** https://acuz.github.io/berkeley-houses/
*(sign-in required — accounts are created in the Firebase console)*

## Stack

- **Single-file app** — [`berkeley-houses.html`](berkeley-houses.html) (deployed copy: [`docs/index.html`](docs/index.html)). Vanilla JS, no build step.
- **Firebase** — Auth (email/password) + Firestore. Data model:
  - `houses/{id}` — address, rent, beds/baths/sqft, status, ratings, lat/lng, photo, listing URL…
  - `houses/{id}/interactions/{id}` — email / call / video tour / visit / question, with date + follow-up.
- **Map** — Leaflet + OpenStreetMap; addresses geocoded via Nominatim (no API key).

## Add a listing from a URL

- **In the app:** paste the listing URL in the Add-house form and click **⤓ Fetch** — it pulls the photo, title, and any structured data. Works best on Craigslist / HotPads / property sites; Zillow & Apartments.com block scraping.
  - Optional reliable proxy: deploy [`worker/listing-proxy.js`](worker/listing-proxy.js) (free Cloudflare Worker) and set `PROXY_URL` in the app.
- **Via Claude:** run the `/add-listing <url>` skill — it scrapes server-side and writes to Firestore via [`scripts/add_listing.py`](scripts/add_listing.py) (auto-geocodes). Runs locally or in the cloud against this repo.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/add_listing.py` | Write a house entry to Firestore (used by the skill). |
| `scripts/backup_houses.py` | Export `houses` + interactions to JSON. |

A GitHub Action ([`.github/workflows/daily-backup.yml`](.github/workflows/daily-backup.yml)) backs up Firestore nightly to the `backups` branch — set the `GOOGLE_SERVICE_ACCOUNT` repo secret to enable it.

## Local dev

```bash
python -m http.server 8000 --directory docs
# open http://localhost:8000/
```

## Setup notes

- Firebase **web config** lives in the HTML (public-safe — security is enforced by Auth + Firestore rules).
- The **service-account key** (`*-firebase-adminsdk-*.json`) is git-ignored — never commit it. For CI, store it as the `GOOGLE_SERVICE_ACCOUNT` secret.
