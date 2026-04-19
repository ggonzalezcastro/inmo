"""
Random property generator for demo / seed data.

Genera propiedades chilenas realistas con datos coherentes:
  - Comunas y regiones reales del Gran Santiago
  - Precios UF/CLP coherentes (UF ≈ $38.000 CLP)
  - m² coherentes con número de dormitorios
  - ~30% de propiedades con oferta activa (offer_price 5–15% bajo list_price)

Uso típico (ver routes.generate_sample_properties):
    from app.services.properties.generator import generate_random_property
    prop = generate_random_property(broker_id=1)
"""
from __future__ import annotations

import random
import uuid
from typing import Any, Dict, List, Optional

from app.models.project import Project
from app.models.property import Property


# Conversión aproximada UF→CLP (valor de mercado abril 2026 ≈ $38.000).
_UF_TO_CLP = 38_000


_COMMUNES_RM: List[Dict[str, str]] = [
    {"commune": "Las Condes", "city": "Santiago", "region": "Región Metropolitana"},
    {"commune": "Providencia", "city": "Santiago", "region": "Región Metropolitana"},
    {"commune": "Ñuñoa", "city": "Santiago", "region": "Región Metropolitana"},
    {"commune": "Vitacura", "city": "Santiago", "region": "Región Metropolitana"},
    {"commune": "Lo Barnechea", "city": "Santiago", "region": "Región Metropolitana"},
    {"commune": "La Reina", "city": "Santiago", "region": "Región Metropolitana"},
    {"commune": "Macul", "city": "Santiago", "region": "Región Metropolitana"},
    {"commune": "San Miguel", "city": "Santiago", "region": "Región Metropolitana"},
    {"commune": "Maipú", "city": "Santiago", "region": "Región Metropolitana"},
    {"commune": "La Florida", "city": "Santiago", "region": "Región Metropolitana"},
    {"commune": "Santiago Centro", "city": "Santiago", "region": "Región Metropolitana"},
    {"commune": "Independencia", "city": "Santiago", "region": "Región Metropolitana"},
]

_STREET_NAMES = [
    "Av. Apoquindo", "Av. Vitacura", "Av. Kennedy", "Av. Las Condes", "Av. Providencia",
    "Av. Irarrázaval", "Av. Tobalaba", "Av. Manquehue", "Av. Pedro de Valdivia",
    "Av. Los Leones", "Calle Pocuro", "Calle Holanda", "Calle Suecia",
    "Av. Bilbao", "Av. Grecia", "Av. Vicuña Mackenna",
]

_PROPERTY_TYPES = ["departamento", "casa", "oficina"]
# 'terreno' se omite para no generar specs incoherentes (sin baños/dormitorios).

_AMENITIES_POOL = [
    "piscina", "gimnasio", "quincho", "salón_eventos", "áreas_verdes",
    "sala_de_cine", "cowork", "lavandería", "bodega", "conserjería_24h",
    "sala_multiuso", "juegos_infantiles", "bicicletero", "sala_de_estudio",
]

_HIGHLIGHTS_POOL = [
    "Luminoso, vista panorámica",
    "Recién remodelado, listo para entrar",
    "Excelente ubicación, cercano a metro",
    "Vista a la cordillera",
    "Terraza amplia con parrilla",
    "Edificio nuevo con áreas comunes premium",
    "Piso alto, súper iluminado",
    "Plusvalía garantizada en sector consolidado",
]

_ORIENTATIONS = ["norte", "sur", "oriente", "poniente", "nororiente", "norponiente", "suroriente"]

_DESCRIPTION_TEMPLATES = [
    (
        "Espectacular {ptype} de {bedrooms} dormitorios y {bathrooms} baños en {commune}, "
        "con {sqm} m² útiles. Cuenta con {parking} estacionamiento(s) y bodega. "
        "Sector consolidado con excelente conectividad y plusvalía."
    ),
    (
        "{ptype_capital} en {commune} con vista despejada y terminaciones de primer nivel. "
        "{bedrooms} dormitorios, {bathrooms} baños, {sqm} m² útiles. "
        "Cercano a colegios, supermercados y áreas verdes."
    ),
    (
        "Hermoso {ptype} ubicado en una de las mejores zonas de {commune}. "
        "Diseño funcional, {bedrooms}D / {bathrooms}B, {sqm} m². "
        "Ideal para familias o inversión segura."
    ),
]

_FINANCING_OPTIONS_POOL = [
    ["crédito_hipotecario", "leasing"],
    ["crédito_hipotecario"],
    ["crédito_hipotecario", "pie_en_cuotas"],
    ["crédito_hipotecario", "leasing", "pie_en_cuotas"],
]


