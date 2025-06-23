import os, stripe, logging
from typing import Dict, Any

log = logging.getLogger(__name__)

stripe.api_key      = os.getenv("STRIPE_SECRET_KEY")
PUBLISHABLE_KEY     = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_VERSION      = "2023-10-16"
stripe.api_version  = STRIPE_VERSION
CURRENCY            = os.getenv("STRIPE_CURRENCY", "PEN")

if not stripe.api_key or not PUBLISHABLE_KEY:
    raise RuntimeError("Faltan STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY en env")

def _get_or_create_customer(email: str | None = None) -> stripe.Customer:
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

def generar_payment_sheet(amount_cents: int, email: str | None = None) -> Dict[str, Any]:
    if amount_cents < 50:
        raise ValueError("Importe demasiado pequeño para Stripe")

    customer = _get_or_create_customer(email)

    ekey = stripe.EphemeralKey.create(
        customer=customer.id,
        stripe_version=STRIPE_VERSION,
    )

    intent = stripe.PaymentIntent.create(
        customer=customer.id,
        amount=amount_cents,
        currency=CURRENCY,
        automatic_payment_methods={"enabled": True},
        metadata={"source": "manga-store"},
    )

    log.debug(
        "PI %s / Customer %s creado (%s %s)",
        intent.id,
        customer.id,
        amount_cents,
        CURRENCY,
    )

    return {
        "publishableKey": PUBLISHABLE_KEY,
        "customer":       customer.id,
        "ephemeralKey":   ekey.secret,
        "paymentIntent":  intent.client_secret,
    }
