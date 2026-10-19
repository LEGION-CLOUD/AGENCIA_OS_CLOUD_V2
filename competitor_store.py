"""Persistencia por licencia para las observaciones del Espía de Agencia OS."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import uuid
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

import requests


TABLE_NAME = "agencia_os_competitor_observations"
PLATFORMS = ("Meta", "Google", "TikTok", "Otra")
OBSERVATION_FIELDS = (
    "id",
    "brand",
    "platform",
    "source_url",
    "observed_on",
    "creative_format",
    "headline",
    "text",
    "proposition",
    "offer",
    "call_to_action",
    "destination",
    "notes",
)
FIELD_LIMITS = {
    "id": 100,
    "brand": 200,
    "platform": 40,
    "source_url": 2048,
    "observed_on": 10,
    "creative_format": 120,
    "headline": 500,
    "text": 5000,
    "proposition": 1000,
    "offer": 1000,
    "call_to_action": 300,
    "destination": 2048,
    "notes": 2000,
}
_URL_CONTROL_CHARS = re.compile(r"[\\x00-\\x20\\x7f]")


class CompetitorStoreError(RuntimeError):
    """Error de persistencia del Espía sin exponer secretos de servidor."""


def tenant_id_for_license(license_info):
    """Stable ID compatible with the local prototype: SHA-256(client, created)."""
    if not isinstance(license_info, dict):
        raise ValueError("No se pudo identificar la licencia del Espía.")

    client = str(license_info.get("client") or "").strip()
    created = str(license_info.get("created") or "").strip()
    if not client or not created:
        raise ValueError(
            "La licencia no contiene los datos estables necesarios "
            "para separar las observaciones."
        )

    identity = json.dumps(
        {"client": client, "created": created},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _validate_tenant_id(tenant_id):
    if (
        not isinstance(tenant_id, str)
        or len(tenant_id) != 64
        or any(character not in "0123456789abcdef" for character in tenant_id)
    ):
        raise ValueError("El identificador del espacio de trabajo no es válido.")


def _text(value, field, *, required=False):
    if value is None:
        result = ""
    elif isinstance(value, str):
        result = value.strip()
    else:
        result = str(value).strip()

    limit = FIELD_LIMITS[field]
    if len(result) > limit:
        raise ValueError(f"El campo {field} supera el máximo de {limit} caracteres.")
    if required and not result:
        raise ValueError(f"Completá el campo {field}.")
    return result


def _validate_public_url(value):
    value = _text(value, "source_url")
    if not value:
        return ""
    if _URL_CONTROL_CHARS.search(value):
        raise ValueError("La URL pública contiene caracteres no permitidos.")

    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.netloc
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError
        if hostname.lower() == "localhost" or hostname.lower().endswith(
            (".localhost", ".local")
        ):
            raise ValueError
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError
        _ = parsed.port
    except ValueError:
        raise ValueError(
            "Usá una URL pública HTTP o HTTPS, sin credenciales ni direcciones locales."
        ) from None
    return value


def create_observation(values):
    """Validate and normalize one observation before keeping or persisting it."""
    if not isinstance(values, dict):
        raise ValueError("La observación debe ser un objeto.")

    record = {
        "id": _text(values.get("id"), "id") or str(uuid.uuid4()),
        "brand": _text(values.get("brand"), "brand", required=True),
        "platform": _text(values.get("platform"), "platform", required=True),
        "source_url": _validate_public_url(values.get("source_url")),
        "observed_on": _text(
            values.get("observed_on") or date.today().isoformat(), "observed_on"
        ),
        "creative_format": _text(values.get("creative_format"), "creative_format"),
        "headline": _text(values.get("headline"), "headline"),
        "text": _text(values.get("text"), "text"),
        "proposition": _text(values.get("proposition"), "proposition"),
        "offer": _text(values.get("offer"), "offer"),
        "call_to_action": _text(values.get("call_to_action"), "call_to_action"),
        "destination": _text(values.get("destination"), "destination"),
        "notes": _text(values.get("notes"), "notes"),
    }

    if record["platform"] not in PLATFORMS:
        raise ValueError("Elegí una plataforma válida: Meta, Google, TikTok u Otra.")
    try:
        date.fromisoformat(record["observed_on"])
    except ValueError:
        raise ValueError("La fecha debe tener formato AAAA-MM-DD.") from None

    return record


def export_observations_json(observations):
    if not isinstance(observations, list):
        raise ValueError("La lista de observaciones no es válida.")
    normalized = [create_observation(item) for item in observations]
    return json.dumps(normalized, ensure_ascii=False, indent=2)


def _table_url(supabase_url):
    base = str(supabase_url or "").strip().rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.hostname:
        raise CompetitorStoreError(
            "La URL de Supabase no está configurada correctamente en el servidor."
        )
    return f"{base}/rest/v1/{TABLE_NAME}"


def _headers(secret_key, *, upsert=False):
    key = str(secret_key or "").strip()
    if not key:
        raise CompetitorStoreError(
            "Falta SUPABASE_SECRET_KEY en la configuración del servidor."
        )
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept-Profile": "public",
        "Content-Profile": "public",
    }
    if upsert:
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
    return headers


def _friendly_request_error(action, exc):
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status:
        return f"Supabase rechazó la operación de {action} (HTTP {status})."
    return (
        f"No se pudo completar la operación de {action} por un error de conexión "
        f"({type(exc).__name__})."
    )


def load_observations(supabase_url, secret_key, tenant_id, *, http=requests):
    _validate_tenant_id(tenant_id)
    url = _table_url(supabase_url)
    headers = _headers(secret_key)

    try:
        response = http.get(
            url,
            headers=headers,
            params={
                "select": "tenant_id,observations",
                "tenant_id": f"eq.{tenant_id}",
                "limit": "1",
            },
            timeout=20,
        )
        response.raise_for_status()
        rows = response.json()
    except Exception as exc:
        raise CompetitorStoreError(_friendly_request_error("lectura", exc)) from exc

    if not isinstance(rows, list):
        raise CompetitorStoreError("Supabase devolvió un formato inesperado.")
    if not rows:
        return []

    observations = rows[0].get("observations", [])
    if not isinstance(observations, list):
        raise CompetitorStoreError("El archivo de observaciones guardado tiene un formato inválido.")
    try:
        return [create_observation(item) for item in observations]
    except (TypeError, ValueError) as exc:
        raise CompetitorStoreError(
            f"Hay una observación guardada con formato inválido ({type(exc).__name__})."
        ) from exc


def save_observations(
    supabase_url, secret_key, tenant_id, observations, *, http=requests
):
    _validate_tenant_id(tenant_id)
    url = _table_url(supabase_url)
    headers = _headers(secret_key, upsert=True)

    if not isinstance(observations, list):
        raise ValueError("La lista de observaciones no es válida.")
    normalized = [create_observation(item) for item in observations]

    payload = {
        "tenant_id": tenant_id,
        "observations": normalized,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        response = http.post(
            url,
            headers=headers,
            params={"on_conflict": "tenant_id"},
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
    except Exception as exc:
        raise CompetitorStoreError(_friendly_request_error("guardado", exc)) from exc
