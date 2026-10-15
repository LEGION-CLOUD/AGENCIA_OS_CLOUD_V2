import base64
import binascii
import hmac
import json
import re
import secrets as secrets_module
import time
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode, urlparse

import requests
import pandas as pd


API_VERSION = "v26"
GOOGLE_ADS_SCOPE = "https://www.googleapis.com/auth/adwords"
OAUTH_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_ADS_ENDPOINT = "https://googleads.googleapis.com"
OAUTH_STATE_TTL_SECONDS = 600
OAUTH_CALLBACK_QUERY_KEYS = (
    "code",
    "state",
    "error",
    "error_description",
    "scope",
    "authuser",
    "prompt",
    "iss",
)
_OAUTH_NONCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
_OAUTH_SIGNATURE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
_LICENSE_FINGERPRINT_PATTERN = re.compile(r"^[a-f0-9]{64}$")

GOOGLE_CAMPAIGN_COLUMNS = [
    "Canal",
    "Campaign",
    "Status",
    "Date",
    "Spend",
    "Impressions",
    "Clicks",
    "CTR",
    "CPC",
    "Conversions",
    "Revenue",
    "ROAS",
]


class GoogleAdsError(Exception):
    """A safe, user-facing Google Ads integration error."""


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str


def load_oauth_config(secrets):
    required = (
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "GOOGLE_OAUTH_REDIRECT_URI",
    )
    missing = [
        name
        for name in required
        if not isinstance(secrets.get(name), str) or not secrets.get(name).strip()
    ]
    if missing:
        names = ", ".join(missing)
        raise GoogleAdsError(
            f"Falta configuración de Google OAuth en Streamlit Secrets: {names}."
        )

    redirect_uri = secrets["GOOGLE_OAUTH_REDIRECT_URI"].strip()
    parsed_uri = urlparse(redirect_uri)
    if (
        parsed_uri.scheme != "https"
        or not parsed_uri.hostname
        or parsed_uri.username is not None
        or parsed_uri.password is not None
    ):
        raise GoogleAdsError(
            "GOOGLE_OAUTH_REDIRECT_URI debe ser una URL HTTPS válida."
        )

    return GoogleOAuthConfig(
        client_id=secrets["GOOGLE_OAUTH_CLIENT_ID"].strip(),
        client_secret=secrets["GOOGLE_OAUTH_CLIENT_SECRET"].strip(),
        redirect_uri=redirect_uri,
    )


def _derive_oauth_key(config, purpose):
    return hmac.new(
        config.client_secret.encode("utf-8"),
        b"agencia-os-cloud/google-ads/" + purpose,
        "sha256",
    ).digest()


def fingerprint_license(license_key, config):
    if not isinstance(license_key, str) or not license_key.strip():
        raise ValueError("Se necesita validar una licencia antes de conectar Google Ads.")
    normalized_key = license_key.strip().upper()
    return hmac.new(
        _derive_oauth_key(config, b"license-fingerprint"),
        normalized_key.encode("utf-8"),
        "sha256",
    ).hexdigest()


def capture_oauth_callback(query_params, session_state):
    if not any(key in query_params for key in OAUTH_CALLBACK_QUERY_KEYS):
        return False
    session_state["google_oauth_pending_callback"] = {
        "code": query_params.get("code"),
        "state": query_params.get("state"),
        "error": query_params.get("error"),
    }
    return True


def _urlsafe_encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _urlsafe_decode(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Invalid base64url value")
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if _urlsafe_encode(decoded) != value:
        raise ValueError("Non-canonical base64url value")
    return decoded


def create_oauth_state(config, license_fingerprint, *, now=None):
    if not _LICENSE_FINGERPRINT_PATTERN.fullmatch(str(license_fingerprint or "")):
        raise ValueError("No se pudo vincular OAuth con una licencia validada.")
    issued_at = int(time.time() if now is None else now)
    payload = {
        "v": 1,
        "iat": issued_at,
        "exp": issued_at + OAUTH_STATE_TTL_SECONDS,
        "nonce": secrets_module.token_urlsafe(32),
        "license": license_fingerprint,
    }
    encoded_payload = _urlsafe_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = hmac.new(
        _derive_oauth_key(config, b"state-signature"),
        encoded_payload.encode("ascii"),
        "sha256",
    ).digest()
    return f"{encoded_payload}.{_urlsafe_encode(signature)}"


def build_authorization_url(config, state):
    if not isinstance(state, str) or not state:
        raise ValueError("Falta el estado de seguridad OAuth.")
    return f"{OAUTH_AUTHORIZATION_ENDPOINT}?{urlencode({
        'client_id': config.client_id,
        'redirect_uri': config.redirect_uri,
        'response_type': 'code',
        'scope': GOOGLE_ADS_SCOPE,
        'access_type': 'offline',
        'include_granted_scopes': 'true',
        'prompt': 'consent',
        'state': state,
    })}"


