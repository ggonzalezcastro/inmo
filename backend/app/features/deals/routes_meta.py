from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.services.deals.slots import SLOT_DEFINITIONS, get_required_slots_for_stage

router = APIRouter(prefix="/api/deals", tags=["deals"])

@router.get("/_meta/slots")
async def get_slots_meta(delivery_type: str = Query(default="desconocida")):
    """
    Returns all slot definitions, optionally filtered/annotated by delivery_type.
    Response is cacheable — max-age 1 hour.
    """
    slots = []
    for key, defn in SLOT_DEFINITIONS.items():
        # Determine if this slot is required given the delivery_type
        required = not defn.optional
        if defn.delivery_type_filter and defn.delivery_type_filter != delivery_type:
            required = False

        slots.append({
            "key": key,
            "label": defn.label,
            "required_for_stage": defn.required_for_stage,
            "max_count": defn.max_count,
            "supports_co_titular": defn.supports_co_titular,
            "optional": defn.optional,
            "required": required,
            "mime_whitelist": list(defn.mime_whitelist),
            "delivery_type_filter": defn.delivery_type_filter,
        })

    response = JSONResponse(content={"slots": slots, "delivery_type": delivery_type})
    response.headers["Cache-Control"] = "max-age=3600, public"
    return response
