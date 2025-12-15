"""
Writing AI assistant integration for TAC Writer.
"""

from __future__ import annotations

import json
import logging
import threading
import weakref
import os
from typing import Any, Dict, List, Optional, Tuple
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
    """Coordinates conversations with an external AI service."""

    DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
    DEFAULT_OPENROUTER_MODEL = "openrouter/polaris-alpha"
    _SYSTEM_PROMPT = (
        "You are the TAC Writer assistant, a specialist in Portuguese and English grammar and"
        " academic writing. Your job is to revise, correct, and refine the provided"
        " text while preserving the original meaning, maintaining a formal tone,"
        " and respecting the Continuous Argumentation Technique (introduction,"
        " argumentation, evidence, connection). Fix only what is grammatically or"
        " stylistically incorrect, rewriting sentences only where needed. The response"
        " MUST be a JSON object containing the field 'reply' with the fully corrected"
        " text (no extra commentary) and, if necessary, 'suggestions' with brief notes."
        " Do not include any other text outside the JSON."
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

    def request_assistance(self, prompt: str, context_text: Optional[str] = None) -> bool:
        prompt = (prompt or "").strip()
        if not prompt:
            return False

        with self._lock:
            if self._inflight:
                self._queue_toast(
                    _("The AI assistant is already processing another request.")
                )
                return False
            self._inflight = True

        worker = threading.Thread(
            target=self._process_request_thread,
            args=(prompt, context_text),
            daemon=True,
        )
        worker.start()
        return True

    def handle_setting_changed(self) -> None:
        """Placeholder for future cache invalidation."""
        pass

    def _process_request_thread(self, prompt: str, context_text: Optional[str]) -> None:
        try:
            messages = self._build_messages(prompt, context_text)
            config = self._load_configuration()
            content = self._perform_request(config, messages)
            reply, suggestions = self._parse_response_payload(content)
            GLib.idle_add(self._display_reply, reply, suggestions)
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.error("AI assistant request failed: %s", exc)
            GLib.idle_add(
                self._queue_toast,
                _("AI assistant error: {error}").format(error=str(exc)),
            )
        finally:
            with self._lock:
                self._inflight = False

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
                _("Select an AI provider in Preferences ▸ AI Assistant.")
            )
        if config["provider"] == "gemini" and not config["model"]:
            config["model"] = self.DEFAULT_GEMINI_MODEL
        elif config["provider"] == "openrouter" and not config["model"]:
            config["model"] = self.DEFAULT_OPENROUTER_MODEL
        return config

    def _build_messages(
        self, prompt: str, context_text: Optional[str]
    ) -> List[Dict[str, str]]:
        prompt = (prompt or "").strip()
        context_text = (context_text or "").strip()

        if context_text:
            if prompt:
                user_content = _(
                    "Instrução do usuário:\n{instruction}\n\nTexto para revisão:\n{context}"
                ).format(
                    instruction=prompt,
                    context=context_text[:4000],
                )
            else:
                user_content = _(
                    "Revise o texto a seguir, corrigindo apenas o necessário e mantendo o tom acadêmico:\n{context}"
                ).format(context=context_text[:4000])
        else:
            user_content = prompt or _(
                "Revise o texto a seguir e responda apenas com a versão corrigida."
            )

        return [
            {"role": "system", "content": self._SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

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
            raise RuntimeError(_("Configure the Gemini API key in Preferences."))

        model = config.get("model", "").strip() or self.DEFAULT_GEMINI_MODEL
        system_instruction, contents = self._build_gemini_conversation(messages)
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
                _("Failed to contact Gemini: {error}").format(error=exc)
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
            raise RuntimeError(_("Gemini returned an invalid JSON response.")) from exc

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

        raise RuntimeError(_("Gemini did not return any usable content."))

    def _perform_openrouter_request(
        self, config: Dict[str, str], messages: List[Dict[str, str]]
    ) -> str:
        api_key = config.get("api_key", "").strip()
        if not api_key:
            raise RuntimeError(_("Configure the OpenRouter API key in Preferences."))

        model = config.get("model", "").strip() or self.DEFAULT_OPENROUTER_MODEL
        payload_messages = self._build_openai_messages(messages)
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
                _("Failed to contact OpenRouter: {error}").format(error=exc)
            ) from exc

        if response.status_code >= 400:
            raise RuntimeError(self._format_openrouter_error(response))

        return self._extract_content_from_choices(response)

    def _extract_content_from_choices(self, response: requests.Response) -> str:
        try:
            response_data = response.json()
        except ValueError as exc:
            raise RuntimeError(_("AI provider returned an invalid JSON response.")) from exc

        choices = response_data.get("choices") or []
        if not choices:
            raise RuntimeError(_("The AI provider returned an empty response."))

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            content = "\n".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("text")
            )

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(_("The AI provider did not return any usable content."))
        return content.strip()

    def _parse_response_payload(
        self, content: str
    ) -> Tuple[str, List[Dict[str, str]]]:
        reply_text = self._clean_response(content)
        suggestions: List[Dict[str, str]] = []

        payload = None
        try:
            payload = json.loads(reply_text)
        except json.JSONDecodeError:
            payload = self._extract_json_object(reply_text)

        if isinstance(payload, dict):
            reply_candidate = payload.get("reply")
            if isinstance(reply_candidate, str) and reply_candidate.strip():
                reply_text = reply_candidate.strip()
            suggestions = self._normalize_suggestions(
                payload.get("suggestions") or payload.get("commands")
            )

        return reply_text, suggestions

    def _build_gemini_conversation(
        self, messages: List[Dict[str, str]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
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
            contents.append({
                "role": mapped_role,
                "parts": [{"text": text}],
            })
        if not contents:
            contents.append({"role": "user", "parts": [{"text": ""}]})
        return system_instruction, contents

    def _build_openai_messages(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        formatted: List[Dict[str, str]] = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if not isinstance(content, str) or not content:
                continue
            role_mapped = role if role in {"system", "user", "assistant"} else "user"
            formatted.append({"role": role_mapped, "content": content})
        return formatted

    def _normalize_suggestions(self, value: Any) -> List[Dict[str, str]]:
        suggestions: List[Dict[str, str]] = []
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    suggestions.append({
                        "title": "",
                        "text": item.strip(),
                        "description": "",
                    })
                elif isinstance(item, dict):
                    text = (
                        item.get("text")
                        or item.get("content")
                        or item.get("command")
                        or ""
                    )
                    text = text.strip()
                    if not text:
                        continue
                    suggestions.append({
                        "title": item.get("title", "").strip(),
                        "text": text,
                        "description": (item.get("description") or "").strip(),
                    })
        return suggestions

    def _clean_response(self, raw_content: str) -> str:
        clean = (raw_content or "").strip()
        if clean.startswith("```"):
            lines = clean.splitlines()
            if len(lines) >= 2 and lines[-1].strip().startswith("```"):
                clean = "\n".join(lines[1:-1]).strip()
        return clean

    def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        start = text.find("{")
        while start != -1:
            brace_level = 0
            for end in range(start, len(text)):
                char = text[end]
                if char == "{":
                    brace_level += 1
                elif char == "}":
                    brace_level -= 1
                    if brace_level == 0:
                        candidate = text[start : end + 1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            break
            start = text.find("{", start + 1)
        return None

    def _display_reply(self, reply: str, suggestions: List[Dict[str, str]]) -> bool:
        window = self._window_ref()
        if window and hasattr(window, "show_ai_response_dialog"):
            window.show_ai_response_dialog(reply, suggestions)
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
        fallback = response.text.strip() or _("Unknown error.")
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


    def request_pdf_review(self, pdf_path: str) -> bool:
        """
        Lê um PDF, extrai o texto e envia para análise com o prompt específico.
        """
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

        # Executa em thread separada para não travar a UI
        worker = threading.Thread(
            target=self._process_pdf_thread,
            args=(pdf_path,),
            daemon=True,
        )
        worker.start()
        return True

    def _process_pdf_thread(self, pdf_path: str) -> None:
        try:
            # 1. Extração do Texto do PDF
            text_content = ""
            try:
                reader = PdfReader(pdf_path)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text_content += extracted + "\n"
            except Exception as e:
                raise RuntimeError(_("Erro ao ler PDF: {}").format(str(e)))

            if not text_content.strip():
                raise RuntimeError(_("Não foi possível extrair texto do PDF (pode ser uma imagem ou vazio)."))

            # 2. Montagem do Prompt
            fixed_prompt = (
                "Faça uma revisão ortográfica, gramatical e semântica do texto abaixo. "
                "Procure por palavras que, ainda que digitadas corretamente, possam não fazer sentido "
                "com o conteúdo de uma frase. Identifique repetições de palavras em excesso em pequenos "
                "períodos de texto.\n\n"
                "--- INÍCIO DO TEXTO ---\n"
                f"{text_content}\n"
                "--- FIM DO TEXTO ---"
            )
            
            messages = [
                {
                    "role": "system", 
                    "content": "Você é um especialista em revisão de textos acadêmicos em Português. Responda apenas com a revisão solicitada, sem JSON."
                },
                {
                    "role": "user", 
                    "content": fixed_prompt
                }
            ]

            config = self._load_configuration()
            
            content = self._perform_request(config, messages)
            clean_reply = self._clean_response(content)
            
            GLib.idle_add(self._display_pdf_result, clean_reply)

        except Exception as exc:
            self.logger.error("AI PDF review failed: %s", exc)
            # MUDANÇA AQUI: Em vez de só mandar um toast, chamamos a notificação de erro específica
            GLib.idle_add(self._notify_pdf_error, str(exc))
        finally:
            with self._lock:
                self._inflight = False

    # ADICIONE ESTE MÉTODO NOVO
    def _notify_pdf_error(self, error_msg: str) -> bool:
        """Notifica a janela principal que houve um erro no processamento do PDF"""
        window = self._window_ref()
        # Verifica se a janela tem o método de tratamento de erro
        if window and hasattr(window, "handle_ai_pdf_error"):
            window.handle_ai_pdf_error(error_msg)
        # Fallback para o toast antigo caso o método não exista
        elif window: 
            self._queue_toast(_("Erro IA: {}").format(error_msg))
        return False


    def _display_pdf_result(self, result_text: str) -> bool:
        window = self._window_ref()
        if window and hasattr(window, "show_ai_pdf_result_dialog"):
            window.show_ai_pdf_result_dialog(result_text)
        return False