import json
import math
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO

import pandas as pd
import requests

from safe_csv import dataframe_to_csv_bytes


TIKTOK_API_BASE_URL = "https://business-api.tiktok.com/open_api/v1.3"
TIKTOK_REPORT_ENDPOINT = f"{TIKTOK_API_BASE_URL}/report/integrated/get/"
TIKTOK_PAGE_SIZE = 1000
TIKTOK_REPORT_TYPE = "BASIC"
TIKTOK_DATA_LEVEL = "AUCTION_CAMPAIGN"

TIKTOK_REPORT_COLUMNS = [
    "Canal",
    "Campaign ID",
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

TIKTOK_CAMPAIGN_DIMENSIONS = ["campaign_id", "stat_time_day"]
TIKTOK_CAMPAIGN_METRICS = ["campaign_name", "spend", "impressions", "clicks"]


class TikTokAdsError(Exception):
    """A safe, user-facing TikTok Ads reporting error."""


@dataclass(frozen=True)
class TikTokReportConfig:
    access_token: str = field(repr=False)


def _validated_token(access_token):
    if not isinstance(access_token, str) or not access_token.strip():
        raise TikTokAdsError("Ingresá el token de acceso de TikTok Ads.")
    return access_token.strip()


def normalize_advertiser_id(advertiser_id):
    if not isinstance(advertiser_id, str):
        advertiser_id = str(advertiser_id or "")
    advertiser_id = advertiser_id.strip()
    if not advertiser_id.isascii() or not advertiser_id.isdigit():
        raise ValueError("El ID de anunciante de TikTok debe contener solo dígitos.")
    return advertiser_id


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
    if (end - start).days >= 30:
        raise ValueError(
            "Los informes diarios de TikTok admiten un rango máximo de 30 días."
        )
    return start.isoformat(), end.isoformat()


def _number(value):
    if value is None or value == "" or value == "-":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _optional_int(value):
    number = _number(value)
    return int(number) if number is not None and number.is_integer() else number


def _normalize_report_row(item):
    if not isinstance(item, dict):
        raise TikTokAdsError("TikTok devolvió una fila en un formato no válido.")
    dimensions = item.get("dimensions")
    metrics = item.get("metrics")
    if not isinstance(dimensions, dict) or not isinstance(metrics, dict):
        raise TikTokAdsError("TikTok devolvió una fila en un formato no válido.")

    spend = _number(metrics.get("spend"))
    impressions = _optional_int(metrics.get("impressions"))
    clicks = _optional_int(metrics.get("clicks"))
    ctr = (
        (float(clicks) / float(impressions)) * 100
        if clicks is not None and impressions is not None and impressions > 0
        else None
    )
    cpc = (
        spend / float(clicks)
        if spend is not None and clicks is not None and clicks > 0
        else None
    )

    return {
        "Canal": "TIKTOK",
        "Campaign ID": str(dimensions.get("campaign_id")) if dimensions.get("campaign_id") is not None else None,
        "Campaign": metrics.get("campaign_name"),
        "Status": None,
        "Date": dimensions.get("stat_time_day"),
        "Spend": spend,
        "Impressions": impressions,
        "Clicks": clicks,
        "CTR": ctr,
        "CPC": cpc,
        "Conversions": None,
        "Revenue": None,
        "ROAS": None,
    }


def _request_page(get, config, advertiser_id, period, page):
    start_date, end_date = period
    params = {
        "advertiser_id": advertiser_id,
        "report_type": TIKTOK_REPORT_TYPE,
        "data_level": TIKTOK_DATA_LEVEL,
        "dimensions": json.dumps(TIKTOK_CAMPAIGN_DIMENSIONS),
        "metrics": json.dumps(TIKTOK_CAMPAIGN_METRICS),
        "start_date": start_date,
        "end_date": end_date,
        "page": page,
        "page_size": TIKTOK_PAGE_SIZE,
    }
    try:
        response = get(
            TIKTOK_REPORT_ENDPOINT,
            headers={"Access-Token": config.access_token},
            params=params,
            timeout=30,
            allow_redirects=False,
        )
    except requests.RequestException:
        raise TikTokAdsError(
            "No se pudo conectar con TikTok Ads. Revisá la conexión e intentá nuevamente."
        ) from None

    if response.status_code in (401, 403):
        raise TikTokAdsError(
            f"TikTok Ads rechazó el acceso (HTTP {response.status_code}). "
            "Verificá que el token sea válido y tenga permisos de reporting."
        )
    if response.status_code != 200:
        raise TikTokAdsError(
            f"TikTok Ads respondió HTTP {response.status_code} al consultar el informe."
        )
    try:
        body = response.json()
    except (ValueError, TypeError):
        raise TikTokAdsError("TikTok Ads devolvió una respuesta no válida.") from None
    if not isinstance(body, dict):
        raise TikTokAdsError("TikTok Ads devolvió una respuesta no válida.")

    api_code = body.get("code")
    if api_code != 0:
        if isinstance(api_code, bool) or not isinstance(api_code, int):
            raise TikTokAdsError("TikTok Ads devolvió un código de error no válido.")
        raise TikTokAdsError(
            f"TikTok Ads rechazó el informe (código {api_code}). "
            "Verificá el token, el anunciante autorizado y los permisos de reporting."
        )

    data = body.get("data")
    if not isinstance(data, dict):
        raise TikTokAdsError("TikTok Ads devolvió datos en un formato no válido.")
    rows = data.get("list")
    page_info = data.get("page_info")
    if not isinstance(rows, list) or not isinstance(page_info, dict):
        raise TikTokAdsError("TikTok Ads devolvió datos en un formato no válido.")
    total_pages = page_info.get("total_page")
    if (
        isinstance(total_pages, bool)
        or not isinstance(total_pages, int)
        or total_pages < 0
    ):
        raise TikTokAdsError("TikTok Ads devolvió información de paginación no válida.")
    return rows, total_pages


def fetch_campaign_report(access_token, advertiser_id, period, *, get=None):
    token = _validated_token(access_token)
    config = TikTokReportConfig(access_token=token)
    normalized_advertiser_id = normalize_advertiser_id(advertiser_id)
    selected_period = _validated_period(period)
    get = get or requests.get

    rows = []
    page = 1
    total_pages = 1
    while page <= total_pages:
        page_rows, total_pages = _request_page(
            get,
            config,
            normalized_advertiser_id,
            selected_period,
            page,
        )
        if any(not isinstance(row, dict) for row in page_rows):
            raise TikTokAdsError("TikTok Ads devolvió una fila en un formato no válido.")
        rows.extend(_normalize_report_row(row) for row in page_rows)
        page += 1

    return pd.DataFrame(rows, columns=TIKTOK_REPORT_COLUMNS)


def export_report_csv(report):
    return dataframe_to_csv_bytes(report)


def export_report_excel(report):
    output = BytesIO()
    report.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()
