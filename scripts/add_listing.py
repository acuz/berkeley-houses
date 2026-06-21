"""
Add a Berkeley house listing to Firestore (the `houses` collection).

Write-side of the `add-listing` skill. Works with EITHER backend:

  A) Service account (local / admin) — full access, bypasses rules.
     --key PATH | GOOGLE_SERVICE_ACCOUNT env (JSON content) |
     GOOGLE_APPLICATION_CREDENTIALS | auto-detected *berkeley-houses*adminsdk*.json
  B) Writer login (cloud / least-privilege) — signs in as a normal user and
     writes via the Firestore REST API, constrained by the security rules.
     Set FIREBASE_EMAIL + FIREBASE_PASSWORD (and optionally FIREBASE_API_KEY).

A service account, if present, takes precedence; otherwise the writer login is
used. Geocoding (Nominatim) is best-effort and non-fatal — a blocked network
just means no map pin until the address is re-geocoded later.

Usage:
  python scripts/add_listing.py --json '{"title":"...","url":"...","address":"..."}'
  python scripts/add_listing.py --file listing.json
  echo '{...}' | python scripts/add_listing.py

Requires: firebase-admin (only for the service-account backend).
"""

import argparse
import datetime
import glob
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PROJECT_ID = os.environ.get("FIREBASE_PROJECT", "berkeley-houses")
DEFAULT_WEB_API_KEY = "AIzaSyAM8OsVE69mk-7QcghltnAlpEZX0ole9tY"  # public web key