def _coherent_sqm(bedrooms: int, ptype: str) -> tuple[float, float]:
    """Devuelve (m² útiles, m² totales) coherentes con tipo y dormitorios."""
    if ptype == "casa":
        useful = random.randint(80, 220) + bedrooms * 10
        total = useful + random.randint(20, 120)
    elif ptype == "oficina":
        useful = random.randint(35, 180)
        total = useful + random.randint(5, 25)
    else:  # departamento
        base = {0: 28, 1: 38, 2: 55, 3: 78, 4: 110}.get(bedrooms, 65)
        useful = base + random.randint(-5, 20)
        total = useful + random.randint(5, 20)
    return float(useful), float(total)


def _coherent_price_uf(bedrooms: int, sqm_useful: float, commune: str) -> int:
    """Precio UF coherente con tamaño y plusvalía aproximada por comuna."""
    premium_communes = {"Vitacura", "Las Condes", "Lo Barnechea", "Providencia", "La Reina"}
    uf_per_m2 = random.uniform(95, 145) if commune in premium_communes else random.uniform(55, 95)
    base = sqm_useful * uf_per_m2
    # Pequeña variación por dormitorios.
    base += bedrooms * random.uniform(50, 200)
    return int(round(base / 50.0) * 50)  # redondeo a múltiplos de 50 UF


def generate_random_property(
    broker_id: int,
    *,
    seed: Optional[int] = None,
    project: Optional["Project"] = None,
) -> Property:
    """Construye (sin persistir) una `Property` con datos chilenos coherentes.

    Si se entrega `project`, la property hereda comuna/ciudad/región/financing
    /subsidio del proyecto y se setea `project_id` + una `tipologia` coherente.
    """
    if seed is not None:
        random.seed(seed)

    if project is not None:
        loc = {
            "commune": project.commune or random.choice(_COMMUNES_RM)["commune"],
            "city": project.city or "Santiago",
            "region": project.region or "Región Metropolitana",
        }
    else:
        loc = random.choice(_COMMUNES_RM)
    ptype = random.choices(_PROPERTY_TYPES, weights=[7, 2, 1])[0]
    if project is not None:
        # En proyectos modelamos solo unidades de departamento para coherencia
        # (los proyectos demo son edificios).
        ptype = "departamento"
    bedrooms = 0 if ptype == "oficina" else random.randint(1, 4)
    bathrooms = max(1, min(bedrooms, 3)) if ptype != "oficina" else random.randint(1, 2)
    sqm_useful, sqm_total = _coherent_sqm(bedrooms, ptype)

    list_uf = _coherent_price_uf(bedrooms, sqm_useful, loc["commune"])
    list_clp = list_uf * _UF_TO_CLP

    has_offer = random.random() < 0.30
    offer_uf: Optional[int] = None
    offer_clp: Optional[int] = None
    if has_offer:
        discount = random.uniform(0.05, 0.15)
        offer_uf = int(round(list_uf * (1 - discount) / 50.0) * 50)
        offer_clp = offer_uf * _UF_TO_CLP

    parking = 0 if ptype == "oficina" else random.randint(0, 3)
    storage = 0 if ptype == "oficina" else random.randint(0, 2)
    floor_number = random.randint(1, 25) if ptype == "departamento" else None
    total_floors = (floor_number + random.randint(0, 10)) if floor_number else None

    amenities = random.sample(_AMENITIES_POOL, k=random.randint(2, 6))
    nearby = [
        {"type": "metro", "name": random.choice(["Tobalaba", "Los Leones", "Manquehue", "Escuela Militar"]), "distance_m": random.randint(150, 1200)},
        {"type": "supermercado", "name": random.choice(["Jumbo", "Líder", "Unimarc"]), "distance_m": random.randint(100, 800)},
    ]

    template = random.choice(_DESCRIPTION_TEMPLATES)
    description = template.format(
        ptype=ptype,
        ptype_capital=ptype.capitalize(),
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        sqm=int(sqm_useful),
        commune=loc["commune"],
        parking=parking,
    )
    highlights = random.choice(_HIGHLIGHTS_POOL)

    street = random.choice(_STREET_NAMES)
    address = f"{street} {random.randint(100, 9999)}, {loc['commune']}"

    if project is not None:
        # Código de unidad estilo "Depto 1502" (piso + nro).
        unit_no = (floor_number or random.randint(1, 25)) * 100 + random.randint(1, 6)
        codigo = f"Depto {unit_no:04d}"
        # Tipología derivada de dorms/baños (ej. "2D2B").
        tipologia = f"{bedrooms}D{bathrooms}B"
        name = f"{project.name} - {codigo}"
        financing = project.financing_options or random.choice(_FINANCING_OPTIONS_POOL)
        subsidio = bool(project.subsidio_eligible) and (list_uf <= 2200)
    else:
        codigo = f"{ptype[:3].upper()}-{random.randint(1000, 9999)}"
        tipologia = None
        name = (
            f"{ptype.capitalize()} {loc['commune']} {bedrooms}D"
            if bedrooms
            else f"{ptype.capitalize()} {loc['commune']}"
        )
        financing = random.choice(_FINANCING_OPTIONS_POOL)
        subsidio = list_uf <= 2200

    return Property(
        broker_id=broker_id,
        name=name,
        codigo=codigo,
        tipologia=tipologia,
        project_id=project.id if project is not None else None,
        property_type=ptype,
        status="available",
        commune=loc["commune"],
        city=loc["city"],
        region=loc["region"],
        address=address,
        # price_uf/clp se mantiene en sync con list_price para compatibilidad de la UI antigua.
        price_uf=list_uf,
        price_clp=list_clp,
        list_price_uf=list_uf,
        list_price_clp=list_clp,
        offer_price_uf=offer_uf,
        offer_price_clp=offer_clp,
        has_offer=has_offer,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        parking_spots=parking,
        storage_units=storage,
        square_meters_useful=sqm_useful,
        square_meters_total=sqm_total,
        floor_number=floor_number,
        total_floors=total_floors,
        orientation=random.choice(_ORIENTATIONS),
        year_built=random.randint(2005, 2025),
        description=description,
        highlights=highlights,
        amenities=amenities,
        nearby_places=nearby,
        financing_options=financing,
        common_expenses_clp=random.randint(80_000, 350_000) if ptype != "casa" else None,
        subsidio_eligible=subsidio,
    )


