"""
Payments router — Transbank Webpay Plus reservation payments.

Endpoints:
  POST /api/deals/{deal_id}/payment-link  — create a Webpay transaction, return a shareable link (auth)
  GET  /api/deals/{deal_id}/payments      — list payments for a deal (auth)
  GET  /pay/{buy_order}                    — public: auto-submit form that redirects the buyer to Webpay
  GET|POST /webhooks/transbank/return      — public: Webpay return URL; commits and advances the deal
"""
from __future__ import annotations

import html
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.permissions import Permissions
from app.models.deal import Deal
from app.models.payment import Payment
from app.schemas.payment import PaymentLinkCreate, PaymentLinkResponse, PaymentRead
from app.services.deals.effects import apply_transition_effects
from app.services.deals.exceptions import DealError
from app.services.deals.service import DealService
from app.services.deals.state_machine import transition
from app.services.payments.transbank.service import PaymentProviderError, TransbankService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["payments"])


def _backend_base_url(request: Request) -> str:
    """Public base URL of this backend for building Webpay return + pay links."""
    base = getattr(settings, "WEBHOOK_BASE_URL", None)
    if base:
        return base.rstrip("/")
    return str(request.base_url).rstrip("/")


def _fmt_clp(amount: int | None) -> str:
    if amount is None:
        return "—"
    return "$" + f"{int(amount):,}".replace(",", ".")