def validate_oauth_state(state, config, expected_license_fingerprint, *, now=None):
    if (
        not isinstance(state, str)
        or len(state) > 2048
        or not _LICENSE_FINGERPRINT_PATTERN.fullmatch(
            str(expected_license_fingerprint or "")
        )
    ):
        return False
    parts = state.split(".")
    if len(parts) != 2 or not _OAUTH_SIGNATURE_PATTERN.fullmatch(parts[1]):
        return False
    encoded_payload, encoded_signature = parts
    try:
        signature = _urlsafe_decode(encoded_signature)
        payload_bytes = _urlsafe_decode(encoded_payload)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return False
    if not isinstance(payload, dict) or set(payload) != {
        "v",
        "iat",
        "exp",
        "nonce",
        "license",
    }:
        return False

    expected_signature = hmac.new(
        _derive_oauth_key(config, b"state-signature"),
        encoded_payload.encode("ascii"),
        "sha256",
    ).digest()
    if not hmac.compare_digest(signature, expected_signature):
        return False

    issued_at = payload.get("iat")
    expires_at = payload.get("exp")
    current_time = int(time.time() if now is None else now)
    if (
        payload.get("v") != 1
        or isinstance(payload.get("v"), bool)
        or not isinstance(issued_at, int)
        or isinstance(issued_at, bool)
        or not isinstance(expires_at, int)
        or isinstance(expires_at, bool)
        or issued_at > current_time + 60
        or expires_at <= current_time
        or expires_at <= issued_at
        or expires_at - issued_at > OAUTH_STATE_TTL_SECONDS
        or not isinstance(payload.get("nonce"), str)
        or not _OAUTH_NONCE_PATTERN.fullmatch(payload["nonce"])
        or not isinstance(payload.get("license"), str)
        or not _LICENSE_FINGERPRINT_PATTERN.fullmatch(payload["license"])
        or not hmac.compare_digest(
            payload["license"],
            expected_license_fingerprint,
        )
    ):
        return False
    return True


def complete_oauth_callback(
    code,
    state,
    config,
    expected_license_fingerprint,
    *,
    oauth_error=None,
    now=None,
    post=None,
):
    if not validate_oauth_state(
        state,
        config,
        expected_license_fingerprint,
        now=now,
    ):
        raise GoogleAdsError(
            "No se pudo validar la autorización o su vínculo con la licencia. "
            "Volvé a iniciar la conexión."
        )
    if oauth_error:
        raise GoogleAdsError(
            "Google Ads no autorizó la conexión. Podés volver a intentarlo."
        )
    return exchange_authorization_code(code, config, post=post)


def _oauth_post(post, payload):
    try:
        response = post(
            OAUTH_TOKEN_ENDPOINT,
            data=payload,
            timeout=30,
            allow_redirects=False,
        )
    except requests.RequestException:
        raise GoogleAdsError(
            "No se pudo completar la conexión OAuth con Google."
        ) from None

    if response.status_code != 200:
        raise GoogleAdsError(
            f"Google OAuth rechazó la solicitud (HTTP {response.status_code}). "
            "Revisá la configuración de OAuth y volvé a conectar la cuenta."
        )
    try:
        data = response.json()
    except (ValueError, TypeError):
        raise GoogleAdsError("Google OAuth devolvió una respuesta no válida.") from None
    if not isinstance(data, dict):
        raise GoogleAdsError("Google OAuth devolvió una respuesta no válida.")
    return data


