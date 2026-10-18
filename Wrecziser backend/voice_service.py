import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
KOKORO_DIR = BASE_DIR / "models" / "kokoro"
KOKORO_CONFIG = KOKORO_DIR / "config.json"
KOKORO_MODEL = KOKORO_DIR / "kokoro-v1_0.pth"
VOICES_DIR = KOKORO_DIR / "voices"

# Enable offline mode only if local weights exist, otherwise allow HuggingFace auto-download
if KOKORO_MODEL.exists():
    os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import io
import wave
import re
import base64
import logging
from typing import Dict, Any, List, Optional
import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "am_fenrir"
DEFAULT_SPEED = 0.94
SAMPLE_RATE = 24000
WRECZ_PHONEMES = "waekze"
MAX_CACHE_ENTRIES = 1000  # Up to 1GB allocated in-memory cache for fast instant replay

class KokoroVoiceService:
    def __init__(self, voice: str = DEFAULT_VOICE, speed: float = DEFAULT_SPEED):
        self.voice = voice
        self.speed = speed
        self._pipeline = None
        self._initialized = False
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._voice_cache: Dict[str, Any] = {}

    def _get_pipeline(self):
        if self._pipeline is None:
            try:
                import torch
                # Allocate optimal CPU threads for maximum inference throughput
                optimal_threads = min(8, max(2, os.cpu_count() or 4))
                torch.set_num_threads(optimal_threads)
                logger.info("Configured PyTorch with %d CPU threads for Kokoro.", optimal_threads)

                from kokoro import KPipeline, KModel
                if KOKORO_CONFIG.exists() and KOKORO_MODEL.exists():
                    logger.info("Loading Kokoro model locally from %s", KOKORO_DIR)
                    kmodel = KModel(repo_id="hexgrad/Kokoro-82M", config=str(KOKORO_CONFIG), model=str(KOKORO_MODEL))
                    self._pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M", model=kmodel)
                else:
                    self._pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
                logger.info("Kokoro KPipeline successfully initialized in memory.")
            except Exception as e:
                logger.error("Failed to initialize Kokoro KPipeline: %s", e)
                raise RuntimeError(f"Kokoro initialization error: {e}") from e

        if not self._initialized:
            try:
                lexicon = getattr(self._pipeline.g2p, "lexicon", None)
                if lexicon is not None and hasattr(lexicon, "golds"):
                    lexicon.golds["wrecz"] = WRECZ_PHONEMES
                    lexicon.golds["wreciser"] = "waekzeyser"
                    logger.info("Custom Wrecz pronunciations installed in Misaki lexicon.")
            except Exception as e:
                logger.warning("Could not set custom lexicon: %s", e)
            self._initialized = True

        return self._pipeline

    def _get_voice_tensor(self, voice_name: str):
        if voice_name in self._voice_cache:
            return self._voice_cache[voice_name]
        pipeline = self._get_pipeline()
        local_voice_file = VOICES_DIR / f"{voice_name}.pt"
        if local_voice_file.exists():
            logger.info("Loading voice '%s' from local weights at %s", voice_name, local_voice_file)
            voice_tensor = pipeline.load_voice(str(local_voice_file))
            self._voice_cache[voice_name] = voice_tensor
            return voice_tensor
        return voice_name

    def warm_up(self):
        """Warm up Kokoro so first synthesis does not suffer model-load latency."""
        try:
            p = self._get_pipeline()
            voice_obj = self._get_voice_tensor(self.voice)
            # Generate a 1-word warm up
            for _ in p("Ready.", voice=voice_obj, speed=self.speed):
                pass
            logger.info("Kokoro voice service warmed up successfully.")
            return True
        except Exception as e:
            logger.warning("Kokoro warm-up failed: %s", e)
            return False

    def synthesize_with_timestamps(self, text: str, speed: Optional[float] = None) -> Dict[str, Any]:
        """
        Synthesize text into a single 24kHz WAV and compute word-level timestamps.
        Returns:
            {
                "audio_base64": "data:audio/wav;base64,...",
                "sample_rate": 24000,
                "duration": float,
                "words": [{"word": str, "start": float, "end": float}]
            }
        """
        if not text or not text.strip():
            raise ValueError("Text for synthesis cannot be empty.")

        clean_text = text.strip()
        effective_speed = speed or self.speed

        cache_key = f"{round(effective_speed, 2)}:{clean_text}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        import torch
        pipeline = self._get_pipeline()

        all_chunks: List[np.ndarray] = []
        all_words: List[Dict[str, Any]] = []
        current_time = 0.0

        voice_obj = self._get_voice_tensor(self.voice)
        with torch.inference_mode():
            for gs, _, audio in pipeline(clean_text, voice=voice_obj, speed=effective_speed):
                if audio is None:
                    continue
                chunk = np.asarray(audio, dtype=np.float32).reshape(-1)
                if chunk.size == 0:
                    continue

                all_chunks.append(chunk)
                chunk_duration = float(chunk.size) / float(SAMPLE_RATE)

                # Match words in grapheme chunk
                words_in_chunk = re.findall(r'\S+', gs)
                if words_in_chunk:
                    # Distribute duration proportionally across words by character length
                    total_chars = sum(len(w) for w in words_in_chunk)
                    word_time = current_time
                    for w in words_in_chunk:
                        w_dur = (len(w) / max(total_chars, 1)) * chunk_duration
                        all_words.append({
                            "word": w,
                            "start": round(word_time, 3),
                            "end": round(word_time + w_dur, 3)
                        })
                        word_time += w_dur

                current_time += chunk_duration

        if not all_chunks:
            raise RuntimeError("Kokoro produced no audio output.")

        # Concatenate and encode to 16-bit PCM WAV
        full_audio = np.concatenate(all_chunks)
        int16_audio = np.clip(full_audio * 32767.0, -32768, 32767).astype(np.int16)

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(int16_audio.tobytes())

        wav_bytes = wav_buffer.getvalue()
        b64_audio = base64.b64encode(wav_bytes).decode("ascii")
        data_uri = f"data:audio/wav;base64,{b64_audio}"

        result = {
            "audio_url": data_uri,
            "sample_rate": SAMPLE_RATE,
            "duration": round(current_time, 2),
            "words": all_words
        }

        # Keep cache bounded to MAX_CACHE_ENTRIES (~1GB RAM budget)
        if len(self._cache) >= MAX_CACHE_ENTRIES:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[cache_key] = result
        return result

# Global singleton
voice_service = KokoroVoiceService()
