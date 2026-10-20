import csv
import io
import ipaddress
import json
import re
import uuid
from datetime import date
from urllib.parse import urlsplit


PLATFORMS = ("Meta", "Google", "TikTok", "Otra")
SOURCE_URLS = {
    "Meta Ads Library": "https://www.facebook.com/ads/library/",
    "Google Ads Transparency Center": "https://adstransparency.google.com/",
    "TikTok Commercial Content Library": "https://library.tiktok.com/",
}
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
VARIATION_FIELDS = (
    "angle",
    "hook",
    "headline",
    "primary_text",
    "cta",
    "video_script",
    "reference_structure",
)
_URL_CONTROL_CHARS = re.compile(r"[\x00-\x20\x7f]")


def validate_source_url(value):
    """Validate a manually supplied public HTTP(S) source URL without fetching it."""
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) > 2048 or _URL_CONTROL_CHARS.search(value):
        raise ValueError("La URL de la fuente no es válida.")
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


def _text(value, field_name, *, limit=5000):
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"El campo {field_name} supera el máximo permitido.")
    return value


def create_observation(values):
    if not isinstance(values, dict):
        raise ValueError("La observación debe tener formato de objeto.")
    record = {
        "id": _text(values.get("id"), "id", limit=100) or str(uuid.uuid4()),
        "brand": _text(values.get("brand"), "marca", limit=200),
        "platform": _text(values.get("platform"), "plataforma", limit=40),
        "source_url": validate_source_url(values.get("source_url")),
        "observed_on": _text(
            values.get("observed_on"), "fecha", limit=10
        ) or date.today().isoformat(),
        "creative_format": _text(values.get("creative_format"), "formato"),
        "headline": _text(values.get("headline"), "titular"),
        "text": _text(values.get("text"), "texto"),
        "proposition": _text(values.get("proposition"), "propuesta"),
        "offer": _text(values.get("offer"), "oferta"),
        "call_to_action": _text(values.get("call_to_action"), "llamada a la acción"),
        "destination": _text(values.get("destination"), "destino", limit=2048),
        "notes": _text(values.get("notes"), "notas"),
    }
    if not record["brand"]:
        raise ValueError("Ingresá la marca competidora.")
    if record["platform"] not in PLATFORMS:
        raise ValueError("Seleccioná una plataforma válida.")
    try:
        record["observed_on"] = date.fromisoformat(record["observed_on"]).isoformat()
    except ValueError:
        raise ValueError("La fecha de observación debe tener formato AAAA-MM-DD.") from None
    return record


def search_observations(
    observations,
    *,
    query="",
    platform="Todas",
    brand="",
    start_date="",
    end_date="",
):
    query = (query or "").strip().casefold()
    brand = (brand or "").strip().casefold()
    results = []
    for record in observations:
        if platform and platform != "Todas" and record.get("platform") != platform:
            continue
        if brand and brand not in record.get("brand", "").casefold():
            continue
        if start_date and record.get("observed_on", "") < start_date:
            continue
        if end_date and record.get("observed_on", "") > end_date:
            continue
        searchable = " ".join(
            str(record.get(field, ""))
            for field in OBSERVATION_FIELDS
            if field != "id"
        ).casefold()
        if query and query not in searchable:
            continue
        results.append(record)
    return sorted(results, key=lambda record: record.get("observed_on", ""), reverse=True)


