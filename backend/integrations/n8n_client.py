"""integrations/n8n_client.py — n8n webhook client stub. Faz 4'te aktif olacak."""

from core.logger import get_logger
logger = get_logger(__name__)

_STUB_MSG = "n8n entegrasyonu Faz 4'te implemente edilecek."


def call_webhook(workflow_name: str, payload: dict) -> dict:
    """n8n webhook çağırır. Faz 4'te aktif olacak."""
    raise NotImplementedError(_STUB_MSG)
