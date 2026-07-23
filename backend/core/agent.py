"""
core/agent.py
-------------
Ana Agent Loop.

Konuşma akışı:
    1. Kullanıcı mesajını geçmişe ekle
    2. Router (2 aşamalı) → kategori + tool + parametre
    3. Genel sohbetse → doğrudan LLM cevabı üret
    4. Tool seçildiyse:
       a. tool_executor.execute() → izin + onay kontrolü
       b. pending_approval dönerse → kullanıcıya onay bekle mesajı döner
       c. Tool çalışırsa → sonuç geçmişe eklenir, LLM cevap üretir
    5. Her adım loglanır

Kullanım:
    from core.agent import Agent

    agent = Agent()
    response = await agent.chat(
        session_id="abc123",
        message="README.md dosyasını oku",
        user_id=1,
        user_role="employee",
        db=db,
    )
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx

from config import settings
from core.approval import approval_manager
from core.logger import get_logger
from core.memory import conversation_memory
from core.router import CategoryRouter
from core.tool_executor import ExecutionResult, tool_executor

logger = get_logger(__name__)

SYSTEM_PROMPT = """Sen yerel çalışan bir AI asistanısın. Kullanıcıya Türkçe olarak yardım edersin.
SİSTEME TAM ERİŞİMİN VARDIR (FULL ACCESS). Dosya sistemi, veritabanı, kod çalıştırma ve uygulamaları yönetebilirsin.
Asla "Ben bir yapay zekayım, dosyalara erişemem" veya benzeri ret (refusal) cümleleri kurma. Sana sağlanan fonksiyonları/araçları (tools) KESİNLİKLE KULLANMALISIN.
Geri döndürülemez işlemler için onay mekanizması zaten arka planda mevcuttur. Sadece araçları çağır.
Cevaplarını kısa, net ve Türkçe yaz."""


@dataclass
class AgentResponse:
    """
    Agent'ın bir konuşma turuna verdiği yanıt.

    Attributes:
        message        : Kullanıcıya gösterilecek metin
        status         : "success" | "pending_approval" | "error" | "tool_error"
        tool_name      : Çalıştırılan tool adı (varsa)
        tool_result    : Tool'un döndürdüğü veri (varsa)
        approval_id    : Onay bekleme durumunda atanan ID
        category       : Router'ın seçtiği kategori
        phase1_success : Kategori seçimi başarılı mıydı?
        phase2_success : Tool seçimi başarılı mıydı?
    """

    message: str
    status: str
    tool_name: str | None = None
    tool_result: Any = None
    approval_id: str | None = None
    category: str | None = None
    phase1_success: bool = True
    phase2_success: bool = True


class Agent:
    """
    Ana agent sınıfı.

    Her chat() çağrısı tam bir konuşma turunu gerçekleştirir:
    Router → izin/onay → tool yürütme → LLM cevabı.
    """

    def __init__(self) -> None:
        self._router = CategoryRouter()
        self._base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self._model = settings.OLLAMA_MODEL
        self._timeout = settings.OLLAMA_TIMEOUT

    # ── Public API ────────────────────────────────────────────────────────────

    async def chat(
        self,
        *,
        session_id: str,
        message: str,
        user_id: int | None,
        user_role: str,
        db: Any,
        approval_id: str | None = None,
    ) -> AgentResponse:
        """
        Tek bir konuşma turunu işler.

        Args:
            session_id : Oturum kimliği
            message    : Kullanıcının mesajı
            user_id    : Kullanıcı ID'si
            user_role  : Kullanıcının rolü
            db         : SQLAlchemy session
            approval_id: Önceki onay isteği ID'si (kullanıcı onayladıysa)

        Returns:
            AgentResponse
        """
        logger.info(
            "Agent.chat başlıyor",
            extra={
                "session": session_id,
                "user_id": user_id,
                "role": user_role,
                "message_preview": message[:80],
                "has_approval": approval_id is not None,
            },
        )

        # Oturuma sistem mesajı ekle (ilk mesajsa)
        if conversation_memory.message_count(session_id) == 0:
            conversation_memory.add_message(session_id, "system", SYSTEM_PROMPT)

        # Kullanıcı mesajını geçmişe ekle
        conversation_memory.add_message(session_id, "user", message)
        history = conversation_memory.get_history(session_id, as_dicts=True)

        # ── Onay dönüşü mü? ───────────────────────────────────────────────────
        if approval_id is not None:
            return await self._handle_approval_continuation(
                session_id=session_id,
                message=message,
                user_id=user_id,
                user_role=user_role,
                db=db,
                approval_id=approval_id,
                history=history,
            )

        # ── Router: kategori + tool seçimi ────────────────────────────────────
        try:
            router_result = await self._router.route(message=message, history=history[:-1])
        except Exception as exc:
            logger.error(f"Router hatası: {exc}", exc_info=True)
            return AgentResponse(
                message=f"Üzgünüm, isteğinizi işlerken bir hata oluştu: {exc}",
                status="error",
            )

        # ── Genel sohbet ──────────────────────────────────────────────────────
        if router_result.is_general_chat or router_result.tool_name is None:
            llm_response = await self._llm_chat(history)
            conversation_memory.add_message(session_id, "assistant", llm_response)
            return AgentResponse(
                message=llm_response,
                status="success",
                category=router_result.category,
                phase1_success=router_result.phase1_success,
                phase2_success=router_result.phase2_success,
            )

        # ── Tool çalıştırma ───────────────────────────────────────────────────
        exec_result: ExecutionResult = await tool_executor.execute(
            tool_name=router_result.tool_name,
            parameters=router_result.parameters,
            user_id=user_id,
            user_role=user_role,
            session_id=session_id,
            db=db,
            category=router_result.category,
            approval_id=approval_id,
        )

        # Onay bekleniyor
        if exec_result.status == "pending_approval":
            req = approval_manager.get_request(exec_result.approval_id)
            approval_description = req.description if req else "Onay gerekiyor"
            pending_msg = (
                f"{approval_description}\n\n"
                f"Bu işlemi onaylamak için `/approve/{exec_result.approval_id}` "
                f"endpoint'ini çağırın, iptal için `/reject/{exec_result.approval_id}`."
            )
            conversation_memory.add_message(session_id, "assistant", pending_msg)
            return AgentResponse(
                message=pending_msg,
                status="pending_approval",
                tool_name=router_result.tool_name,
                approval_id=exec_result.approval_id,
                category=router_result.category,
                phase1_success=router_result.phase1_success,
                phase2_success=router_result.phase2_success,
            )

        # İzin reddedildi / hata
        if not exec_result.success:
            error_msg = f"İşlem gerçekleştirilemedi: {exec_result.error}"
            conversation_memory.add_message(session_id, "assistant", error_msg)
            return AgentResponse(
                message=error_msg,
                status=exec_result.status,
                tool_name=router_result.tool_name,
                category=router_result.category,
                phase1_success=router_result.phase1_success,
                phase2_success=router_result.phase2_success,
            )

        # Tool başarılı — LLM ile kullanıcı dostu cevap üret
        tool_result_str = json.dumps(exec_result.data, ensure_ascii=False, indent=2, default=str)
        conversation_memory.add_message(
            session_id,
            "tool",
            f"Tool '{router_result.tool_name}' sonucu:\n{tool_result_str}",
            tool_name=router_result.tool_name,
        )

        # Tool sonucuna dayalı kullanıcı dostu cevap oluştur
        synthesis_history = conversation_memory.get_history(session_id, as_dicts=True)
        synthesis_history.append({
            "role": "user",
            "content": (
                f"Yukarıdaki tool sonucunu kullanarak kullanıcının sorusuna "
                f"kısa ve net Türkçe bir cevap ver: {message}"
            ),
        })
        llm_response = await self._llm_chat(synthesis_history)
        conversation_memory.add_message(session_id, "assistant", llm_response)

        return AgentResponse(
            message=llm_response,
            status="success",
            tool_name=router_result.tool_name,
            tool_result=exec_result.data,
            category=router_result.category,
            phase1_success=router_result.phase1_success,
            phase2_success=router_result.phase2_success,
        )

    async def chat_stream(
        self,
        *,
        session_id: str,
        message: str,
        user_id: int | None,
        user_role: str,
        db: Any,
        approval_id: str | None = None,
    ) -> AsyncIterator[str]:
        """
        Streaming chat — token'ları teker teker verir.

        Tool seçimi ve çalıştırma senkron yapılır, yalnızca
        son LLM sentez cevabı stream edilir.

        Yields:
            Token string'leri (Ollama streaming'den)
        """
        # Tool ve router kısmı normal akışla yapılır
        # (streaming olmayan agent response alınır, cevap kısmı stream edilir)
        if conversation_memory.message_count(session_id) == 0:
            conversation_memory.add_message(session_id, "system", SYSTEM_PROMPT)

        conversation_memory.add_message(session_id, "user", message)
        history = conversation_memory.get_history(session_id, as_dicts=True)

        if approval_id is not None:
            response = await self._handle_approval_continuation(
                session_id=session_id,
                message=message,
                user_id=user_id,
                user_role=user_role,
                db=db,
                approval_id=approval_id,
                history=history,
            )
            yield response.message
            return

        try:
            router_result = await self._router.route(message=message, history=history[:-1])
        except Exception as exc:
            yield f"Hata: {exc}"
            return

        if router_result.is_general_chat or router_result.tool_name is None:
            full_response = ""
            async for token in self._llm_stream(history):
                full_response += token
                yield token
            conversation_memory.add_message(session_id, "assistant", full_response)
            return

        # Tool çalıştır (streaming olmayan)
        exec_result = await tool_executor.execute(
            tool_name=router_result.tool_name,
            parameters=router_result.parameters,
            user_id=user_id,
            user_role=user_role,
            session_id=session_id,
            db=db,
            category=router_result.category,
            approval_id=approval_id,
        )

        if exec_result.status == "pending_approval":
            req = approval_manager.get_request(exec_result.approval_id)
            msg = req.description if req else "Onay gerekiyor"
            conversation_memory.add_message(session_id, "assistant", msg)
            yield f"[PENDING_APPROVAL:{exec_result.approval_id}] {msg}"
            return

        if not exec_result.success:
            msg = f"Hata: {exec_result.error}"
            conversation_memory.add_message(session_id, "assistant", msg)
            yield msg
            return

        # Tool başarılı — sonucu stream et
        tool_result_str = json.dumps(exec_result.data, ensure_ascii=False, default=str)
        conversation_memory.add_message(
            session_id, "tool",
            f"Tool '{router_result.tool_name}' sonucu:\n{tool_result_str}",
            tool_name=router_result.tool_name,
        )
        synthesis_history = conversation_memory.get_history(session_id, as_dicts=True)
        synthesis_history.append({
            "role": "user",
            "content": f"Yukarıdaki tool sonucunu kullanarak kısa ve net Türkçe cevap ver: {message}",
        })

        full_response = ""
        async for token in self._llm_stream(synthesis_history):
            full_response += token
            yield token
        conversation_memory.add_message(session_id, "assistant", full_response)

    # ── Onay Devamı ───────────────────────────────────────────────────────────

    async def _handle_approval_continuation(
        self,
        *,
        session_id: str,
        message: str,
        user_id: int | None,
        user_role: str,
        db: Any,
        approval_id: str,
        history: list[dict],
    ) -> AgentResponse:
        """
        Kullanıcı onay verdiğinde çağrılır.
        Bekleyen onay isteğini bulup tool'u çalıştırır.
        """
        req = approval_manager.get_request(approval_id)
        if req is None:
            return AgentResponse(
                message="Onay isteği bulunamadı veya süresi doldu.",
                status="error",
            )

        exec_result = await tool_executor.execute(
            tool_name=req.tool_name,
            parameters=req.parameters,
            user_id=user_id,
            user_role=user_role,
            session_id=session_id,
            db=db,
            approval_id=approval_id,
        )

        if not exec_result.success:
            return AgentResponse(
                message=f"İşlem tamamlanamadı: {exec_result.error}",
                status=exec_result.status,
                tool_name=req.tool_name,
                approval_id=approval_id,
            )

        tool_result_str = json.dumps(exec_result.data, ensure_ascii=False, default=str)
        conversation_memory.add_message(
            session_id, "tool",
            f"Onaylanan işlem '{req.tool_name}' tamamlandı:\n{tool_result_str}",
            tool_name=req.tool_name,
        )
        synthesis_history = conversation_memory.get_history(session_id, as_dicts=True)
        synthesis_history.append({
            "role": "user",
            "content": "İşlem tamamlandı, kullanıcıya kısa bir Türkçe özet ver.",
        })
        llm_response = await self._llm_chat(synthesis_history)
        conversation_memory.add_message(session_id, "assistant", llm_response)

        return AgentResponse(
            message=llm_response,
            status="success",
            tool_name=req.tool_name,
            tool_result=exec_result.data,
            approval_id=approval_id,
        )

    # ── LLM Yardımcıları ─────────────────────────────────────────────────────

    async def _llm_chat(self, messages: list[dict]) -> str:
        """Ollama'dan senkron cevap alır."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.7},
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")

    async def _llm_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """Ollama'dan token'ları teker teker alır."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": 0.7},
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
