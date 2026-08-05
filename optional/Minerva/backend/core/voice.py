#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoiceManager — STT (Whisper + Vosk) y TTS (Piper / Fish Audio) para Minerva.

Expone el singleton `voice_mgr` que utilizan los engines de chat.
"""
import io
import json
import os
import queue
import sys
import tempfile
import threading
import time

from .config import VOICE_AVAILABLE, VOSK_AVAILABLE, FISH_AUDIO_AVAILABLE, VOICE_DIR
from .io import emit
from .audio_analyzer import AudioAnalyzer

if VOICE_AVAILABLE:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    from pywhispercpp.model import Model

if VOSK_AVAILABLE:
    from vosk import Model as VoskModel, KaldiRecognizer

if FISH_AUDIO_AVAILABLE:
    from fish_audio_sdk import Session as FishSession, TTSRequest


# ── Utilidades de emotion tags ────────────────────────────────────────────────
import re as _re

# Tags soportados por Fish Audio:
# [happy] [sad] [angry] [excited] [calm] [nervous] [confident] [surprised] [satisfied]
# [scared] [worried] [upset] [frustrated] [empathetic]
# [embarrassed] [disgusted] [moved] [proud] [relaxed] [grateful] [curious] [sarcastic]
# (+ aliases de compatibilidad: [neutral] [fearful] [disgust] [surprise])
_EMOTION_TAGS_PATTERN = r'happy|sad|angry|excited|calm|nervous|confident|surprised|surprise|satisfied|scared|fearful|worried|upset|frustrated|empathetic|embarrassed|disgusted|disgust|moved|proud|relaxed|grateful|curious|sarcastic|neutral'

_EMOTION_TAG_RE = _re.compile(
    rf'\s*\[({_EMOTION_TAGS_PATTERN})\]\s*',
    _re.IGNORECASE
)

def strip_emotion_tags(text: str) -> str:
    """Elimina los emotion tags del texto para mostrarlo limpio en el chat.

    Preserva la separación natural entre palabras sin juntar ni duplicar espacios.
    """
    def _sub(m):
        start = m.start()
        end = m.end()
        prev_char = text[start-1] if start > 0 else ''
        next_char = text[end] if end < len(text) else ''

        if start == 0 or prev_char in '\n\r':
            return ''
        if prev_char.isspace() or next_char.isspace():
            return ''
        return ' '

    cleaned = _EMOTION_TAG_RE.sub(_sub, text)
    cleaned = _re.sub(r'  +', ' ', cleaned)
    return cleaned


class StreamEmotionStripper:
    """Procesador en streaming para eliminar emotion tags token a token sin fuga de tags parciales

    ni destrucción de espacios entre palabras.
    """
    def __init__(self):
        self.buffer = ''
        self.emitted_any = False
        self.last_char = ''

    def _strip(self, text: str) -> str:
        def _sub(m):
            start = m.start()
            end = m.end()
            prev_char = text[start-1] if start > 0 else self.last_char
            next_char = text[end] if end < len(text) else ''

            if not self.emitted_any and start == 0 and prev_char == '':
                return ''
            if prev_char in '\n\r':
                return ''
            if prev_char.isspace() or next_char.isspace():
                return ''
            return ' '

        cleaned = _EMOTION_TAG_RE.sub(_sub, text)
        if self.last_char.isspace() and cleaned.startswith(' '):
            cleaned = cleaned.lstrip(' ')
        cleaned = _re.sub(r'  +', ' ', cleaned)
        return cleaned

    def add(self, chunk: str) -> str:
        self.buffer += chunk

        last_bracket = self.buffer.rfind('[')
        if last_bracket != -1:
            closing = self.buffer.find(']', last_bracket)
            if closing == -1 or closing >= len(self.buffer) - 1:
                safe_split = last_bracket
                while safe_split > 0 and self.buffer[safe_split-1].isspace():
                    safe_split -= 1
                out = self.buffer[:safe_split]
                self.buffer = self.buffer[safe_split:]
                out_cleaned = self._strip(out)
                if out_cleaned:
                    self.emitted_any = True
                    self.last_char = out_cleaned[-1]
                return out_cleaned

        out = self.buffer
        self.buffer = ''
        out_cleaned = self._strip(out)
        if out_cleaned:
            self.emitted_any = True
            self.last_char = out_cleaned[-1]
        return out_cleaned

    def flush(self) -> str:
        out = self.buffer
        self.buffer = ''
        out_cleaned = self._strip(out)
        if out_cleaned:
            self.emitted_any = True
            self.last_char = out_cleaned[-1]
        return out_cleaned


class VoiceManager:
    def __init__(self):
        self.is_recording  = False
        self.audio_data    = []
        self.samplerate    = 16000
        self.stream        = None
        self.whisper_model = None

        self.piper_voice = None

        # ── Proveedor TTS ──────────────────────────────────────────────────────
        # "piper" (local, sin internet) o "fish" (Fish Audio API, en la nube)
        self.tts_provider   = "piper"
        self.fish_api_key   = ""
        self.fish_voice_id  = "15e8b140868348538ab2d7d887060e78"
        self.fish_model     = "speech-1.5"  # speech-1.5 | speech-1.6 | s2-pro | s1 | s1-mini | agent-x0
        self._fish_client   = None   # se crea al vuelo cuando se necesita

        self.tts_queue     = queue.Queue()
        self.play_queue    = queue.Queue()
        self.tts_thread    = None
        self.play_thread   = None
        self.tts_stop_event = threading.Event()

        # Analizador de audio para métricas de visualización (RMS + FFT)
        self.analyzer = AudioAnalyzer(smoothing=0.3)

        if VOICE_AVAILABLE:
            os.makedirs(VOICE_DIR, exist_ok=True)
            self.tts_thread  = threading.Thread(target=self._tts_worker,  daemon=True)
            self.play_thread = threading.Thread(target=self._play_worker, daemon=True)
            self.tts_thread.start()
            self.play_thread.start()

            # Vosk para wake word
            self.vosk_model      = None
            self.vosk_recognizer = None
            if VOSK_AVAILABLE:
                try:
                    vosk_path = os.path.join(VOICE_DIR, "vosk-model-es")
                    if os.path.exists(vosk_path):
                        self.vosk_model      = VoskModel(vosk_path)
                        self.vosk_recognizer = KaldiRecognizer(self.vosk_model, 16000)
                        self.wake_word_thread = threading.Thread(
                            target=self._wake_word_worker, daemon=True
                        )
                        self.wake_word_thread.start()
                except Exception as e:
                    print(f"Error cargando vosk: {e}", file=sys.stderr)

    # ── Configuración de proveedor TTS ────────────────────────────────────────

    def set_tts_provider(self, provider: str, fish_api_key: str = "", fish_voice_id: str = "", fish_model: str = ""):
        """Cambia el proveedor TTS en caliente (sin reiniciar el backend).

        Args:
            provider:      "piper" o "fish"
            fish_api_key:  API Key de Fish Audio (solo necesaria si provider="fish")
            fish_voice_id: reference_id del modelo de voz en Fish Audio
            fish_model:    backend de generación: speech-1.5 | speech-1.6 | s2-pro | s1 | s1-mini | agent-x0
        """
        self.tts_provider  = provider.lower().strip()
        self.fish_api_key  = fish_api_key
        if fish_voice_id:
            self.fish_voice_id = fish_voice_id
        if fish_model:
            self.fish_model = fish_model

        # Invalidar el cliente de Fish para que se recree con la nueva API key
        self._fish_client = None

        print(
            f"[VoiceManager] TTS provider: {self.tts_provider!r}"
            + (f"  model: {self.fish_model!r}  voice_id: {self.fish_voice_id!r}" if self.tts_provider == "fish" else ""),
            file=sys.stderr
        )

    def _get_fish_client(self):
        """Retorna (o crea) el cliente de Fish Audio reutilizando la instancia."""
        if self._fish_client is None:
            if not FISH_AUDIO_AVAILABLE:
                raise RuntimeError("fish-audio-sdk no está instalado. Ejecuta: pip install fish-audio-sdk")
            if not self.fish_api_key:
                raise RuntimeError("Se requiere una API Key de Fish Audio (fishApiKey en la config).")
            self._fish_client = FishSession(apikey=self.fish_api_key)
        return self._fish_client

    # ── TTS (Piper) ──────────────────────────────────────────────────────────

    def _ensure_piper_model(self):
        if self.piper_voice is not None:
            return
        try:
            print("Cargando modelo Piper TTS...", file=sys.stderr)
            from piper import PiperVoice
            model_path = os.path.join(VOICE_DIR, "es_MX-claude-high.onnx")
            if not os.path.exists(model_path):
                print(f"Modelo no encontrado: {model_path}", file=sys.stderr)
                return
            self.piper_voice = PiperVoice.load(model_path)
            print("Modelo Piper TTS cargado exitosamente.", file=sys.stderr)
        except Exception as e:
            print(f"Error cargando Piper TTS: {e}", file=sys.stderr)

    # ── TTS (Fish Audio — HTTP streaming) ─────────────────────────────────────

    def _synthesize_fish(self, text: str):
        """Genera audio con Fish Audio (HTTP streaming) y lo encola en play_queue.

        Fish Audio devuelve el audio como un stream de bytes MP3 que se decodifica
        en memoria con soundfile. Para mantener latencia baja, cada respuesta HTTP
        (que ya viene en chunks) se decodifica y encola tan pronto como llega.
        """
        try:
            client = self._get_fish_client()
        except RuntimeError as e:
            print(f"[Fish Audio] Error: {e}", file=sys.stderr)
            return

        try:
            mp3_buffer = io.BytesIO()

            for chunk in client.tts(
                TTSRequest(
                    reference_id=self.fish_voice_id,
                    text=text,
                ),
                backend=self.fish_model,
            ):
                if self.tts_stop_event.is_set():
                    break
                mp3_buffer.write(chunk)

            if self.tts_stop_event.is_set():
                return

            # Decodificar el MP3 completo en memoria
            mp3_buffer.seek(0)
            audio_np, sample_rate = sf.read(mp3_buffer, dtype="int16", always_2d=False)

            # Si es estéreo, mezclar a mono
            if audio_np.ndim == 2:
                audio_np = audio_np.mean(axis=1).astype(np.int16)

            self.play_queue.put((audio_np, sample_rate))

        except Exception as e:
            import traceback
            print(f"ERROR EN TTS WORKER (Fish Audio): {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    # ── Worker de síntesis ────────────────────────────────────────────────────

    def _tts_worker(self):
        while True:
            text = self.tts_queue.get()
            if text is None:
                break
            if self.tts_stop_event.is_set():
                self.tts_queue.task_done()
                continue

            try:
                if self.tts_provider == "fish":
                    if not self.tts_stop_event.is_set():
                        self._synthesize_fish(text)
                else:
                    # Piper (comportamiento original)
                    self._ensure_piper_model()
                    if not self.piper_voice:
                        print("Piper TTS no pudo ser inicializado", file=sys.stderr)
                        self.tts_queue.task_done()
                        continue
                    if not self.tts_stop_event.is_set():
                        for chunk in self.piper_voice.synthesize(text):
                            if self.tts_stop_event.is_set():
                                break
                            audio_np = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16)
                            self.play_queue.put((audio_np, chunk.sample_rate))
            except Exception as e:
                import traceback
                print(f"ERROR EN TTS WORKER ({self.tts_provider}): {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

            self.tts_queue.task_done()

    def _play_worker(self):
        self.is_speaking = False
        _zero_audio = {"type": "audio_data", "source": "tts",
                       "rms": 0, "band0": 0, "band1": 0, "band2": 0, "band3": 0}
        while True:
            item = self.play_queue.get()
            if item is None:
                if self.is_speaking:
                    emit({"type": "voice_speaking_stopped"})
                    self.analyzer.reset()
                    emit(_zero_audio)
                    self.is_speaking = False
                break

            if not self.is_speaking:
                emit({"type": "voice_speaking_started"})
                self.is_speaking = True

            audio, sample_rate = item
            if not self.tts_stop_event.is_set():
                # Subdividir en chunks de ~20ms para análisis a ~50fps
                sub_size = max(1, int(sample_rate * 0.02))
                metrics_list = []
                for j in range(0, len(audio), sub_size):
                    sub = audio[j:j + sub_size]
                    metrics_list.append(self.analyzer.analyze(sub, sample_rate))

                # Reproducir el chunk completo (non-blocking)
                sd.play(audio, sample_rate)

                # Emitir métricas a intervalos de ~20ms durante la reproducción
                for m in metrics_list:
                    if self.tts_stop_event.is_set():
                        break
                    emit({"type": "audio_data", "source": "tts", **m})
                    time.sleep(0.02)

                # Esperar a que termine la reproducción del chunk
                sd.wait()

            self.play_queue.task_done()

            if self.play_queue.empty() and self.is_speaking:
                emit({"type": "voice_speaking_stopped"})
                self.analyzer.reset()
                emit(_zero_audio)
                self.is_speaking = False

    def stop_tts(self):
        if not VOICE_AVAILABLE:
            return
        self.tts_stop_event.set()
        sd.stop()
        while not self.tts_queue.empty():
            try:
                self.tts_queue.get_nowait()
            except Exception:
                pass
        while not self.play_queue.empty():
            try:
                self.play_queue.get_nowait()
            except Exception:
                pass
        # Resetear métricas de audio y notificar al frontend
        self.analyzer.reset()
        emit({"type": "audio_data", "source": "tts",
              "rms": 0, "band0": 0, "band1": 0, "band2": 0, "band3": 0})
        if getattr(self, 'is_speaking', False):
            self.is_speaking = False
            emit({"type": "voice_speaking_stopped"})

    # ── Wake word (Vosk) ──────────────────────────────────────────────────────

    def _wake_word_worker(self):
        if not self.vosk_model:
            return
        try:
            with sd.RawInputStream(
                samplerate=16000, blocksize=320, dtype='int16',
                channels=1, callback=self.audio_callback
            ):
                while True:
                    time.sleep(1)
        except Exception as e:
            print(f"Error en wake word stream: {e}", file=sys.stderr)

    def audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            audio_np = np.frombuffer(indata, dtype=np.int16).astype(np.float32) / 32768.0
            self.audio_data.append(audio_np.copy())

            # Emitir métricas de audio del micrófono para el SiriOrb
            metrics = self.analyzer.analyze(audio_np, 16000)
            emit({"type": "audio_data", "source": "mic", **metrics})

            if self.vosk_recognizer:
                is_final = self.vosk_recognizer.AcceptWaveform(bytes(indata))
                if is_final:
                    res  = json.loads(self.vosk_recognizer.Result())
                    text = res.get("text", "")
                    if text.strip():
                        emit({"type": "silence_detected"})
        elif self.vosk_recognizer:
            if getattr(self, 'is_speaking', False):
                self.vosk_recognizer.Reset()
                return

            is_final = self.vosk_recognizer.AcceptWaveform(bytes(indata))
            if is_final:
                res  = json.loads(self.vosk_recognizer.Result())
                text = res.get("text", "")
            else:
                res  = json.loads(self.vosk_recognizer.PartialResult())
                text = res.get("partial", "")

            if "minerva" in text.lower():
                if not self.is_recording:
                    self.vosk_recognizer.Reset()
                    emit({"type": "wake_word_detected"})

    # ── Grabación / Transcripción ─────────────────────────────────────────────

    def toggle_recording(self):
        if not VOICE_AVAILABLE:
            return None

        if not self.is_recording:
            self.stop_tts()
            self.tts_stop_event.clear()
            self.is_recording = True
            self.audio_data   = []
            if not getattr(self, "wake_word_thread", None) or not self.wake_word_thread.is_alive():
                self.stream = sd.RawInputStream(
                    samplerate=16000, blocksize=320, dtype='int16',
                    channels=1, callback=self.audio_callback
                )
                self.stream.start()
            return "started"
        else:
            self.is_recording = False
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None

            if not self.audio_data:
                return "empty"

            audio_np = np.concatenate(self.audio_data, axis=0)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                sf.write(tmp.name, audio_np, self.samplerate)
                tmp_name = tmp.name

            if not self.whisper_model:
                try:
                    self.whisper_model = Model(
                        "small", language="es",
                        print_realtime=False, print_progress=False
                    )
                except Exception:
                    os.remove(tmp_name)
                    return "error"

            try:
                segments = self.whisper_model.transcribe(tmp_name)
                text = " ".join([s.text for s in segments]).strip()
            except Exception:
                text = "error"
            finally:
                os.remove(tmp_name)

            return text


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────
voice_mgr = VoiceManager()
