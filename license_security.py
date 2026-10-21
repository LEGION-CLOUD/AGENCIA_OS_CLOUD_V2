"""Security helpers for agency license keys.

This module stores fingerprints, never the plaintext values, of license keys
that were exposed in the repository's public history.
"""
import hashlib
import math
import secrets
from datetime import datetime, timedelta


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
        if record.get("active", True) and is_exposed_license_key(key)
    }


def generate_license_key(year=None):
    """Generate a high-entropy key that is safe to normalize to uppercase."""
    year = int(year or datetime.now().year)
    return f"LEGION-{year}-{secrets.token_hex(24).upper()}"


def _positive_integer(value, label, *, maximum=None):
    """Parse a positive integer without silently truncating decimals or booleans."""
    if isinstance(value, bool):
        raise ValueError(f"{label} debe ser un entero mayor que cero.")
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{label} debe ser un entero mayor que cero.") from None
    if not math.isfinite(numeric) or not numeric.is_integer() or numeric < 1:
        raise ValueError(f"{label} debe ser un entero mayor que cero.")
    if maximum is not None and numeric > maximum:
        raise ValueError(f"{label} supera el máximo permitido ({maximum}).")
    return int(numeric)


def create_license_record(
    client,
    days,
    max_accounts,
    *,
    existing_keys=(),
    key_factory=None,
    now=None,
):
    """Build validated license metadata and a unique secure key without persisting it."""
    normalized_client = str(client or "").strip()
    if not normalized_client:
        raise ValueError("Ingresá el nombre del cliente antes de crear la licencia.")
    duration_days = _positive_integer(days, "La duración", maximum=36500)
    account_limit = _positive_integer(
        max_accounts,
        "El máximo de cuentas",
        maximum=2147483647,
    )

    factory = key_factory or generate_license_key
    reserved = {str(key).strip().upper() for key in (existing_keys or [])}
    new_key = None
    for _ in range(5):
        candidate = str(factory()).strip().upper()
        if candidate and candidate not in reserved:
            new_key = candidate
            break
    if new_key is None:
        raise RuntimeError("No se pudo generar una clave nueva y única.")

    created_at = now or datetime.now()
    if not isinstance(created_at, datetime):
        raise ValueError("La fecha de creación de la licencia no es válida.")
    try:
        expires_at = created_at + timedelta(days=duration_days)
    except OverflowError:
        raise ValueError("La duración de la licencia supera el rango de fechas permitido.") from None

    record = {
        "client": normalized_client,
        "created": created_at.isoformat(),
        "expires": expires_at.isoformat(),
        "max_accounts": account_limit,
        "active": True,
    }
    return new_key, record


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