def generate_random_properties(broker_id: int, count: int = 10) -> List[Property]:
    """Genera una lista de N propiedades aleatorias (no persiste)."""
    return [generate_random_property(broker_id) for _ in range(count)]


# ── Project demo data ────────────────────────────────────────────────────────

_PROJECT_NAME_PREFIXES = ["Edificio", "Condominio", "Torre", "Residencial", "Mirador"]
_PROJECT_NAME_THEMES = [
    "Andes", "Cordillera", "Parque", "Plaza", "Norte", "Vista", "Alameda",
    "Pacífico", "Aurora", "Sol Naciente", "Las Camelias", "Los Robles",
]
_DEVELOPERS = [
    "Inmobiliaria Aconcagua", "Constructora Pacal", "Inmobiliaria Manquehue",
    "Echeverría Izquierdo", "Inmobiliaria Numancia", "Inmobiliaria Aitué",
]
_PROJECT_STATUSES = ["en_blanco", "en_construccion", "en_venta", "entrega_inmediata"]


def generate_random_project(broker_id: int, *, seed: Optional[int] = None) -> Project:
    """Construye (sin persistir) un Project demo coherente."""
    if seed is not None:
        random.seed(seed)

    loc = random.choice(_COMMUNES_RM)
    name = (
        f"{random.choice(_PROJECT_NAME_PREFIXES)} {random.choice(_PROJECT_NAME_THEMES)} "
        f"{loc['commune']}"
    )
    # uuid sufijo evita colisiones con UniqueConstraint(broker_id, code)
    # cuando se llama "Generar demo" varias veces sobre el mismo broker.
    code = f"PRJ-{uuid.uuid4().hex[:8].upper()}"
    status = random.choice(_PROJECT_STATUSES)
    total_units = random.randint(40, 200)
    available_units = (
        total_units
        if status in ("en_blanco", "en_construccion")
        else random.randint(int(total_units * 0.2), total_units)
    )
    common_amenities = random.sample(_AMENITIES_POOL, k=random.randint(4, 8))
    description = (
        f"Proyecto residencial en {loc['commune']}, {total_units} departamentos, "
        f"con amenities premium y excelente conectividad. "
        f"Estado actual: {status.replace('_', ' ')}."
    )
    return Project(
        broker_id=broker_id,
        name=name,
        code=code,
        description=description,
        developer=random.choice(_DEVELOPERS),
        status=status,
        commune=loc["commune"],
        city=loc["city"],
        region=loc["region"],
        address=f"{random.choice(_STREET_NAMES)} {random.randint(100, 9999)}, {loc['commune']}",
        total_units=total_units,
        available_units=available_units,
        common_amenities=common_amenities,
        financing_options=random.choice(_FINANCING_OPTIONS_POOL),
        subsidio_eligible=random.random() < 0.4,
        highlights=random.choice(_HIGHLIGHTS_POOL),
    )


def generate_random_projects(broker_id: int, count: int = 3) -> List[Project]:
    return [generate_random_project(broker_id) for _ in range(count)]
