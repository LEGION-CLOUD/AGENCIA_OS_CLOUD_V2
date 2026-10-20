"""Security helpers for agency license keys.

This module stores fingerprints, never the plaintext values, of license keys
that were exposed in the repository's public history.
"""
import hashlib
import secrets
from datetime import datetime


EXPOSED_LICENSE_FINGERPRINTS = frozenset({
    "84336bf0245daeaedfb465515e099ec3ca1123d939db2e3f00d594ac00eb01a9",
    "8566acb4ce3b3d64d3ca2a9092b81ee4bb1c482af34bf3647960f6cb89762336",
})


def license_key_fingerprint(key):
    """Return a stable SHA-256 fingerprint for a normalized license key."""
    normalized = str(key or "").strip().upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_exposed_license_key(key):
    """Return True when a key matches a value found in public Git history."""
    return license_key_fingerprint(key) in EXPOSED_LICENSE_FINGERPRINTS


def find_exposed_license_keys(licenses):
    """Return current license records whose plaintext key was publicly exposed."""
    return {
        key: record
        for key, record in (licenses or {}).items()
        if is_exposed_license_key(key)
    }


def generate_license_key(year=None):
    """Generate a high-entropy key that is safe to normalize to uppercase."""
    year = int(year or datetime.now().year)
    return f"LEGION-{year}-{secrets.token_hex(24).upper()}"


def build_license_rotation_plan(licenses, key_factory=generate_license_key):
    """Prepare replacement keys while retaining license metadata.

    The caller persists the returned mapping in one database request. Old keys
    are disabled in the same write; new keys retain the client's existing
    expiry and account limit. This function does not persist or print secrets.
    """
    updated = {key: dict(record) for key, record in (licenses or {}).items()}
    exposed = find_exposed_license_keys(updated)
    replacements = []
    reserved = set(updated)

    for old_key, old_record in exposed.items():
        new_key = None
        for _ in range(5):
            candidate = str(key_factory()).strip().upper()
            if candidate and candidate not in reserved:
                new_key = candidate
                break
        if new_key is None:
            raise RuntimeError("No se pudo generar una clave nueva y única.")

        reserved.add(new_key)
        updated[old_key]["active"] = False
        new_record = dict(old_record)
        new_record["active"] = True
        updated[new_key] = new_record
        replacements.append({
            "client": new_record.get("client", ""),
            "license_key": new_key,
            "expires": new_record.get("expires"),
            "max_accounts": new_record.get("max_accounts"),
        })

    return updated, replacements
