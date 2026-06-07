from __future__ import annotations

import unittest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from scripts.run_maria_telegram import transcribe_telegram_message
from services.maria_transcription import TRANSCRIPTION_PROMPT, _transcribe_openai
from services.telegram import TelegramConfig


class MariaTelegramAudioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = TelegramConfig(
            enabled=True,
            token="test-token",
            api_url="https://api.telegram.org",
            allowed_chat_ids=set(),
            allow_all_chats=True,
        )

    @patch("scripts.run_maria_telegram.transcribe_audio")
    @patch("scripts.run_maria_telegram.download_telegram_file")
    def test_voice_message_is_downloaded_and_transcribed(
        self,
        download_file: Mock,
        transcribe: Mock,
    ) -> None:
        download_file.return_value = "voice/file_1.oga"
        transcribe.return_value = "Cuantos Merchan se vendieron este mes"

        result = transcribe_telegram_message(
            self.config,
            {"voice": {"file_id": "voice-1"}},
        )

        self.assertEqual(result, "Cuantos Merchan se vendieron este mes")
        self.assertEqual(download_file.call_args.args[1], "voice-1")
        audio_path = download_file.call_args.args[2]
        self.assertIsInstance(audio_path, Path)
        self.assertEqual(audio_path.suffix, ".ogg")
        self.assertTrue(transcribe.called)

    def test_non_audio_message_returns_none(self) -> None:
        self.assertIsNone(
            transcribe_telegram_message(self.config, {"text": "Hola"})
        )

    @patch("services.maria_transcription.requests.post")
    def test_openai_transcription_uses_wally_glossary(self, post: Mock) -> None:
        response = Mock()
        response.ok = True
        response.json.return_value = {"text": "Venta de Merchan por sucursal"}
        post.return_value = response

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "audio.ogg"
            audio_path.write_bytes(b"test-audio")
            result = _transcribe_openai(
                audio_path,
                "audio.ogg",
                {
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "test",
                    "model": "gpt-4o-transcribe",
                },
            )

        self.assertEqual(result, "Venta de Merchan por sucursal")
        self.assertEqual(post.call_args.kwargs["data"]["model"], "gpt-4o-transcribe")
        self.assertEqual(post.call_args.kwargs["data"]["prompt"], TRANSCRIPTION_PROMPT)
        self.assertIn("Merchan", TRANSCRIPTION_PROMPT)


if __name__ == "__main__":
    unittest.main()
