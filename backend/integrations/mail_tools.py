"""integrations/mail_tools.py — Gmail entegrasyonu stub. Faz 4'te aktif olacak."""
_STUB_MSG = "Mail entegrasyonu Faz 4'te implemente edilecek."

def mail_read_inbox(count: int = 5) -> dict: raise NotImplementedError(_STUB_MSG)
def mail_send(to: str, subject: str, body: str) -> dict: raise NotImplementedError(_STUB_MSG)
def mail_extract_meeting(mail_id: str) -> dict: raise NotImplementedError(_STUB_MSG)
