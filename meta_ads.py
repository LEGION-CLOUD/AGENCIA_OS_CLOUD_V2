import json
import logging
from datetime import date, timedelta
from urllib.parse import urlparse

import pandas as pd
import requests


CAMPAIGN_COLUMNS = [
    "Canal", "Campaign ID", "Campaign", "Spend", "Impressions",
    "CTR", "CPC", "Conversions", "Revenue", "ROAS"
]

logger = logging.getLogger(__name__)


class MetaAdsError(Exception):
    """A safe, user-facing Meta Ads query error."""


def _log_meta_response(
    account_id,
    since,
    until,
    http_status,
    graph_code,
    row_count,
):
    log_method = logger.info if http_status == 200 and graph_code is None else logger.warning
    log_method(
        "Meta insights account=%s since=%s until=%s level=campaign "
        "http_status=%s graph_code=%s rows=%s",
        account_id,
        since,
        until,
        http_status,
        graph_code,
        row_count,
    )


def meta_date_range(preset, custom_start=None, custom_end=None, *, today=None):
    if preset == "custom":
        if not isinstance(custom_start, date) or not isinstance(custom_end, date):
            raise ValueError("Seleccioná las fechas de inicio y fin.")
        if custom_start > custom_end:
            raise ValueError("La fecha de inicio no puede ser posterior a la fecha de fin.")
        return custom_start.isoformat(), custom_end.isoformat()

    date_ranges = {
        "last_7d": 7,
        "last_14d": 14,
        "last_30d": 30,
    }
    days = date_ranges.get(preset)
    if days is None:
        raise ValueError("Rango de fechas no válido.")

    reference_date = today or date.today()
    return (
        (reference_date - timedelta(days=days)).isoformat(),
        (reference_date - timedelta(days=1)).isoformat(),
    )


def normalize_ad_account(ad_account):
    account_id = ad_account.strip()
    account_number = account_id[4:] if account_id.startswith("act_") else account_id
    if not account_number.isascii() or not account_number.isdigit():
        raise ValueError("El ID de la cuenta publicitaria no es válido.")
    return f"act_{account_number}"


def _metric_value(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _purchase_value(actions, purchase_types):
    if not isinstance(actions, list):
        return None
    if any(not isinstance(action, dict) for action in actions):
        return None

    for action_type in purchase_types:
        values = [
            _metric_value(action.get("value"))
            for action in actions
            if action.get("action_type") == action_type
        ]
        if values:
            if any(value is None for value in values):
                return None
            return sum(values)
    return None


def fetch_meta_insights(token, ad_account, period, *, get=None):
    if not token or not token.strip():
        raise ValueError("Ingresá el token de Meta.")
    if not isinstance(period, tuple) or len(period) != 2:
        raise ValueError("El período seleccionado no es válido.")

    account_id = normalize_ad_account(ad_account)
    since, until = period
    url = f"https://graph.facebook.com/v24.0/{account_id}/insights"
    params = {
        "access_token": token.strip(),
        "level": "campaign",
        "time_range": json.dumps({"since": since, "until": until}),
        "fields": (
            "campaign_id,campaign_name,spend,impressions,clicks,ctr,cpc,"
            "actions,action_values"
        ),
        "limit": 500,
    }
    get = get or requests.get
    rows = []
    purchase_types = (
        "omni_purchase",
        "purchase",
        "offsite_conversion.fb_pixel_purchase",
    )

    try:
        seen_pages = set()
        while url:
            if url in seen_pages:
                raise MetaAdsError("Meta devolvió una página repetida; se detuvo la consulta.")
            seen_pages.add(url)

            response = get(url, params=params, timeout=30, allow_redirects=False)
            try:
                data = response.json()
            except (ValueError, TypeError):
                _log_meta_response(
                    account_id,
                    since,
                    until,
                    response.status_code,
                    None,
                    0,
                )
                raise MetaAdsError(
                    f"Meta devolvió una respuesta no válida (HTTP {response.status_code})."
                ) from None

            if not isinstance(data, dict):
                _log_meta_response(
                    account_id,
                    since,
                    until,
                    response.status_code,
                    None,
                    0,
                )
                raise MetaAdsError("Meta devolvió una respuesta no válida.")

            if response.status_code != 200 or "error" in data:
                error = data.get("error", {})
                if not isinstance(error, dict):
                    error = {}
                code = error.get("code")
                if not isinstance(code, int) or isinstance(code, bool):
                    code = None
                page_rows = data.get("data")
                row_count = len(page_rows) if isinstance(page_rows, list) else 0
                _log_meta_response(
                    account_id,
                    since,
                    until,
                    response.status_code,
                    code,
                    row_count,
                )
                code_message = f", código Graph {code}" if code is not None else ""
                raise MetaAdsError(
                    f"Meta rechazó la consulta (HTTP {response.status_code}{code_message}). "
                    "Verificá que el token siga vigente, que la cuenta sea accesible "
                    "y que el acceso autorizado permita leer sus anuncios."
                )

            page_rows = data.get("data")
            if not isinstance(page_rows, list):
                _log_meta_response(
                    account_id,
                    since,
                    until,
                    response.status_code,
                    None,
                    0,
                )
                raise MetaAdsError("Meta devolvió datos de campañas en un formato no válido.")

            _log_meta_response(
                account_id,
                since,
                until,
                response.status_code,
                None,
                len(page_rows),
            )
            for item in page_rows:
                if not isinstance(item, dict):
                    raise MetaAdsError("Meta devolvió una campaña en un formato no válido.")

                spend = _metric_value(item.get("spend"))
                impressions = _metric_value(item.get("impressions"))
                revenue = _purchase_value(item.get("action_values"), purchase_types)
                rows.append({
                    "Canal": "META",
                    "Campaign ID": item.get("campaign_id"),
                    "Campaign": item.get("campaign_name"),
                    "Spend": spend,
                    "Impressions": int(impressions) if impressions is not None else None,
                    "CTR": _metric_value(item.get("ctr")),
                    "CPC": _metric_value(item.get("cpc")),
                    "Conversions": _purchase_value(item.get("actions"), purchase_types),
                    "Revenue": revenue,
                    "ROAS": revenue / spend if revenue is not None and spend > 0 else None,
                })

            paging = data.get("paging", {})
            if not isinstance(paging, dict):
                raise MetaAdsError("Meta devolvió datos de paginación en un formato no válido.")

            url = paging.get("next")
            if url is not None:
                try:
                    parsed_url = urlparse(url) if isinstance(url, str) else None
                    valid_next_url = (
                        parsed_url is not None
                        and parsed_url.scheme == "https"
                        and parsed_url.hostname == "graph.facebook.com"
                        and parsed_url.username is None
                        and parsed_url.password is None
                        and parsed_url.port in (None, 443)
                    )
                except ValueError:
                    valid_next_url = False
                if not valid_next_url:
                    raise MetaAdsError("Meta devolvió un enlace de paginación no válido.")
            params = None
    except requests.RequestException:
        raise MetaAdsError(
            "No se pudo conectar con Meta. Revisá la conexión e intentá nuevamente."
        ) from None

    return pd.DataFrame(rows, columns=CAMPAIGN_COLUMNS)
