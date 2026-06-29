---
name: add-listing
description: Scrape a rental listing URL and add it to the Berkeley house-search app (Firestore). Use when given a rental/listing link to import.
argument-hint: "<listing URL>"
allowed-tools: ["WebFetch", "Bash", "Read"]
---

# Add a rental listing to the Berkeley house app

Given a rental listing URL, extract its details and write a new entry to the
`houses` collection in Firestore (project `berkeley-houses`). The entry then
shows up automatically in [berkeley-houses.html](../../berkeley-houses.html)
and on the map.

The URL is in `$ARGUMENTS`. If empty, ask the user for the listing link.

## Steps

1. **Fetch the listing.** Use `WebFetch` on the URL with a prompt like:
   > "Extract this rental listing as data: title/headline, full street address,
   > neighborhood, monthly rent (number), bedrooms, bathrooms, square footage,
   > available date (YYYY-MM-DD), lease term, parking, laundry, pet policy, the
   > main listing photo URL (og:image), and a 1-2 sentence summary."

   If WebFetch is blocked or returns little (Zillow/Apartments.com often block
   bots), tell the user and ask them to paste the key details, or to use the
   in-app **⤓ Fetch** button instead.

2. **Map to the house schema.** Build a JSON object using only these keys
   (omit unknowns — don't invent values):

   | key | type | notes |
   |-----|------|-------|
   | `title` | string | short label, e.g. "2BR on Shattuck Ave" |
   | `url` | string | the listing URL (always include) |
   | `address` | string | full street address (drives the map pin) |
   | `neighborhood` | string | |
   | `rent` | number | $/month, digits only |
   | `beds` / `baths` | number | |
   | `sqft` | number | |
   | `availableDate` | string | `YYYY-MM-DD` |
   | `leaseTerm` | string | e.g. "12 mo" |
   | `parking` | string | None / Street / Driveway / Garage |
   | `laundry` | string | In-unit / Shared / None |
   | `pets` | string | OK / Cats only / No |
   | `photo` | string | main image URL (og:image) — this is the card preview |
   | `notes` | string | the summary + anything notable |
   | `status` | string | default `interested` |

   Always include `url`; always include `address` if known (no address = no map pin).

3. **Write to Firestore.** Pass the JSON to the writer script (it geocodes the
   address and stamps timestamps automatically):

   ```bash
   python scripts/add_listing.py --json '{"title":"...","url":"...","address":"...","rent":3200,"beds":2,"baths":1,"photo":"https://...","status":"interested"}'
   ```

   On Windows PowerShell, do NOT pipe via stdin (PowerShell sends empty/garbled
   stdin to python). Instead, write the JSON to a temp file with the Write tool
   and pass `--file` (the script strips a UTF-8 BOM automatically):
   ```powershell
   python scripts/add_listing.py --file <path-to-temp.json>
   ```

4. **Report** the new house id and address the script prints, and remind the
   user it's now visible in the app.

## Reading the listing

`WebFetch` works for Craigslist / HotPads / property sites but is blocked
(HTTP 403) by Zillow & Apartments.com. In a cloud session, prefer your own
browsing to read those; if that's also blocked, ask the user to paste the
listing text — then map it to the schema the same way.

## Credentials (two backends, auto-selected)

- **Local (service account):** the script auto-detects
  `*berkeley-houses*adminsdk*.json` in the repo root (or `GOOGLE_SERVICE_ACCOUNT`
  env with the JSON content). Requires `pip install firebase-admin`.
- **Cloud (writer login):** when no service account is present, the script signs
  in as a normal user via the Firestore REST API using `FIREBASE_EMAIL` +
  `FIREBASE_PASSWORD` env vars (writer account, constrained by security rules).
  No admin key needed; nothing to commit. This is the no-PC path.

Geocoding is best-effort — if the network blocks Nominatim, the write still
succeeds (just no map pin until the address is re-geocoded).