def compare_observations(first, second):
    if not isinstance(first, dict) or not isinstance(second, dict):
        raise ValueError("Seleccioná dos observaciones válidas para comparar.")
    return [
        {
            "Campo": field.replace("_", " ").capitalize(),
            "Primera observación": first.get(field, ""),
            "Segunda observación": second.get(field, ""),
        }
        for field in (
            "brand",
            "platform",
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
    ]


def analyze_observation(record):
    text = " ".join(
        str(record.get(field) or "")
        for field in ("headline", "text", "proposition", "offer", "call_to_action")
    ).strip()
    if not text:
        return {
            "status": "insufficient",
            "notice": "No hay texto suficiente para analizar; agregá titular, texto u oferta.",
            "hook": "No determinable",
            "proposition": "No determinable",
            "offer": "No determinable",
            "call_to_action": "No determinable",
        }
    hook_text = " ".join(
        str(record.get(field) or "") for field in ("headline", "text")
    ).casefold()
    if "?" in hook_text or any(word in hook_text for word in ("cómo", "por qué", "sabías")):
        hook = "Pregunta o curiosidad (hipótesis)"
    elif any(word in hook_text for word in ("ahorr", "mejorá", "lográ", "conseguí")):
        hook = "Beneficio (hipótesis)"
    else:
        hook = "Afirmación o descripción (hipótesis)"
    proposition = (
        "Propuesta ingresada manualmente (hipótesis)"
        if str(record.get("proposition") or "").strip()
        else "No indicada"
    )
    offer = (
        "Oferta indicada manualmente (no verificada)"
        if str(record.get("offer") or "").strip()
        else "No indicada"
    )
    cta = (
        "CTA ingresada manualmente (no verificada)"
        if str(record.get("call_to_action") or "").strip()
        else "No indicada"
    )
    return {
        "status": "hypothesis",
        "notice": "Análisis heurístico del texto ingresado; no verifica vigencia ni publicación del anuncio.",
        "hook": hook,
        "proposition": proposition,
        "offer": offer,
        "call_to_action": cta,
    }


def export_observations_json(observations):
    normalized = [create_observation(record) for record in observations]
    return json.dumps(
        {"schema_version": 1, "observations": normalized},
        ensure_ascii=False,
        indent=2,
    )


def import_observations_json(content):
    if isinstance(content, bytes):
        if len(content) > 5_000_000:
            raise ValueError("El archivo JSON supera el tamaño máximo de 5 MB.")
        content = content.decode("utf-8-sig")
    if not isinstance(content, str) or len(content) > 5_000_000:
        raise ValueError("El archivo JSON no es válido o supera 5 MB.")
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("No se pudo leer el archivo JSON de observaciones.") from None
    if isinstance(payload, dict):
        if payload.get("schema_version") != 1:
            raise ValueError("La versión del archivo JSON no es compatible.")
        payload = payload.get("observations")
    if not isinstance(payload, list):
        raise ValueError("El JSON debe contener una lista de observaciones.")
    return [create_observation(record) for record in payload]


def export_observations_csv(observations):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=OBSERVATION_FIELDS)
    writer.writeheader()
    writer.writerows(create_observation(record) for record in observations)
    return output.getvalue()



def _reference_kind(reference):
    if isinstance(reference, dict):
        source = " ".join(
            str(reference.get(key) or "")
            for key in ("headline", "text", "call_to_action")
        )
    else:
        source = str(reference or "")

    source = source.casefold().strip().translate(
        str.maketrans("\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1", "aeiouun")
    )
    if (
        "?" in source
        or "\u00bf" in source
        or any(word in source for word in (
            "como", "por que", "sabias", "buscas", "necesitas"
        ))
    ):
        return "pregunta"

    if any(word in source for word in (
        "ahorr", "oferta", "descuento", "promocion",
        "promo", "rebaja", "2x1"
    )):
        return "promocional"

    return "descriptiva"

def _reference_structure(reference):
    kind = _reference_kind(reference)
    descriptions = {
        "ninguna": "Sin referencia; estructura creada desde los datos propios.",
        "pregunta": (
            "Pregunta/curiosidad detectada; se reutiliza el enfoque, "
            "no el texto literal."
        ),
        "promocional": (
            "\u00c9nfasis promocional detectado; la oferta de referencia "
            "no se atribuye a la marca propia."
        ),
        "descriptiva": (
            "Afirmaci\u00f3n/descripci\u00f3n detectada; hip\u00f3tesis basada en el texto "
            "de referencia."
        ),
    }
    return descriptions[kind]