def exchange_authorization_code(code, config, *, post=None):
    if not isinstance(code, str) or not code:
        raise GoogleAdsError("Google no devolvió un código de autorización válido.")
    post = post or requests.post
    data = _oauth_post(
        post,
        {
            "code": code,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "redirect_uri": config.redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    access_token = data.get("access_token")
    expires_in = data.get("expires_in")
    if (
        not isinstance(access_token, str)
        or not access_token
        or not isinstance(expires_in, (int, float))
        or isinstance(expires_in, bool)
        or expires_in <= 0
    ):
        raise GoogleAdsError("Google OAuth no devolvió credenciales válidas.")

    refresh_token = data.get("refresh_token")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token if isinstance(refresh_token, str) else None,
        "expires_at": time.time() + expires_in,
    }


def refresh_access_token(refresh_token, config, *, post=None):
    if not isinstance(refresh_token, str) or not refresh_token:
        raise GoogleAdsError(
            "La autorización de Google venció. Volvé a conectar la cuenta."
        )
    post = post or requests.post
    data = _oauth_post(
        post,
        {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    access_token = data.get("access_token")
    expires_in = data.get("expires_in")
    if (
        not isinstance(access_token, str)
        or not access_token
        or not isinstance(expires_in, (int, float))
        or isinstance(expires_in, bool)
        or expires_in <= 0
    ):
        raise GoogleAdsError("Google OAuth no devolvió credenciales válidas.")
    return {
        "access_token": access_token,
        "expires_at": time.time() + expires_in,
    }


def get_valid_access_token(credentials, config, *, now=None, post=None):
    access_token = credentials.get("access_token")
    expires_at = credentials.get("expires_at")
    current_time = time.time() if now is None else now
    if (
        isinstance(access_token, str)
        and access_token
        and isinstance(expires_at, (int, float))
        and expires_at - current_time > 60
    ):
        return access_token

    refreshed = refresh_access_token(
        credentials.get("refresh_token"),
        config,
        post=post,
    )
    credentials.update(refreshed)
    return refreshed["access_token"]


def normalize_customer_id(customer_id):
    if not isinstance(customer_id, str):
        customer_id = str(customer_id or "")
    normalized = customer_id.replace("-", "").strip()
    if not re.fullmatch(r"\d{10}", normalized):
        raise ValueError("Ingresá un ID de cliente de Google Ads válido (10 dígitos).")
    return normalized


def _validated_period(period):
    if not isinstance(period, (tuple, list)) or len(period) != 2:
        raise ValueError("El período seleccionado no es válido.")
    try:
        start = date.fromisoformat(period[0])
        end = date.fromisoformat(period[1])
    except (TypeError, ValueError):
        raise ValueError("Las fechas deben tener el formato AAAA-MM-DD.") from None
    if start > end:
        raise ValueError("La fecha de inicio no puede ser posterior a la fecha de fin.")
    return start.isoformat(), end.isoformat()


def build_campaign_query(period):
    since, until = _validated_period(period)
    return (
        "SELECT campaign.id, campaign.name, campaign.status, segments.date, "
        "metrics.cost_micros, metrics.impressions, metrics.clicks, metrics.ctr, "
        "metrics.average_cpc, metrics.conversions, metrics.conversions_value "
        "FROM campaign "
        f"WHERE segments.date BETWEEN '{since}' AND '{until}' "
        "ORDER BY segments.date, campaign.id"
    )


def _number(value, default=0):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _field(mapping, snake_name, camel_name):
    value = mapping.get(snake_name)
    return mapping.get(camel_name) if value is None else value


def _campaign_row(row):
    campaign = row.get("campaign") or {}
    metrics = row.get("metrics") or {}
    segments = row.get("segments") or {}

    spend = _number(_field(metrics, "cost_micros", "costMicros")) / 1_000_000
    average_cpc = _number(_field(metrics, "average_cpc", "averageCpc")) / 1_000_000
    ctr = _number(metrics.get("ctr")) * 100
    conversions = _number(metrics.get("conversions"))
    revenue = _number(_field(metrics, "conversions_value", "conversionsValue"))
    return {
        "Canal": "GOOGLE",
        "Campaign": campaign.get("name"),
        "Status": campaign.get("status"),
        "Date": segments.get("date"),
        "Spend": spend,
        "Impressions": int(_number(metrics.get("impressions"))),
        "Clicks": int(_number(metrics.get("clicks"))),
        "CTR": ctr,
        "CPC": average_cpc,
        "Conversions": conversions,
        "Revenue": revenue,
        "ROAS": revenue / spend if spend > 0 else None,
    }


def fetch_google_campaigns(
    access_token,
    customer_id,
    period,
    login_customer_id=None,
    *,
    post=None,
):
    if not isinstance(access_token, str) or not access_token:
        raise ValueError("Conectá tu cuenta de Google Ads antes de consultar.")
    customer_id = normalize_customer_id(customer_id)
    query = build_campaign_query(period)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    if login_customer_id:
        headers["login-customer-id"] = normalize_customer_id(login_customer_id)

    post = post or requests.post
    url = (
        f"{GOOGLE_ADS_ENDPOINT}/{API_VERSION}/customers/"
        f"{customer_id}/googleAds:search"
    )
    rows = []
    page_token = None
    while True:
        body = {"query": query}
        if page_token:
            body["pageToken"] = page_token
        try:
            response = post(
                url,
                headers=headers,
                json=body,
                timeout=60,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise GoogleAdsError(
                "No se pudo conectar con Google Ads. Revisá la conexión e intentá nuevamente."
            ) from None

        if response.status_code != 200:
            raise GoogleAdsError(
                f"Google Ads API respondió HTTP {response.status_code}. "
                "Verificá el acceso del usuario a la cuenta y el nivel de acceso "
                "del proyecto de Google Cloud."
            )
        try:
            data = response.json()
        except (ValueError, TypeError):
            raise GoogleAdsError("Google Ads devolvió una respuesta no válida.") from None
        if not isinstance(data, dict):
            raise GoogleAdsError("Google Ads devolvió una respuesta no válida.")

        page_rows = data.get("results", [])
        if not isinstance(page_rows, list):
            raise GoogleAdsError("Google Ads devolvió resultados en un formato no válido.")
        if any(not isinstance(row, dict) for row in page_rows):
            raise GoogleAdsError("Google Ads devolvió una campaña en un formato no válido.")
        rows.extend(_campaign_row(row) for row in page_rows)

        page_token = data.get("nextPageToken")
        if not page_token:
            break
        if not isinstance(page_token, str):
            raise GoogleAdsError("Google Ads devolvió un token de paginación no válido.")

    return pd.DataFrame(rows, columns=GOOGLE_CAMPAIGN_COLUMNS)
