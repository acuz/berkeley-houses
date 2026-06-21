"""
Add a Berkeley house listing to Firestore (the `houses` collection).

This is the write-side of the `add-listing` Claude skill: Claude scrapes a
listing URL, maps the result to the house schema, then calls this script to
persist it. Geocodes the address (Nominatim) so the map pin appears.

Usage:
  python scripts/add_listing.py --json '{"title":"2BR Shattuck","url":"...","address":"2120 Shattuck Ave, Berkeley, CA","rent":3200,"beds":2,"baths":1}'
  echo '{...}' | python scripts/add_listing.py

Credentials (first match wins):
  --key PATH                          path to a service account JSON
  GOOGLE_SERVICE_ACCOUNT env          service account JSON *content*
  GOOGLE_APPLICATION_CREDENTIALS env  path to a service account JSON
  ./*berkeley-houses*adminsdk*.json   auto-detected in the repo root

Requires: pip install firebase-admin
"""

import argparse
import glob
import json
import os
import sys
import urllib.parse
import urllib.request

import firebase_admin
from firebase_admin import credentials, firestore

# Schema fields with defaults (mirrors berkeley-houses.html).
FIELDS = {
    "title": "", "url": "", "source": "", "address": "", "neighborhood": "",
    "rent": None, "beds": None, "baths": None, "sqft": None,
    "availableDate": "", "leaseTerm": "", "parking": "", "laundry": "", "pets": "",
    "photo": "", "status": "interested", "pros": "", "cons": "", "notes": "",
}
NUMERIC = ("rent", "beds", "baths", "sqft")

KNOWN_SOURCES = {
    "zillow.com": "Zillow", "craigslist.org": "Craigslist",
    "apartments.com": "Apartments.com", "trulia.com": "Trulia",
    "redfin.com": "Redfin", "facebook.com": "Facebook",
    "hotpads.com": "HotPads", "padmapper.com": "PadMapper",
}


def get_credentials(key_arg):
    if key_arg:
        return credentials.Certificate(key_arg)
    content = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
    if content:
        return credentials.Certificate(json.loads(content))
    gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if gac and os.path.exists(gac):
        return credentials.Certificate(gac)
    matches = glob.glob("*berkeley-houses*adminsdk*.json")
    if matches:
        return credentials.Certificate(matches[0])
    sys.exit("No credentials. Pass --key PATH, set GOOGLE_SERVICE_ACCOUNT, "
             "or place the service account JSON in the repo root.")


def source_from_url(url):
    if not url:
        return ""
    host = urllib.parse.urlparse(url).netloc.replace("www.", "")
    for domain, name in KNOWN_SOURCES.items():
        if host.endswith(domain):
            return name
    return host


def geocode(address):
    try:
        q = address if "Berkeley" in address else address + ", Berkeley, CA"
        url = ("https://nominatim.openstreetmap.org/search?format=json&limit=1&q="
               + urllib.parse.quote(q))
        req = urllib.request.Request(url, headers={"User-Agent": "berkeley-houses/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            arr = json.load(r)
        if arr:
            return float(arr[0]["lat"]), float(arr[0]["lon"])
    except Exception as e:  # noqa: BLE001
        print(f"  geocode failed: {e}", file=sys.stderr)
    return None, None


def coerce_number(val):
    if val in ("", None):
        return None
    s = str(val).replace(",", "")
    return float(s) if "." in s else int(float(s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="House fields as a JSON object")
    ap.add_argument("--file", help="Path to a file containing the JSON object")
    ap.add_argument("--key", help="Path to service account JSON")
    args = ap.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8-sig") as f:
            raw = f.read()
    else:
        raw = args.json or sys.stdin.read()
    if not raw.strip():
        sys.exit("No input. Provide --json '{...}' or pipe JSON via stdin.")
    incoming = json.loads(raw)

    doc = {k: incoming.get(k, v) for k, v in FIELDS.items()}
    for f in NUMERIC:
        doc[f] = coerce_number(doc[f])
    if not doc["source"]:
        doc["source"] = source_from_url(doc["url"])
    if not doc["title"] and not doc["address"]:
        sys.exit("Need at least 'title' or 'address'.")

    lat, lng = incoming.get("lat"), incoming.get("lng")
    if (lat is None or lng is None) and doc["address"]:
        lat, lng = geocode(doc["address"])
    doc["lat"], doc["lng"] = lat, lng
    doc["ratings"] = incoming.get("ratings", {})

    cred = get_credentials(args.key)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    doc["createdAt"] = firestore.SERVER_TIMESTAMP
    doc["updatedAt"] = firestore.SERVER_TIMESTAMP
    doc["createdBy"] = incoming.get("createdBy", "add-listing-skill")

    ref = db.collection("houses").add(doc)[1]
    print(f"Added house {ref.id}: {doc['title'] or doc['address']}")
    if lat:
        print(f"  geocoded -> {lat}, {lng}")
    else:
        print("  (no coordinates - add a clearer address for the map pin)")


if __name__ == "__main__":
    main()