def generate_ad_variations(inputs, *, reference=None):
    if not isinstance(inputs, dict):
        raise ValueError("Completa los datos del anuncio.")

    required = (
        ("brand", "marca"),
        ("product", "producto o servicio"),
        ("audience", "p\u00fablico objetivo"),
        ("benefit", "beneficio principal"),
        ("objective", "objetivo de campa\u00f1a"),
        ("tone", "tono"),
    )
    values = {
        key: _text(inputs.get(key), label, limit=500)
        for key, label in required
    }
    missing = [label for key, label in required if not values[key]]
    if missing:
        raise ValueError(
            "Completa estos datos antes de generar: "
            + ", ".join(missing) + "."
        )

    def plain(value):
        value = str(value or "").casefold()
        return value.translate(
            str.maketrans(
                "\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1",
                "aeiouun",
            )
        )

    brand = values["brand"]
    product = values["product"]
    audience = values["audience"]
    benefit = values["benefit"].strip().rstrip(" .!?;:")
    objective_plain = plain(values["objective"])
    tone = values["tone"].casefold()

    offer = _text(inputs.get("offer"), "oferta", limit=500)
    offer_plain = plain(offer)
    placeholder_offer = (
        offer_plain in {
            "", "vacio", "(vacio)", "sin oferta", "sin promocion",
            "no aplica", "n/a", "ninguna",
        }
        or offer_plain.startswith((
            "dejar vacio", "completar", "ingresar", "escribir",
            "sin oferta", "sin promocion", "solo si",
        ))
        or "si no hay una promocion vigente" in offer_plain
    )
    if placeholder_offer:
        offer = ""

    cta = {
        "reconocimiento": "Conocer m\u00e1s",
        "reconocimiento de marca": "Conocer m\u00e1s",
        "awareness": "Conocer m\u00e1s",
        "trafico": "Ver producto",
        "traffic": "Ver producto",
        "leads": "Solicitar informaci\u00f3n",
        "generar consultas": "Solicitar informaci\u00f3n",
        "clientes potenciales": "Solicitar informaci\u00f3n",
        "consultas": "Solicitar informaci\u00f3n",
        "conversion": "Ver opciones",
        "conversiones": "Ver opciones",
        "ventas": "Ver opciones",
    }.get(objective_plain, "Conocer m\u00e1s")

    product_lower = product[0].lower() + product[1:]
    product_plain = plain(product)
    audience_lower = audience[0].lower() + audience[1:]

    if product_plain.startswith("instalacion de "):
        product_phrase = "la " + product_lower
    elif product_plain.startswith("servicio de "):
        product_phrase = "el " + product_lower
    else:
        product_phrase = product_lower

    if product_plain.startswith("instalacion de aire acondicionado"):
        service_action = "instalar tu aire acondicionado"
    elif product_plain.startswith("instalacion de "):
        service_action = "realizar " + product_phrase
    else:
        service_action = product_phrase

    benefit_plain = plain(benefit)
    if benefit_plain.startswith((
        "instalacion coordinada",
        "coordinacion de la instalacion",
    )):
        benefit_sentence = (
            "Coordinamos la instalaci\u00f3n "
            "seg\u00fan las necesidades del cliente."
        )
    elif benefit_plain.startswith("atencion personalizada"):
        benefit_sentence = "Ofrecemos atenci\u00f3n personalizada."
    elif benefit_plain.startswith("prendas faciles de combinar"):
        benefit_sentence = "Encontr\u00e1 prendas f\u00e1ciles de combinar."
    elif benefit_plain.startswith((
        "ofrecemos ", "brindamos ", "coordinamos ",
    )):
        benefit_sentence = benefit[0].upper() + benefit[1:]
        benefit_sentence = benefit_sentence.rstrip(".") + "."
    else:
        benefit_lower = benefit[0].lower() + benefit[1:]
        benefit_sentence = f"Beneficio destacado: {benefit_lower}."

    structure = _reference_structure(reference)
    reference_kind = _reference_kind(reference)

    if reference_kind == "promocional":
        hook_1 = f"Consult\u00e1 por {product_phrase} en {brand}."
    elif tone == "directo":
        hook_1 = f"Consult\u00e1 por {product_phrase}."
    elif tone == "experto":
        hook_1 = (
            f"Antes de decidir, consult\u00e1 las condiciones "
            f"de {product_phrase}."
        )
    elif tone == "inspirador":
        hook_1 = (
            f"Encontr\u00e1 una opci\u00f3n de {product_lower} "
            "que se adapte a vos."
        )
    elif tone == "informal":
        hook_1 = (
            f"\u00bfLo ten\u00e9s pendiente? "
            f"Consult\u00e1 por {product_phrase}."
        )
    else:
        hook_1 = f"\u00bfNecesit\u00e1s {service_action}?"

    # Evitar repetir el mismo encuadre cuando la referencia ya plantea una pregunta.
    if reference_kind == "pregunta" and hook_1.lstrip().startswith(("¿", "?")):
        hook_1 = f"Consultá opciones para {product_phrase} con {brand}."

    primary_text_1 = (
        f"En {brand}, pod\u00e9s consultar por {product_phrase}. "
        f"{benefit_sentence} "
        "Escribinos para conocer disponibilidad y condiciones."
    )

    if offer:
        angle_3 = "Oferta"
        hook_3 = f"Conoc\u00e9 la propuesta de {brand}."
        headline_3 = f"Una propuesta para {product_lower}"
        primary_text_3 = (
            f"Conoc\u00e9 la propuesta de {brand}: {offer}. "
            "Consult\u00e1 las condiciones y la vigencia antes de contratar."
        )
        cta_3 = "Consultar condiciones"
        video_text_3 = offer
    else:
        angle_3 = "Informaci\u00f3n y condiciones"
        hook_3 = (
            f"\u00bfQuer\u00e9s consultar la disponibilidad "
            f"de {product_phrase}?"
        )
        headline_3 = "Disponibilidad y condiciones"
        primary_text_3 = (
            f"Contact\u00e1 a {brand} para consultar la disponibilidad "
            f"y las condiciones de {product_phrase}. "
            "Contanos qu\u00e9 necesit\u00e1s para recibir "
            "informaci\u00f3n sobre tu caso."
        )
        cta_3 = cta
        video_text_3 = "Consult\u00e1 disponibilidad y condiciones"

    return [
        {
            "angle": "Beneficio",
            "hook": hook_1,
            "headline": product,
            "primary_text": primary_text_1,
            "cta": cta,
            "video_script": (
                f"Escena 1: mostrar {product_lower} en contexto. "
                f"Locuci\u00f3n: {hook_1} {benefit_sentence} "
                f"Cierre: {brand} | {cta}."
            ),
            "reference_structure": (f"{structure} Enfoque aplicado: destacar el beneficio y proponer una consulta con un gancho alternativo."),
        },
        {
            "angle": "Resolver dudas",
            "hook": (
                f"Antes de elegir, conoc\u00e9 los detalles "
                f"de {product_phrase}."
            ),
            "headline": f"Informaci\u00f3n sobre {product_lower}",
            "primary_text": (
                f"Para {audience_lower}, en {brand} pod\u00e9s consultar "
                f"por {product_phrase}, su disponibilidad y sus condiciones. "
                "Contanos qu\u00e9 necesit\u00e1s para orientarte."
            ),
            "cta": cta,
            "video_script": (
                f"Escena 1: mostrar {product_lower}. "
                "Texto en pantalla: Consult\u00e1 disponibilidad "
                "y condiciones. "
                f"Cierre: {brand} | {cta}."
            ),
            "reference_structure": (f"{structure} Enfoque aplicado: resolver dudas y facilitar la evaluación de disponibilidad y condiciones."),
        },
        {
            "angle": angle_3,
            "hook": hook_3,
            "headline": headline_3,
            "primary_text": primary_text_3,
            "cta": cta_3,
            "video_script": (
                f"Escena 1: presentar {product_lower}. "
                f"Texto en pantalla: {video_text_3}. "
                f"Cierre: {brand} | {cta_3}."
            ),
            "reference_structure": (f"{structure} Enfoque aplicado: " + ("presentar la oferta ingresada para la marca propia." if offer else "informar disponibilidad y condiciones sin inventar una oferta.")),
        },
    ]
def export_variations_csv(variations):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=VARIATION_FIELDS)
    writer.writeheader()
    writer.writerows(
        {field: variation.get(field, "") for field in VARIATION_FIELDS}
        for variation in variations
    )
    return output.getvalue()


def export_variations_txt(variations):
    sections = []
    for index, variation in enumerate(variations, start=1):
        sections.append(
            "\n".join(
                [
                    f"VARIACIÓN {index} — {variation.get('angle', '')}",
                    f"Gancho: {variation.get('hook', '')}",
                    f"Titular: {variation.get('headline', '')}",
                    f"Texto principal: {variation.get('primary_text', '')}",
                    f"CTA: {variation.get('cta', '')}",
                    f"Guion de video: {variation.get('video_script', '')}",
                    f"Estructura de referencia (hipótesis): {variation.get('reference_structure', '')}",
                ]
            )
        )
    return "\n\n".join(sections)
