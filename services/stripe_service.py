# # services/stripe_service.py
# # ──────────────────────────────────────────────────────────────────────────────
# #  Wrapper minimal (pero robusto) para crear el “Payment Sheet” que usa la
# #  aplicación Android.  Devuelve:
# #
# #  {
# #      "publishableKey": "pk_test_…",
# #      "customer":       "cus_…",
# #      "ephemeralKey":   "ek_test_…",
# #      "paymentIntent":  "pi_…_secret_…"
# #  }
# #
# #  La app lo llama con:
# #      POST /payment-sheet     JSON: { "amount_cents": 12345, "email": "u@d.com" }
# #  y luego construye PaymentSheet con esos campos.
# # ──────────────────────────────────────────────────────────────────────────────
# from __future__ import annotations

# import os, stripe, logging
# from typing import Dict, Any

# log = logging.getLogger(__name__)

# # ─── Config global (variables de entorno) ─────────────────────────────────────
# stripe.api_key      = os.getenv("STRIPE_SECRET_KEY")            # sk_test_…
# PUBLISHABLE_KEY     = os.getenv("STRIPE_PUBLISHABLE_KEY")       # pk_test_…
# STRIPE_VERSION      = "2023-10-16"                              # versión estable
# CURRENCY            = os.getenv("STRIPE_CURRENCY", "usd")       # p.e. “pen”

# if not stripe.api_key or not PUBLISHABLE_KEY:
#     raise RuntimeError("Faltan STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY en env")


# # ─── Helpers internos ─────────────────────────────────────────────────────────
# def _get_or_create_customer(email: str | None = None) -> stripe.Customer:
#     """
#     Busca (o crea) un Customer de Stripe.  Si se proporciona *email*, intenta
#     reutilizar; en otro caso genera uno anónimo.
#     """
#     if email:
#         # Usamos metadata para no depender 100 % de la búsqueda por email
#         customers = stripe.Customer.search(
#             query=f"metadata['app_email']:'{email}'",
#             limit=1,
#         )
#         if customers.data:
#             return customers.data[0]

#     # Crear uno nuevo
#     return stripe.Customer.create(
#         email=email,
#         metadata={"app_email": email or ""},
#     )


# # ─── API principal ────────────────────────────────────────────────────────────
# def generar_payment_sheet(amount_cents: int, email: str | None = None) -> Dict[str, Any]:
#     """
#     ▸ *amount_cents*  Importe total en céntimos (p.e. 499 → 4,99 USD/PEN).
#     ▸ *email*         (opcional) Asociar cliente a ese correo.

#     Devuelve los campos necesarios para Stripe PaymentSheet.
#     """
#     if amount_cents < 50:  # mínimo 0.50 u.m.
#         raise ValueError("Importe demasiado pequeño para Stripe")

#     # 1) Customer
#     customer = _get_or_create_customer(email)

#     # 2) Ephemeral Key (para PaymentSheet)
#     ekey = stripe.EphemeralKey.create(
#         customer=customer.id,
#         stripe_version=STRIPE_VERSION,
#     )

#     # 3) PaymentIntent
#     intent = stripe.PaymentIntent.create(
#         customer              = customer.id,
#         amount                = amount_cents,
#         currency              = CURRENCY,
#         automatic_payment_methods={"enabled": True},
#         metadata={"source": "manga-store"},
#     )

#     log.debug("PI %s / Customer %s creado (%s %s)",
#               intent.id, customer.id, amount_cents, CURRENCY)

#     return {
#         "publishableKey": PUBLISHABLE_KEY,
#         "customer":       customer.id,
#         "ephemeralKey":   ekey.secret,
#         "paymentIntent":  intent.client_secret,
#     }


# # ─── Atajo para Flask route opcional ──────────────────────────────────────────
# #
# #   from services.stripe_service import generar_payment_sheet
# #
# #   @app.route("/payment-sheet", methods=["POST"])
# #   @jwt_required()                           # o la protección que uses
# #   def api_payment_sheet():
# #       data  = request.get_json(force=True)
# #       total = int(data.get("amount_cents", 0))
# #       email = get_jwt_identity()            #  ← o data["email"]
# #       try:
# #           payload = generar_payment_sheet(total, email)
# #           return jsonify(payload), 200
# #       except Exception as exc:
# #           log.exception("Stripe error")
# #           return jsonify(msg=str(exc)), 400
# #
# # (No incluimos la ruta en el servicio para mantener la separación lógica)
