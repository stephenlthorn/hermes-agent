"""Tests for Telegram model picker thread fallback."""

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


def _ensure_telegram_mock():
    if "telegram" in sys.modules and hasattr(sys.modules["telegram"], "__file__"):
        return

    mod = MagicMock()
    mod.ext.ContextTypes.DEFAULT_TYPE = type(None)
    mod.constants.ParseMode.MARKDOWN = "Markdown"
    mod.constants.ParseMode.MARKDOWN_V2 = "MarkdownV2"
    mod.constants.ParseMode.HTML = "HTML"
    mod.constants.ChatType.PRIVATE = "private"
    mod.constants.ChatType.GROUP = "group"
    mod.constants.ChatType.SUPERGROUP = "supergroup"
    mod.constants.ChatType.CHANNEL = "channel"
    mod.error.NetworkError = type("NetworkError", (OSError,), {})
    mod.error.TimedOut = type("TimedOut", (OSError,), {})
    mod.error.BadRequest = type("BadRequest", (Exception,), {})

    for name in ("telegram", "telegram.ext", "telegram.constants", "telegram.request"):
        sys.modules.setdefault(name, mod)
    sys.modules.setdefault("telegram.error", mod.error)


_ensure_telegram_mock()

from gateway.config import PlatformConfig
from plugins.platforms.telegram.adapter import TelegramAdapter


def _make_adapter():
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="test-token"))
    adapter._bot = AsyncMock()
    adapter._app = MagicMock()
    return adapter


class TestTelegramModelPicker:
    @pytest.mark.asyncio
    async def test_send_model_picker_escapes_dynamic_provider_label(self):
        adapter = _make_adapter()
        sent = {}

        async def mock_send_message(**kwargs):
            sent.update(kwargs)
            return SimpleNamespace(message_id=101)

        adapter._bot.send_message = AsyncMock(side_effect=mock_send_message)

        result = await adapter.send_model_picker(
            chat_id="12345",
            providers=[
                {"slug": "provider_one", "name": "Provider One", "total_models": 1, "is_current": True}
            ],
            current_model="model_1",
            current_provider="provider_one",
            session_key="s",
            on_model_selected=AsyncMock(),
            metadata={"thread_id": "99999"},
        )

        assert result.success is True
        assert "MARKDOWN_V2" in repr(sent["parse_mode"])
        assert "provider\\_one" in sent["text"]
        assert "`model_1`" in sent["text"]

    @pytest.mark.asyncio
    async def test_back_button_escapes_dynamic_provider_label(self):
        adapter = _make_adapter()
        adapter._model_picker_state["12345"] = {
            "providers": [{"slug": "provider_one", "name": "Provider One", "total_models": 1, "is_current": True}],
            "current_model": "model_1",
            "current_provider": "provider_one",
            "session_key": "s",
            "on_model_selected": AsyncMock(),
            "msg_id": 42,
        }

        query = AsyncMock()
        query.data = "mb"
        query.message = MagicMock()
        query.message.chat_id = 12345
        query.from_user = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        await adapter._handle_model_picker_callback(query, "mb", "12345")

        edit_kwargs = query.edit_message_text.call_args[1]
        assert "MARKDOWN_V2" in repr(edit_kwargs["parse_mode"])
        assert "provider\\_one" in edit_kwargs["text"]
        assert "`model_1`" in edit_kwargs["text"]

    @pytest.mark.asyncio
    async def test_local_folder_drills_directly_to_named_models(self, tmp_path, monkeypatch):
        (tmp_path / "config.yaml").write_text(
            "providers:\n"
            "  qwen38-27b-crack-q8:\n"
            "    name: Qwen 3.8 27B CRACK\n"
            "    base_url: http://127.0.0.1:8187/v1\n"
        )
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        adapter = _make_adapter()
        adapter._model_picker_state["12345"] = {
            "providers": [
                {
                    "slug": "custom:qwen38-27b-crack-q8",
                    "name": "Qwen 3.8 27B CRACK",
                    "models": ["qwen38-27b-crack-q8"],
                    "total_models": 1,
                    "is_current": True,
                }
            ],
            "current_model": "qwen38-27b-crack-q8",
            "current_provider": "custom:qwen38-27b-crack-q8",
            "session_key": "s",
            "on_model_selected": AsyncMock(),
            "msg_id": 42,
        }

        query = AsyncMock()
        query.data = "mpg:local"
        query.message = MagicMock()
        query.message.chat_id = 12345
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        await adapter._handle_model_picker_callback(query, "mpg:local", "12345")

        edit_kwargs = query.edit_message_text.call_args[1]
        assert "Local" in edit_kwargs["text"]
        assert adapter._model_picker_state["12345"]["selected_provider"] == ""
        assert adapter._model_picker_state["12345"]["model_list"] == [
            {
                "id": "qwen38-27b-crack-q8",
                "provider": "custom:qwen38-27b-crack-q8",
                "label": "Qwen 3.8 27B CRACK",
            }
        ]

    @pytest.mark.asyncio
    async def test_non_local_folder_drills_to_its_own_models_not_local(self, tmp_path, monkeypatch):
        """Regression test for 2026-08-18: the mpg: handler's local_row lookup
        was hardcoded to `group_id == "local"` instead of the tapped
        `group_id`, so EVERY curated folder (z.AI, xAI, Moonshot, ...) showed
        the Local folder's model list instead of its own. With two folders
        present in state["providers"], tapping the non-local one must return
        that folder's models, not Local's.
        """
        (tmp_path / "config.yaml").write_text(
            "providers:\n"
            "  qwen38-27b-crack-q8:\n"
            "    name: Qwen 3.8 27B CRACK\n"
            "    base_url: http://127.0.0.1:8187/v1\n"
        )
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        adapter = _make_adapter()
        adapter._model_picker_state["12345"] = {
            "providers": [
                {
                    "slug": "custom:qwen38-27b-crack-q8",
                    "name": "Qwen 3.8 27B CRACK",
                    "models": ["qwen38-27b-crack-q8"],
                    "total_models": 1,
                    "is_current": False,
                },
                {
                    "slug": "zai",
                    "name": "z.AI",
                    "models": ["glm-5.2", "glm-5.1", "glm-5"],
                    "total_models": 3,
                    "is_current": True,
                },
            ],
            "current_model": "glm-5.2",
            "current_provider": "zai",
            "session_key": "s",
            "on_model_selected": AsyncMock(),
            "msg_id": 42,
        }

        query = AsyncMock()
        query.data = "mpg:zai"
        query.message = MagicMock()
        query.message.chat_id = 12345
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        await adapter._handle_model_picker_callback(query, "mpg:zai", "12345")

        model_ids = {
            entry["id"] for entry in adapter._model_picker_state["12345"]["model_list"]
        }
        assert model_ids == {"glm-5.2", "glm-5.1", "glm-5"}
        assert "qwen38-27b-crack-q8" not in model_ids