def _result_page(status: str, payment: Optional[Payment] = None) -> str:
    """
    Public HTML page shown to the BUYER after returning from Webpay.

    The buyer has no system access, so we render a self-contained result page
    (not the internal SPA). On success it doubles as a receipt.
    """
    themes = {
        "success": ("#16a34a", "✓", "¡Pago aprobado!",
                    "Tu reserva fue pagada correctamente. Guarda este comprobante."),
        "failed":  ("#dc2626", "✕", "El pago no se pudo completar",
                    "No se realizó ningún cobro. Solicita un nuevo link de pago a tu ejecutivo."),
        "aborted": ("#ea580c", "!", "Pago anulado",
                    "Anulaste el pago y no se realizó ningún cobro. Si fue un error, solicita un nuevo link."),
    }
    color, icon, title, subtitle = themes.get(status, themes["failed"])

    receipt_html = ""
    if status == "success" and payment is not None:
        tx_date = payment.transaction_date or ""
        try:
            tx_date = datetime.fromisoformat(tx_date).strftime("%d-%m-%Y %H:%M") if tx_date else "—"
        except Exception:
            tx_date = payment.transaction_date or "—"
        rows = [
            ("Monto", _fmt_clp(payment.amount)),
            ("Código de autorización", payment.authorization_code or "—"),
            ("Tarjeta", f"•••• {payment.card_last4}" if payment.card_last4 else "—"),
            ("Orden de compra", payment.buy_order),
            ("Fecha", tx_date),
        ]
        cells = "".join(
            f'<div class="row"><span class="k">{html.escape(k)}</span>'
            f'<span class="v">{html.escape(str(v))}</span></div>'
            for k, v in rows
        )
        receipt_html = f'<div class="receipt">{cells}</div>'

    return f"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
        background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
        color:#0f172a;padding:24px}}
  .card{{background:#fff;border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,.08);
         max-width:440px;width:100%;padding:32px 28px;text-align:center}}
  .badge{{width:72px;height:72px;border-radius:50%;display:flex;align-items:center;justify-content:center;
          margin:0 auto 20px;font-size:38px;font-weight:700;color:#fff;background:{color}}}
  h1{{font-size:22px;margin:0 0 8px}}
  p.sub{{color:#64748b;font-size:15px;line-height:1.5;margin:0 0 20px}}
  .receipt{{text-align:left;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;margin-top:8px}}
  .row{{display:flex;justify-content:space-between;gap:12px;padding:11px 14px;border-top:1px solid #f1f5f9}}
  .row:first-child{{border-top:none}}
  .k{{color:#64748b;font-size:13px}}
  .v{{font-weight:600;font-size:14px;text-align:right;word-break:break-all}}
  .foot{{margin-top:22px;color:#94a3b8;font-size:12px}}
</style></head>
<body>
  <div class="card">
    <div class="badge">{icon}</div>
    <h1>{html.escape(title)}</h1>
    <p class="sub">{html.escape(subtitle)}</p>
    {receipt_html}
    <p class="foot">Puedes cerrar esta ventana.</p>
  </div>
</body></html>"""


# ── POST /api/deals/{deal_id}/payment-link ───────────────────────────────────

@router.post("/api/deals/{deal_id}/payment-link", response_model=PaymentLinkResponse)
async def create_payment_link(
    deal_id: int,
    body: PaymentLinkCreate,
    request: Request,
    current_user: dict = Depends(Permissions.require_write_access),
    db: AsyncSession = Depends(get_db),
):
    broker_id: int = current_user["broker_id"]
    _raw_uid = current_user.get("id") or current_user.get("user_id")
    user_id: Optional[int] = int(_raw_uid) if _raw_uid is not None else None

    try:
        deal = await DealService.get(db, deal_id=deal_id, broker_id=broker_id)
    except DealError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    if deal.stage != "draft":
        raise HTTPException(
            status_code=422,
            detail="Solo se puede generar un link de pago para un negocio en etapa 'draft'.",
        )

    # Reject if this deal already has an approved payment (avoid double charge).
    approved = await db.execute(
        select(Payment.id).where(
            Payment.deal_id == deal_id, Payment.status == "approved"
        )
    )
    if approved.first():
        raise HTTPException(
            status_code=409,
            detail="Este negocio ya tiene un pago aprobado.",
        )

    # Supersede any still-payable link so only one active link exists at a time.
    await db.execute(
        sa_update(Payment)
        .where(
            Payment.deal_id == deal_id,
            Payment.status.in_(["created", "pending"]),
        )
        .values(status="cancelled")
    )

    # buy_order must be <= 26 chars and unique per commerce.
    buy_order = f"d{deal_id}-{uuid.uuid4().hex[:12]}"[:26]
    session_id = f"deal-{deal_id}-b{broker_id}"[:61]
    return_url = f"{_backend_base_url(request)}/webhooks/transbank/return"

    try:
        service = await TransbankService.for_broker(db, broker_id)
        resp = await service.create_transaction(
            buy_order=buy_order,
            session_id=session_id,
            amount=body.amount,
            return_url=return_url,
        )
    except PaymentProviderError as e:
        logger.error("[Payments] create_transaction failed for deal %s: %s", deal_id, e.message)
        raise HTTPException(status_code=502, detail="No se pudo crear la transacción en Transbank.")

    token = resp.get("token")
    webpay_url = resp.get("url")
    if not token or not webpay_url:
        raise HTTPException(status_code=502, detail="Respuesta inválida de Transbank.")

    payment = Payment(
        broker_id=broker_id,
        deal_id=deal_id,
        created_by_user_id=user_id,
        provider="transbank",
        environment=service.environment,
        buy_order=buy_order,
        session_id=session_id,
        amount=body.amount,
        token=token,
        webpay_url=webpay_url,
        status="created",
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    pay_url = f"{_backend_base_url(request)}/pay/{buy_order}"
    return PaymentLinkResponse(
        payment_id=payment.id,
        deal_id=deal_id,
        buy_order=buy_order,
        amount=payment.amount,
        status=payment.status,
        pay_url=pay_url,
        environment=payment.environment,
    )


# ── GET /api/deals/{deal_id}/payments ────────────────────────────────────────

@router.get("/api/deals/{deal_id}/payments", response_model=list[PaymentRead])
async def list_deal_payments(
    deal_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    broker_id: int = current_user["broker_id"]
    result = await db.execute(
        select(Payment)
        .where(Payment.deal_id == deal_id, Payment.broker_id == broker_id)
        .order_by(Payment.created_at.desc())
    )
    base = _backend_base_url(request)
    out: list[PaymentRead] = []
    for p in result.scalars().all():
        item = PaymentRead.model_validate(p)
        # Only still-payable links are worth (re)sharing.
        if p.status in ("created", "pending"):
            item.pay_url = f"{base}/pay/{p.buy_order}"
        out.append(item)
    return out


# ── POST /api/deals/{deal_id}/payments/{payment_id}/cancel ───────────────────

@router.post("/api/deals/{deal_id}/payments/{payment_id}/cancel", response_model=PaymentRead)
async def cancel_payment(
    deal_id: int,
    payment_id: int,
    current_user: dict = Depends(Permissions.require_write_access),
    db: AsyncSession = Depends(get_db),
):
    broker_id: int = current_user["broker_id"]
    result = await db.execute(
        select(Payment).where(
            Payment.id == payment_id,
            Payment.deal_id == deal_id,
            Payment.broker_id == broker_id,
        )
    )
    payment = result.scalars().first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado.")
    if payment.status == "approved":
        raise HTTPException(status_code=409, detail="No se puede anular un pago aprobado.")
    if payment.status in ("created", "pending"):
        payment.status = "cancelled"
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
    return PaymentRead.model_validate(payment)


# ── GET /pay/{buy_order} — public redirect-to-Webpay page ────────────────────

@router.get("/pay/{buy_order}", response_class=HTMLResponse)
async def pay_redirect(buy_order: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Payment).where(Payment.buy_order == buy_order))
    payment = result.scalars().first()
    if payment is None or not payment.token or not payment.webpay_url:
        raise HTTPException(status_code=404, detail="Link de pago no encontrado.")

    if payment.status == "approved":
        return HTMLResponse(
            "<p style='font-family:sans-serif;text-align:center;padding:3rem'>"
            "Este pago ya fue realizado.</p>",
            status_code=200,
        )

    # Superseded/cancelled/failed/aborted links must not be payable anymore.
    if payment.status not in ("created", "pending"):
        return HTMLResponse(
            "<p style='font-family:sans-serif;text-align:center;padding:3rem'>"
            "Este link de pago ya no está disponible. Solicita uno nuevo al ejecutivo.</p>",
            status_code=200,
        )

    if payment.status == "created":
        payment.status = "pending"
        db.add(payment)
        await db.commit()

    token = html.escape(payment.token)
    action = html.escape(payment.webpay_url)
    page = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Redirigiendo a Webpay…</title></head>
<body onload="document.forms[0].submit()" style="font-family:sans-serif;text-align:center;padding:3rem">
<form method="post" action="{action}">
<input type="hidden" name="token_ws" value="{token}"/>
<noscript><button type="submit">Continuar al pago</button></noscript>
</form>
<p>Redirigiendo a Webpay para completar el pago…</p>
</body></html>"""
    return HTMLResponse(content=page, status_code=200)


# ── GET|POST /webhooks/transbank/return — Webpay return URL ───────────────────

@router.api_route("/webhooks/transbank/return", methods=["GET", "POST"])
async def transbank_return(request: Request, db: AsyncSession = Depends(get_db)):
    # Webpay may send params via query (GET) or form body (POST).
    params: dict = dict(request.query_params)
    if request.method == "POST":
        try:
            form = await request.form()
            params.update({k: v for k, v in form.items()})
        except Exception:  # pragma: no cover - defensive
            pass

    token_ws = params.get("token_ws")
    tbk_token = params.get("TBK_TOKEN")

    # Buyer aborted/cancelled at Webpay: no commit, mark aborted.
    if not token_ws and tbk_token:
        result = await db.execute(select(Payment).where(Payment.token == tbk_token))
        payment = result.scalars().first()
        if payment and payment.status not in ("approved",):
            payment.status = "aborted"
            db.add(payment)
            await db.commit()
        return HTMLResponse(_result_page("aborted", payment))

    if not token_ws:
        raise HTTPException(status_code=400, detail="Falta token_ws.")

    result = await db.execute(select(Payment).where(Payment.token == token_ws))
    payment = result.scalars().first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado.")

    # Idempotency: if already committed, don't re-commit (Webpay would error).
    if payment.status == "approved":
        return HTMLResponse(_result_page("success", payment))
    if payment.status in ("failed", "aborted", "cancelled"):
        return HTMLResponse(_result_page("failed", payment))

    try:
        service = await TransbankService.for_broker(db, payment.broker_id)
        commit_resp = await service.commit_transaction(token_ws)
    except PaymentProviderError as e:
        logger.error("[Payments] commit failed for payment %s: %s", payment.id, e.message)
        payment.status = "error"
        db.add(payment)
        await db.commit()
        return HTMLResponse(_result_page("failed", payment))

    response_code = commit_resp.get("response_code")
    tx_status = commit_resp.get("status")
    approved = response_code == 0 and tx_status == "AUTHORIZED"

    # Defense-in-depth: the committed amount must match what we created the
    # transaction with. A mismatch means tampering or a Transbank inconsistency;
    # never advance the deal in that case.
    committed_amount = commit_resp.get("amount")
    if approved and committed_amount is not None and int(committed_amount) != int(payment.amount):
        logger.error(
            "[Payments] amount mismatch on payment %s: committed=%s expected=%s — rejecting",
            payment.id, committed_amount, payment.amount,
        )
        approved = False

    card_detail = commit_resp.get("card_detail") or {}
    payment.response_code = response_code
    payment.authorization_code = commit_resp.get("authorization_code")
    payment.payment_type_code = commit_resp.get("payment_type_code")
    payment.installments_number = commit_resp.get("installments_number")
    payment.card_last4 = (card_detail.get("card_number") or None)
    payment.transaction_date = str(commit_resp.get("transaction_date") or "") or None
    payment.raw_response = commit_resp
    payment.committed_at = datetime.now(timezone.utc)
    payment.status = "approved" if approved else "failed"
    db.add(payment)

    if not approved:
        await db.commit()
        return HTMLResponse(_result_page("failed", payment))

    # Approved — advance the deal draft → reserva (idempotent).
    await db.flush()  # ensure the approved Payment is visible to the guard query
    deal = await db.get(Deal, payment.deal_id)
    if deal is not None and deal.stage == "draft":
        try:
            from_stage = deal.stage
            await transition(deal, "reserva", db)
            await apply_transition_effects(
                deal, from_stage, "reserva", db, actor_user_id=payment.created_by_user_id
            )
        except DealError as e:
            # Payment stays approved; log but don't fail the buyer's result page.
            logger.error(
                "[Payments] payment %s approved but deal %s transition failed: %s",
                payment.id, payment.deal_id, e.message,
            )

    await db.commit()
    return HTMLResponse(_result_page("success", payment))
