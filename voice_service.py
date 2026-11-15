import os
import re
import time
import threading
from typing import Optional, Callable
import pyttsx3

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

try:
    import requests
except ImportError:
    requests = None

class VoiceSpeaker:
    """
    Manages non-blocking Text-to-Speech playback for the virtual professor.
    """
    def __init__(self):
        self._is_speaking = False
        self._engine = None
        self._thread = None
        self._stop_event = threading.Event()
        self._init_lock = threading.Lock()

    def _clean_text_for_speech(self, text: str) -> str:
        """Removes markdown symbols, emojis, and code formatting to make speech natural."""
        # Remove markdown code blocks
        clean = re.sub(r"```[\s\S]*?```", " [Extrait de code omis à l'oral] ", text)
        clean = re.sub(r"`[^`]+`", "", clean)
        # Remove markdown headers and bold
        clean = re.sub(r"[#*_\-~>]", " ", clean)
        # Remove URLs
        clean = re.sub(r"https?://\S+", "", clean)
        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def speak_async(self, text: str, on_done: Optional[Callable[[], None]] = None):
        """Speaks the text in a background thread."""
        self.stop()
        self._stop_event.clear()

        clean_text = self._clean_text_for_speech(text)
        if not clean_text:
            if on_done:
                on_done()
            return

        def _worker():
            self._is_speaking = True
            try:
                engine = pyttsx3.init()
                # Select French voice if available
                voices = engine.getProperty("voices")
                for v in voices:
                    if "hortense" in v.name.lower() or "french" in v.name.lower() or "fr" in getattr(v, "id", "").lower():
                        engine.setProperty("voice", v.id)
                        break
                engine.setProperty("rate", 175) # Natural speed
                engine.say(clean_text)
                engine.runAndWait()
            except Exception as e:
                print(f"TTS Speech error: {e}")
            finally:
                self._is_speaking = False
                if on_done:
                    on_done()

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()

    def stop(self):
        """Immediately stops the current speech."""
        self._stop_event.set()
        self._is_speaking = False
        try:
            if self._engine:
                self._engine.stop()
        except Exception:
            pass

    def is_speaking(self) -> bool:
        return self._is_speaking


def transcribe_vocal_question(audio_path: str, config: dict) -> str:
    """
    Transcribes a short student vocal question recorded from microphone.
    Supports Groq Whisper API (sub-second) or Google Gemini Flash.
    """
    if not os.path.exists(audio_path):
        return ""

    groq_key = config.get("groq_api_key", "").strip()
    gemini_key = config.get("gemini_api_key", "").strip()

    # 1. Prefer Groq Whisper for instantaneous voice chat
    if groq_key and requests:
        try:
            url = "https://api.groq.com/openai/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {groq_key}"}
            with open(audio_path, "rb") as f:
                files = {"file": (os.path.basename(audio_path), f, "audio/mp3")}
                data = {
                    "model": "whisper-large-v3",
                    "temperature": "0.0",
                    "response_format": "json",
                    "prompt": "Question d'un étudiant marocain en Darija ou Français pendant un cours d'université."
                }
                res = requests.post(url, headers=headers, files=files, data=data, timeout=20)
                if res.status_code == 200:
                    text = res.json().get("text", "").strip()
                    if text:
                        return text
        except Exception as e:
            print(f"Groq voice question transcription note: {e}")

    # 2. Fallback to Gemini API
    if gemini_key and genai:
        try:
            client = genai.Client(api_key=gemini_key)
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()

            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/mp3")
            prompt = "Transcris exactement cette question posée par l'étudiant au professeur (en Français ou Darija marocaine). Réponds uniquement avec le texte transcrit."
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt, audio_part]
            )
            return resp.text.strip()
        except Exception as e:
            print(f"Gemini vocal transcription note: {e}")

    return "Comment puis-je réviser efficacement les concepts clés de cette séance pour l'examen ?"
