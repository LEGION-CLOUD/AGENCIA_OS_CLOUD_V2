"""Rule-based original ad copy proposals for Agency OS."""

import re
import unicodedata


def _plain(text):
    text = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _clean(text):
    return re.sub(r"\s+", " ", str(text or "").strip()).strip(" .!?;,")


def _clean_promo(text):
    promo = _clean(text)
    # This is an instruction, not customer-facing promotional copy.
    promo = re.sub(
        r"(?i)(?:[.;,]\s*)?sin descuentos ni precios inventados\.?$",
        "",
        promo,
    )
    promo = re.sub(r"(?i)\bpromocion informada:\s*", "", promo)
    return _clean(promo)


def _benefits(text):
    text = _clean(text)
    text = re.sub(r"(?i)^beneficios informados:\s*", "", text)
    text = re.sub(r"(?i)^servicio de\s+", "", text)
    return _clean(text)


def _sector(text):
    value = _plain(text)
    # Prefer service intent when the offer is a repair/installation, even if
    # it mentions a technology product such as a phone or air conditioner.
    if any(word in value for word in ("instalacion", "reparacion", "diagnostico", "mantenimiento", "servicio")):
        return "SERVICIO"
    if any(word in value for word in ("ropa", "moda", "jeans", "blazer", "vestido", "tops", "calzado", "coleccion")):
        return "MODA"
    if any(word in value for word in ("celular", "telefono", "notebook", "computadora", "hardware", "auricular", "televisor", "tecnologia")):
        return "TECH"
    if any(word in value for word in ("supermercado", "alimentos", "verduleria", "carniceria", "almacen")):
        return "COMERCIO"
    return "GENERAL"


def _offer_parts(offer):
    clean = _clean(offer)
    if ":" in clean:
        head, detail = clean.split(":", 1)
        if len(head.strip()) <= 85 and detail.strip():
            return _clean(head), _clean(detail)
    return clean, ""


def generate_ad_proposals(description, benefits="", promotion="", objective="Ventas"):
    """Return three sector-aware ad proposals using only user-provided claims."""
    offer = _clean(description)
    if not offer:
        return []

    short_offer, details = _offer_parts(offer)
    benefit_text = _benefits(benefits)
    promo_text = _clean_promo(promotion)
    sector = _sector(offer + " " + benefit_text)

    normalized_offer = _plain(short_offer)
    installation_prefix = "servicio de instalacion de "
    if normalized_offer.startswith(installation_prefix):
        item = short_offer[len(installation_prefix):].strip()
        short_offer = f"la instalación de {item}"

    if objective == "Ventas":
        ctas = [
            "Consultá precio y disponibilidad.",
            "Escribinos para conocer las opciones.",
            "Hacé tu consulta antes de decidir.",
        ]
    elif objective == "Generar consultas":
        ctas = [
            "Contanos qué necesitás.",
            "Escribinos y consultá los detalles.",
            "Dejanos tu consulta y te orientamos.",
        ]
    else:
        ctas = [
            "Conocé la propuesta.",
            "Descubrí más sobre esta opción.",
            "Conocé los detalles.",
        ]

    promo_line = f" {promo_text}." if promo_text else ""
    benefit_line = f" {benefit_text}." if benefit_text else ""

    if sector == "MODA":
        title_1 = "Tu próximo look empieza acá"
        detail_sentence = f" Explorá opciones como {details}." if details else ""
        body_1 = (
            "Descubrí prendas para crear looks casuales o elegantes."
            + detail_sentence
        )
        title_2 = "Moda para combinar a tu manera"
        body_2 = (
            f"{details.capitalize()}. " if details else ""
        ) + "Encontrá combinaciones para distintos estilos."
        title_3 = "¿Qué look estás buscando?"
        body_3 = "Contanos qué estilo te gusta y consultá por las prendas disponibles."
    elif sector == "TECH":
        title_1 = "Encontrá la opción que necesitás"
        body_1 = f"Conocé la propuesta de {short_offer} y sus características."
        title_2 = f"Conocé mejor {short_offer}"
        body_2 = f"Consultá las características y opciones de {short_offer}."
        title_3 = "¿Qué necesitás resolver?"
        body_3 = f"Contanos qué estás buscando y consultá por {short_offer}."
    elif sector == "SERVICIO":
        if short_offer.lower().startswith("la instalación de "):
            title_1 = f"¿Estás por instalar {short_offer[len('la instalación de '):]}?"
            body_1 = f"Consultá por {short_offer} y conocé los detalles antes de decidir."
        else:
            title_1 = f"¿Necesitás {short_offer.lower()}?"
            body_1 = f"Conocé la propuesta de {short_offer} y consultá cómo puede ayudarte."
        title_2 = "Información clara para elegir"
        body_2 = f"Consultá qué incluye {short_offer} y las condiciones del servicio."
        title_3 = "Contanos qué necesitás"
        body_3 = f"Explicanos tu caso y consultá por {short_offer}."
    else:
        title_1 = f"Descubrí {short_offer}"
        body_1 = f"Conocé la propuesta de {short_offer} y sus características."
        title_2 = f"Conocé mejor {short_offer}"
        body_2 = f"Explorá las opciones de {short_offer} y elegí con información clara."
        title_3 = "Busquemos la opción para vos"
        body_3 = f"Contanos qué necesitás y consultá por {short_offer}."

    proposals = [
        (
            "ANUNCIO 1 — ATRAER LA ATENCIÓN\n"
            f"TÍTULO: {title_1}\n"
            f"TEXTO: {body_1}{benefit_line}{promo_line}\n"
            f"CTA: {ctas[0]}"
        ),
        (
            "ANUNCIO 2 — DESTACAR EL VALOR\n"
            f"TÍTULO: {title_2}\n"
            f"TEXTO: {body_2}{benefit_line}{promo_line}\n"
            f"CTA: {ctas[1]}"
        ),
        (
            "ANUNCIO 3 — GENERAR UNA CONVERSACIÓN\n"
            f"TÍTULO: {title_3}\n"
            f"TEXTO: {body_3}{benefit_line}{promo_line}\n"
            f"CTA: {ctas[2]}"
        ),
    ]
    return proposals
