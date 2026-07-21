"""integrations/calendar_tools.py — Google Calendar stub. Faz 4'te aktif olacak."""
_STUB_MSG = "Takvim entegrasyonu Faz 4'te implemente edilecek."

def calendar_list_events(date_range: str | None = None) -> dict: raise NotImplementedError(_STUB_MSG)
def calendar_add_event(title: str, date: str, time: str, meeting_link: str | None = None) -> dict: raise NotImplementedError(_STUB_MSG)
def calendar_delete_event(id: str) -> dict: raise NotImplementedError(_STUB_MSG)
