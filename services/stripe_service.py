# services/stripe_service.py

import os
import stripe
import logging
from typing import Dict, Any
import db.database as db  # Ajusta el import según tu estructura de proyecto
import uuid

log = logging.getLogger(__name__)

# Configuración de Stripe desde variables de entorno
stripe.api_key      = os.getenv("STRIPE_SECRET_KEY")
PUBLISHABLE_KEY     = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_VERSION      = "2023-10-16"
stripe.api_version  = STRIPE_VERSION
CURRENCY            = os.getenv("STRIPE_CURRENCY", "PEN")

if not stripe.api_key or not PUBLISHABLE_KEY:
    raise RuntimeError("Faltan STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY en env")


def _get_or_create_customer(email: str | None = None) -> stripe.Customer:
    """
    Busca un Customer de Stripe por metadata['app_email'], o lo crea si no existe.
    """
    if email:
        customers = stripe.Customer.search(
            query=f"metadata['app_email']:'{email}'",
            limit=1,
        )
        if customers.data:
            return customers.data[0]

    return stripe.Customer.create(
        email=email,
        metadata={"app_email": email or ""},
    )


def crear_devolucion(payment_intent_id: str, amount_cents: int) -> stripe.Refund:
    """
    Crea un reembolso en Stripe para el PaymentIntent dado.
    - payment_intent_id: el ID que guardaste en venta.stripe_pi_id
    - amount_cents: monto a reembolsar en céntimos
    """
    refund = stripe.Refund.create(
        payment_intent=payment_intent_id,
        amount=amount_cents,
        idempotency_key=str(uuid.uuid4())
    )
    log.debug("Refund %s creado para PI %s (%s céntimos)", refund.id, payment_intent_id, amount_cents)
    return refund

def _save_stripe_pi(order_id: int, pi_id: str) -> None:
    """
    Guarda el ID del PaymentIntent en la fila correspondiente de la tabla 'venta'.
    """
    with db.obtener_conexion() as cn, cn.cursor() as cur:
        cur.execute(
            "UPDATE venta SET stripe_pi_id = %s WHERE id_ven = %s",
            (pi_id, order_id)
        )
        cn.commit()


def generar_payment_sheet(
    amount_cents: int,
    order_id:    int,
    email:       str | None = None
) -> Dict[str, Any]:
    """
    Crea un PaymentIntent y una EphemeralKey para la PaymentSheet.
    - amount_cents: monto en céntimos (>=50).
    - email: email del usuario (para Customer).
    - order_id: id_ven de la venta preliminar en tu BD.
    """
    if amount_cents < 50:
        raise ValueError("Importe demasiado pequeño para Stripe")
    if order_id is None:
        raise ValueError("Falta order_id para vincular la venta")

    # 1) Obtiene o crea el Customer
    customer = _get_or_create_customer(email)

    # 2) Ephemeral Key para Android/iOS SDK
    ekey = stripe.EphemeralKey.create(
        customer=customer.id,
        stripe_version=STRIPE_VERSION,
    )

    # 3) Crea el PaymentIntent con metadata.order_id
    intent = stripe.PaymentIntent.create(
        customer=customer.id,
        amount=amount_cents,
        currency=CURRENCY,
        automatic_payment_methods={"enabled": True},
        metadata={"order_id": order_id},
    )

    # 4) Guarda el payment_intent_id en la fila de 'venta'
    _save_stripe_pi(order_id, intent.id)

    log.debug(
        "PI %s / Customer %s creado para order %s (%s %s)",
        intent.id, customer.id, order_id, amount_cents, CURRENCY
    )

    # 5) Devuelve los datos que el cliente móvil necesita
    return {
        "publishableKey": PUBLISHABLE_KEY,
        "customer":       customer.id,
        "ephemeralKey":   ekey.secret,
        "paymentIntent":  intent.client_secret,
    }

