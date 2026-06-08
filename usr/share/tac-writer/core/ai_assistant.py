"""
PDF proofreading AI assistant integration for TAC Writer.

The only entry point is request_pdf_review(). The assistant is restricted to
identifying errors in the author's text — it must never write new content.
This design complies with CNPq Portaria nº 2.664/2026, which requires that:
  (1) AI use must be declared, specifying the tool and its purpose;
  (2) AI-generated content must not be presented as human authorship;
  (3) the author remains fully responsible for the final content.
"""

from __future__ import annotations

import logging
import os
import threading
import weakref
from typing import Any, Dict, List

try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

import requests

import gi

gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
from gi.repository import Adw, GLib

from utils.i18n import _


class WritingAiAssistant:
    """Coordinates PDF proofreading requests with an external AI service."""

    DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
    DEFAULT_OPENROUTER_MODEL = "openrouter/polaris-alpha"

    # Complies with CNPq Portaria nº 2.664/2026: the AI is restricted to
    # identifying errors only — it must not rewrite the text or add content.
    # Authors remain fully responsible for the final work.
    _PDF_SYSTEM_PROMPT = (
        "You are an expert proofreader of academic texts in Portuguese. "
        "Your role is STRICTLY LIMITED to identifying and reporting errors — "
        "you must NEVER rewrite the text, suggest alternative phrasings that "
        "add new content, or alter the author's ideas and arguments in any way. "
        "Point out grammatical, orthographic, and semantic errors, words that "
        "are spelled correctly but do not fit the context, and excessive "
        "repetitions within short passages. "
        "For each issue found, indicate the original passage and briefly explain "
        "the problem, without replacing it with new authored text. "
        "At the end of your report, include a note that this AI tool was used "
        "exclusively for proofreading, so the author can fulfill the mandatory "
        "AI use disclosure required by CNPq Portaria nº 2.664/2026. "
        "Present all considerations in Brazilian Portuguese. "
        "Respond only with the proofreading report, without JSON."
    )

    def __init__(self, window, config):
        self._window_ref = weakref.ref(window)
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._inflight = False

    def missing_configuration(self) -> List[str]:
        missing: List[str] = []
        provider = (self.config.get_ai_assistant_provider() or "").strip()
        api_key = (self.config.get_ai_assistant_api_key() or "").strip()
        if not provider:
            missing.append("provider")
            return missing
        if provider in {"gemini", "openrouter"} and not api_key:
            missing.append("api_key")
        return missing

    def handle_setting_changed(self) -> None:
        """Placeholder for future cache invalidation."""
        pass

    # ------------------------------------------------------------------ #
    # Public entry point                                                   #
    # ------------------------------------------------------------------ #

    def request_pdf_review(self, pdf_path: str) -> bool:
        """Read a PDF, extract its text, and send it for proofreading."""
        if not PDF_AVAILABLE:
            self._queue_toast(_("Biblioteca pypdf não instalada."))
            return False

        if not pdf_path or not os.path.exists(pdf_path):
            return False

        with self._lock:
            if self._inflight:
                self._queue_toast(_("O assistente já está processando uma solicitação."))
                return False
            self._inflight = True

        worker = threading.Thread(
            target=self._process_pdf_thread,
            args=(pdf_path,),
            daemon=True,
        )
        worker.start()
        return True

    # ------------------------------------------------------------------ #
    # PDF processing                                                       #
    # ------------------------------------------------------------------ #

    def _process_pdf_thread(self, pdf_path: str) -> None:
        try:
            text_content = self._extract_pdf_text(pdf_path)
            messages = self._build_pdf_messages(text_content)
            config = self._load_configuration()
            content = self._perform_request(config, messages)
            clean_reply = self._clean_response(content)
            GLib.idle_add(self._display_pdf_result, clean_reply)
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.error("AI PDF review failed: %s", exc)
            GLib.idle_add(self._notify_pdf_error, str(exc))
        finally:
            with self._lock:
                self._inflight = False

    def _extract_pdf_text(self, pdf_path: str) -> str:
        text_content = ""
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text_content += extracted + "\n"
        except Exception as exc:
            raise RuntimeError(_("Erro ao ler PDF: {}").format(str(exc))) from exc

        if not text_content.strip():
            raise RuntimeError(
                _("Não foi possível extrair texto do PDF (pode ser uma imagem ou vazio).")
            )
        return text_content

    def _build_pdf_messages(self, text_content: str) -> List[Dict[str, str]]:
        user_prompt = (
            "Examine o texto abaixo e aponte os problemas encontrados, sem reescrever o texto. "
            "Verifique: ortografia, gramática e semântica; palavras que, mesmo escritas corretamente, "
            "não fazem sentido no contexto da frase; repetições excessivas de palavras em trechos "
            "curtos. Para cada problema, indique o trecho original e explique o erro. "
            "Não produza versões corrigidas — apenas aponte os problemas para que o autor faça "
            "as correções. "
            "Não avalie citações diretas, elas são seguidas de parentêses e ano da obra. \n\n"
            "--- INÍCIO DO TEXTO ---\n"
            f"{text_content}\n"
            "--- FIM DO TEXTO ---"
        )
        return [
            {"role": "system", "content": self._PDF_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

    # ------------------------------------------------------------------ #
    # Configuration                                                        #
    # ------------------------------------------------------------------ #

    def _load_configuration(self) -> Dict[str, str]:
        config = {
            "provider": (self.config.get_ai_assistant_provider() or "").strip(),
            "model": (self.config.get_ai_assistant_model() or "").strip(),
            "api_key": (self.config.get_ai_assistant_api_key() or "").strip(),
            "openrouter_site_url": (self.config.get_openrouter_site_url() or "").strip(),
            "openrouter_site_name": (self.config.get_openrouter_site_name() or "").strip(),
        }
        if not config["provider"]:
            raise RuntimeError(
                _("Selecione um provedor de IA em Preferências ▸ Assistente de IA.")
            )
        if config["provider"] == "gemini" and not config["model"]:
            config["model"] = self.DEFAULT_GEMINI_MODEL
        elif config["provider"] == "openrouter" and not config["model"]:
            config["model"] = self.DEFAULT_OPENROUTER_MODEL
        return config

    # ------------------------------------------------------------------ #
    # HTTP requests                                                        #
    # ------------------------------------------------------------------ #

    def _perform_request(
        self, config: Dict[str, str], messages: List[Dict[str, str]]
    ) -> str:
        provider = config["provider"]
        if provider == "gemini":
            return self._perform_gemini_request(config, messages)
        if provider == "openrouter":
            return self._perform_openrouter_request(config, messages)
        raise RuntimeError(
            _("Provider '{provider}' is not supported.").format(provider=provider)
        )

    def _perform_gemini_request(
        self, config: Dict[str, str], messages: List[Dict[str, str]]
    ) -> str:
        api_key = config.get("api_key", "").strip()
        if not api_key:
            raise RuntimeError(_("Configure a chave da API Gemini em Preferências."))

        model = config.get("model", "").strip() or self.DEFAULT_GEMINI_MODEL

        # Convert messages to Gemini format, extracting the system instruction.
        system_instruction = ""
        contents: List[Dict[str, Any]] = []
        for message in messages:
            role = message.get("role", "user")
            text = message.get("content", "")
            if not text:
                continue
            if role == "system" and not system_instruction:
                system_instruction = text
                continue
            mapped_role = "model" if role == "assistant" else "user"
            contents.append({"role": mapped_role, "parts": [{"text": text}]})
        if not contents:
            contents.append({"role": "user", "parts": [{"text": ""}]})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload: Dict[str, Any] = {"contents": contents}
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
        except requests.RequestException as exc:
            raise RuntimeError(
                _("Falha ao contatar Gemini: {error}").format(error=exc)
            ) from exc

        if response.status_code >= 400:
            raise RuntimeError(
                _("Gemini responded with HTTP {status}: {detail}").format(
                    status=response.status_code, detail=response.text.strip()
                )
            )

        try:
            response_data = response.json()
        except ValueError as exc:
            raise RuntimeError(_("Gemini retornou uma resposta JSON inválida.")) from exc

        candidates = response_data.get("candidates") or []
        collected: List[str] = []
        for candidate in candidates:
            content = candidate.get("content") if isinstance(candidate, dict) else None
            parts = content.get("parts") if isinstance(content, dict) else None
            if not parts:
                continue
            for part in parts:
                if isinstance(part, dict) and part.get("text"):
                    collected.append(part["text"])

        if collected:
            return "\n".join(collected)

        raise RuntimeError(_("O Gemini não retornou conteúdo utilizável."))

    def _perform_openrouter_request(
        self, config: Dict[str, str], messages: List[Dict[str, str]]
    ) -> str:
        api_key = config.get("api_key", "").strip()
        if not api_key:
            raise RuntimeError(_("Configure a chave da API OpenRouter em Preferências."))

        model = config.get("model", "").strip() or self.DEFAULT_OPENROUTER_MODEL

        # Normalise roles for the OpenAI-compatible endpoint.
        payload_messages = [
            {
                "role": m.get("role") if m.get("role") in {"system", "user", "assistant"} else "user",
                "content": m.get("content", ""),
            }
            for m in messages
            if isinstance(m.get("content"), str) and m.get("content")
        ]

        url = "https://openrouter.ai/api/v1/chat/completions"
        payload: Dict[str, Any] = {"model": model, "messages": payload_messages}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        site_url = config.get("openrouter_site_url")
        site_name = config.get("openrouter_site_name")
        if site_url:
            headers["HTTP-Referer"] = site_url
        if site_name:
            headers["X-Title"] = site_name

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
        except requests.RequestException as exc:
            raise RuntimeError(
                _("Falha ao contatar OpenRouter: {error}").format(error=exc)
            ) from exc

        if response.status_code >= 400:
            raise RuntimeError(self._format_openrouter_error(response))

        return self._extract_content_from_choices(response)

    def _extract_content_from_choices(self, response: requests.Response) -> str:
        try:
            response_data = response.json()
        except ValueError as exc:
            raise RuntimeError(_("Provedor de IA retornou uma resposta JSON inválida.")) from exc

        choices = response_data.get("choices") or []
        if not choices:
            raise RuntimeError(_("O provedor de IA retornou uma resposta vazia."))

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            content = "\n".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("text")
            )

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(_("O provedor de IA não retornou conteúdo utilizável."))
        return content.strip()

    # ------------------------------------------------------------------ #
    # Response helpers                                                     #
    # ------------------------------------------------------------------ #

    def _clean_response(self, raw_content: str) -> str:
        clean = (raw_content or "").strip()
        if clean.startswith("```"):
            lines = clean.splitlines()
            if len(lines) >= 2 and lines[-1].strip().startswith("```"):
                clean = "\n".join(lines[1:-1]).strip()
        return clean

    # ------------------------------------------------------------------ #
    # UI callbacks                                                         #
    # ------------------------------------------------------------------ #

    def _display_pdf_result(self, result_text: str) -> bool:
        window = self._window_ref()
        if window and hasattr(window, "show_ai_pdf_result_dialog"):
            window.show_ai_pdf_result_dialog(result_text)
        return False

    def _notify_pdf_error(self, error_msg: str) -> bool:
        """Notify the main window that PDF processing failed."""
        window = self._window_ref()
        if window and hasattr(window, "handle_ai_pdf_error"):
            window.handle_ai_pdf_error(error_msg)
        elif window:
            self._queue_toast(_("Erro IA: {}").format(error_msg))
        return False

    def _queue_toast(self, message: str) -> None:
        def _show_toast():
            window = self._window_ref()
            if window and hasattr(window, "toast_overlay"):
                toast = Adw.Toast(title=message)
                window.toast_overlay.add_toast(toast)
            return False

        GLib.idle_add(_show_toast)

    def _format_openrouter_error(self, response: requests.Response) -> str:
        status = response.status_code
        fallback = response.text.strip() or _("Erro desconhecido.")
        try:
            payload = response.json()
        except ValueError:
            return _("OpenRouter respondeu com HTTP {status}: {message}").format(
                status=status, message=fallback
            )

        error_obj = payload.get("error")
        if not isinstance(error_obj, dict):
            return _("OpenRouter respondeu com HTTP {status}: {message}").format(
                status=status, message=fallback
            )

        message = error_obj.get("message") or fallback
        metadata = error_obj.get("metadata", {})
        provider_name = metadata.get("provider_name")
        raw_detail = metadata.get("raw")
        details = []
        if provider_name:
            details.append(str(provider_name))
        if raw_detail:
            details.append(str(raw_detail))
        suffix = f" ({' | '.join(details)})" if details else ""
        return _("OpenRouter respondeu com HTTP {status}: {message}{detail}").format(
            status=status, message=message, detail=suffix
        )