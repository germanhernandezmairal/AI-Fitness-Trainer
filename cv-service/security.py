"""Autenticación del servicio CV: valida la API key de las peticiones entrantes
y firma los webhooks salientes para que el backend pueda verificar su origen.
"""

import hashlib
import hmac
import os

API_KEY = os.environ.get("CV_API_KEY", "dev-cv-api-key")
WEBHOOK_SECRET = os.environ.get(
    "CV_WEBHOOK_SECRET", "dev-webhook-secret-change-me-in-production"
)


def check_api_key(provided: str | None) -> bool:
    """Compara la API key recibida en el header X-API-Key contra la configurada."""
    return provided == API_KEY


def sign_webhook(body: bytes, timestamp: str) -> str:
    """Firma el cuerpo del webhook con HMAC-SHA256, igual que espera el backend.

    La firma cubre "timestamp + '.' + body" para que el backend pueda rechazar
    mensajes reenviados fuera de su ventana de tolerancia (protección anti-replay).
    """
    message = f"{timestamp}.".encode() + body
    return hmac.new(WEBHOOK_SECRET.encode(), message, hashlib.sha256).hexdigest()