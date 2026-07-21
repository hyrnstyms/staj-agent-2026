"""
mcp_servers/app_server.py
-------------------------
Uygulama MCP Server — FAZ 5'te tam implementasyon yapılacak.
"""

from core.logger import get_logger

logger = get_logger(__name__)
_STUB_MSG = "Uygulama server'ı Faz 5'te implemente edilecek."


class AppServer:
    def app_open(self, name: str) -> dict:
        raise NotImplementedError(_STUB_MSG)

    def app_close(self, name: str) -> dict:
        raise NotImplementedError(_STUB_MSG)

    def app_list_running(self) -> dict:
        raise NotImplementedError(_STUB_MSG)


app_server = AppServer()
