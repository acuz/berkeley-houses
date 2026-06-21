"""
Firestore -> JSON backup for the Berkeley house app.
Exports the `houses` collection plus each house's `interactions` sub-collection.

Env vars:
  GOOGLE_SERVICE_ACCOUNT  - content of the service account JSON key (for CI)
  BACKUP_PATH             - output file path (default: houses-backup.json)

Or run locally: it auto-detects *berkeley-houses*adminsdk*.json in the repo root.
Requires: pip install firebase-admin
"""

import glob
import json
import os

import firebase_admin
from firebase_admin import credentials, firestore


def get_credentials():
    content = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
    if content:
        return credentials.Certificate(json.loads(content))
    matches = glob.glob("*berkeley-houses*adminsdk*.json")
    if matches:
        return credentials.Certificate(matches[0])
    raise SystemExit("No credentials: set GOOGLE_SERVICE_ACCOUNT or place the "
                     "service account JSON in the repo root.")


def export_all(db):
    backup = {}
    for house in db.collection("houses").stream():
        data = house.to_dict()
        data["interactions"] = {
            i.id: i.to_dict()
            for i in db.collection("houses").document(house.id)
                       .collection("interactions").stream()
        }
        backup[house.id] = data
    return backup


def main():
    out_path = os.environ.get("BACKUP_PATH", "houses-backup.json")
    cred = get_credentials()
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    print("Exporting houses...")
    backup = export_all(db)
    n_int = sum(len(v.get("interactions", {})) for v in backup.values())
    print(f"  {len(backup)} houses, {n_int} interactions")

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(backup, f, indent=2, default=str)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