FIELDS = {
    "title": "", "url": "", "source": "", "address": "", "neighborhood": "",
    "unit": "", "videoUrl": "",
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


# ---------- shared helpers ----------
def source_from_url(url):
    if not url:
        return ""
    host = urllib.parse.urlparse(url).netloc.replace("www.", "")
    for domain, name in KNOWN_SOURCES.items():
        if host.endswith(domain):
            return name
    return host


def coerce_number(val):
    if val in ("", None):
        return None
    s = str(val).replace(",", "")
    return float(s) if "." in s else int(float(s))


BANCROFT = (37.8722756, -122.2588768)  # Bancroft Library, UC Berkeley


def geocode(address):
    q = address if "Berkeley" in address else address + ", Berkeley, CA"
    # Photon first — reachable from cloud envs where Nominatim is blocked.
    try:
        url = ("https://photon.komoot.io/api/?limit=1&lat=37.87&lon=-122.27&q="
               + urllib.parse.quote(q))
        req = urllib.request.Request(url, headers={"User-Agent": "berkeley-houses/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            feats = (json.load(r).get("features") or [])
        if feats:
            lon, lat = feats[0]["geometry"]["coordinates"][:2]
            return float(lat), float(lon)
    except Exception as e:  # noqa: BLE001
        print(f"  photon geocode skipped: {e}", file=sys.stderr)
    # Nominatim fallback.
    try:
        url = ("https://nominatim.openstreetmap.org/search?format=json&limit=1&q="
               + urllib.parse.quote(q))
        req = urllib.request.Request(url, headers={"User-Agent": "berkeley-houses/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            arr = json.load(r)
        if arr:
            return float(arr[0]["lat"]), float(arr[0]["lon"])
    except Exception as e:  # noqa: BLE001
        print(f"  nominatim geocode skipped: {e}", file=sys.stderr)
    return None, None


def travel_minutes(lat, lng, costing):
    try:
        body = json.dumps({
            "locations": [{"lat": lat, "lon": lng},
                          {"lat": BANCROFT[0], "lon": BANCROFT[1]}],
            "costing": costing,
        }).encode()
        req = urllib.request.Request("https://valhalla1.openstreetmap.de/route",
                                     data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            t = json.load(r).get("trip", {}).get("summary", {}).get("time")
        return round(t / 60) if t else None
    except Exception as e:  # noqa: BLE001
        print(f"  route ({costing}) skipped: {e}", file=sys.stderr)
        return None


def http_json(url, body=None, headers=None, method="POST"):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:  # noqa: BLE001
            return e.code, {"error": e.read().decode(errors="replace")[:300]}


# ---------- backend A: service account ----------
def try_service_account(key_arg):
    if key_arg:
        return key_arg, "key"
    if os.environ.get("GOOGLE_SERVICE_ACCOUNT"):
        return os.environ["GOOGLE_SERVICE_ACCOUNT"], "env"
    gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if gac and os.path.exists(gac):
        return gac, "key"
    matches = glob.glob("*berkeley-houses*adminsdk*.json")
    if matches:
        return matches[0], "key"
    return None, None


def write_admin(cred_src, kind, doc, created_by):
    import firebase_admin
    from firebase_admin import credentials, firestore
    cred = (credentials.Certificate(json.loads(cred_src)) if kind == "env"
            else credentials.Certificate(cred_src))
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    doc = dict(doc)
    doc["createdAt"] = firestore.SERVER_TIMESTAMP
    doc["updatedAt"] = firestore.SERVER_TIMESTAMP
    doc["createdBy"] = created_by
    return db.collection("houses").add(doc)[1].id


# ---------- backend B: writer login (REST) ----------
def to_value(v):
    if v is None:
        return {"nullValue": None}
    if isinstance(v, bool):
        return {"booleanValue": v}
    if isinstance(v, int):
        return {"integerValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, str):
        return {"stringValue": v}
    if isinstance(v, dict):
        return {"mapValue": {"fields": {k: to_value(x) for k, x in v.items()}}}
    if isinstance(v, list):
        return {"arrayValue": {"values": [to_value(x) for x in v]}}
    return {"stringValue": str(v)}


def write_rest(doc, created_by):
    api_key = os.environ.get("FIREBASE_API_KEY", DEFAULT_WEB_API_KEY)
    email, pw = os.environ["FIREBASE_EMAIL"], os.environ["FIREBASE_PASSWORD"]

    code, res = http_json(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
        {"email": email, "password": pw, "returnSecureToken": True})
    if code != 200:
        raise SystemExit(f"Sign-in failed: {res.get('error', {}).get('message', res)}")
    token = res["idToken"]

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    fields = {k: to_value(v) for k, v in doc.items()}
    fields["createdAt"] = {"timestampValue": now}
    fields["updatedAt"] = {"timestampValue": now}
    fields["createdBy"] = {"stringValue": created_by}

    url = (f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}"
           f"/databases/(default)/documents/houses?key={api_key}")
    code, res = http_json(url, {"fields": fields}, {"Authorization": "Bearer " + token})
    if code != 200:
        raise SystemExit(f"Firestore write failed (HTTP {code}): "
                         f"{res.get('error', {}).get('status') or res}")
    return res["name"].rsplit("/", 1)[-1]


# ---------- main ----------
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
        sys.exit("No input. Provide --json '{...}', --file PATH, or pipe JSON via stdin.")
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
    if lat is not None and lng is not None:
        wm = travel_minutes(lat, lng, "pedestrian")
        bm = travel_minutes(lat, lng, "bicycle")
        if wm is not None:
            doc["walkMin"] = wm
        if bm is not None:
            doc["bikeMin"] = bm
    doc["ratings"] = incoming.get("ratings", {})
    created_by = incoming.get("createdBy", "add-listing-skill")

    cred_src, kind = try_service_account(args.key)
    if cred_src:
        doc_id = write_admin(cred_src, kind, doc, created_by)
        backend = "service account"
    elif os.environ.get("FIREBASE_EMAIL") and os.environ.get("FIREBASE_PASSWORD"):
        doc_id = write_rest(doc, created_by)
        backend = "writer login"
    else:
        sys.exit("No credentials. Locally: place the service account JSON in the repo "
                 "root. In the cloud: set FIREBASE_EMAIL + FIREBASE_PASSWORD secrets.")

    print(f"Added house {doc_id}: {doc['title'] or doc['address']} (via {backend})")
    print(f"  geocoded -> {lat}, {lng}" if lat else
          "  (no coordinates - add a clearer address for the map pin)")


if __name__ == "__main__":
    main()
