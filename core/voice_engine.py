"""
STARK Voice Engine — TTS (pyttsx3) + Speech Recognition listener
Pulled from STARK v2.
"""
import threading
import re

try:
    import pyttsx3
    HAS_TTS = True
except ImportError:
    HAS_TTS = False

try:
    import speech_recognition as sr
    HAS_SPEECH = True
except ImportError:
    HAS_SPEECH = False


def clean_for_speech(text: str) -> str:
    """Strip markdown symbols, paths, and special chars before speaking."""
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    text = re.sub(r'[*_`#\-─═╔╗╚╝║|✅❌▶️🎵🔍]+', '', text)
    text = re.sub(r'[A-Za-z]:\\[^\s]+', '', text)
    text = re.sub(r'\s{3,}', ' ', text)
    text = re.sub(r'\n{2,}', '. ', text)
    return text.strip()


class VoiceEngine:
    """Text-to-speech engine using Windows SAPI5 via pyttsx3."""

    def __init__(self):
        self.enabled = True
        self.rate = 175
        self.volume = 0.9
        self._engine = None
        self._lock = threading.Lock()
        self._voices = []
        self._init()

    def _init(self):
        if not HAS_TTS:
            return
        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.rate)
            self._engine.setProperty("volume", self.volume)
            voices = self._engine.getProperty("voices") or []
            self._voices = voices
            if voices:
                self._engine.setProperty("voice", voices[0].id)
        except Exception as e:
            print(f"[VoiceEngine] Init failed: {e}")
            self._engine = None

    def speak(self, text: str, force: bool = False):
        """Speak text asynchronously. Set force=True to speak even when disabled."""
        if not self._engine:
            return
        if not self.enabled and not force:
            return
        clean = clean_for_speech(text)
        words = clean.split()
        if len(words) > 80:
            clean = " ".join(words[:80]) + "..."
        if len(clean) < 2:
            return
        self.stop()

        def _run():
            with self._lock:
                try:
                    self._engine.say(clean)
                    self._engine.runAndWait()
                except Exception:
                    pass

        threading.Thread(target=_run, daemon=True).start()

    def stop(self):
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        if not self.enabled:
            self.stop()
        return self.enabled

    def set_rate(self, r: int):
        self.rate = r
        if self._engine:
            try:
                self._engine.setProperty("rate", r)
            except Exception:
                pass

    def set_volume(self, v: float):
        self.volume = v
        if self._engine:
            try:
                self._engine.setProperty("volume", v)
            except Exception:
                pass

    def get_voice_names(self) -> list:
        return [getattr(v, "name", str(v)) for v in self._voices] or ["Default"]

    def set_voice_idx(self, idx: int):
        if self._voices and self._engine:
            try:
                self._engine.setProperty("voice", self._voices[idx % len(self._voices)].id)
            except Exception:
                pass

    @property
    def available(self) -> bool:
        return HAS_TTS and self._engine is not None


class SpeechListener:
    """
    Background microphone listener.
    Calls on_result(text) when speech is recognised.
    on_state_change(bool) fires when listening starts/stops.
    """

    def __init__(self, on_result, on_state_change=None):
        self.on_result = on_result
        self.on_state_change = on_state_change
        self._running = False
        self._thread = None

    def is_listening(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        if self.on_state_change:
            self.on_state_change(True)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self.on_state_change:
            self.on_state_change(False)

    def toggle(self):
        self.stop() if self._running else self.start()

    def _loop(self):
        if not HAS_SPEECH:
            return
        try:
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 300
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold = 0.8

            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                while self._running:
                    try:
                        audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                        text = recognizer.recognize_google(audio)
                        if text and self._running:
                            self.on_result(text.strip())
                    except sr.WaitTimeoutError:
                        pass
                    except sr.UnknownValueError:
                        pass
                    except sr.RequestError:
                        pass
                    except Exception:
                        break
        except Exception:
            pass
        finally:
            self._running = False
            if self.on_state_change:
                self.on_state_change(False)

    @property
    def available(self) -> bool:
        return HAS_SPEECH
