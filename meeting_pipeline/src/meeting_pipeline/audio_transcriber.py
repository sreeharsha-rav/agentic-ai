"""AudioTranscriber -- Step 0 of the pipeline.

Extracts audio from a video via ffmpeg, then runs faster-whisper locally to
produce a VTT transcript that is time-aligned with the source video (as
opposed to relying on an externally-supplied VTT, which risks a timestamp
mismatch against the actual recording).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

from .config import TranscriptionConfig
from .errors import FFmpegError, FFmpegNotFoundError
from .timecodes import format_vtt_timestamp

logger = logging.getLogger(__name__)


class AudioTranscriber:
    """Extracts audio from video and transcribes it using faster-whisper.

    Writes a VTT file guaranteed to be time-aligned with the input video.
    Suitable for any meeting type (technical, business, design, syncs, reviews).
    """

    def __init__(
        self,
        model_size: str = "base.en",
        device: str = "cpu",
        compute_type: str = "default",
        initial_prompt: str | None = None,
        *,
        beam_size: int = 5,
        temperatures: tuple[float, ...] = (0.0, 0.2, 0.4),
        condition_on_previous_text: bool = False,
        repetition_penalty: float = 1.1,
        vad_filter: bool = False,
        word_timestamps: bool = False,
        ffmpeg_path: str = "ffmpeg",
        audio_filter: str = "highpass=f=80,loudnorm",
        audio_sample_rate: int = 16000,
        audio_channels: int = 1,
    ) -> None:
        """
        Args:
            model_size: Whisper model size (e.g. ``base.en``, ``small.en``,
                ``medium.en``). English-specialized (``.en``) models are more
                accurate for English speech.
            device: ``"cpu"`` or ``"cuda"``.
            compute_type: ``"default"`` is safest/fastest on CPU.
            initial_prompt: optional context/agenda/vocabulary string to
                prime Whisper for a specific meeting. If ``None``, a neutral
                meeting primer is used (``TranscriptionConfig.DEFAULT_INITIAL_PROMPT``)
                to avoid domain bias.
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.initial_prompt = (
            initial_prompt if initial_prompt is not None else TranscriptionConfig.DEFAULT_INITIAL_PROMPT
        )
        self.beam_size = beam_size
        self.temperatures = temperatures
        self.condition_on_previous_text = condition_on_previous_text
        self.repetition_penalty = repetition_penalty
        self.vad_filter = vad_filter
        self.word_timestamps = word_timestamps
        self.ffmpeg_path = ffmpeg_path
        self.audio_filter = audio_filter
        self.audio_sample_rate = audio_sample_rate
        self.audio_channels = audio_channels
        self._model = None  # lazy-loaded

    @classmethod
    def from_config(cls, config: TranscriptionConfig) -> "AudioTranscriber":
        return cls(
            model_size=config.model_size,
            device=config.device,
            compute_type=config.compute_type,
            initial_prompt=config.initial_prompt,
            beam_size=config.beam_size,
            temperatures=config.temperatures,
            condition_on_previous_text=config.condition_on_previous_text,
            repetition_penalty=config.repetition_penalty,
            vad_filter=config.vad_filter,
            word_timestamps=config.word_timestamps,
            ffmpeg_path=config.ffmpeg_path,
            audio_filter=config.audio_filter,
            audio_sample_rate=config.audio_sample_rate,
            audio_channels=config.audio_channels,
        )

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            logger.info(
                "Loading Whisper '%s' model on %s (compute=%s)",
                self.model_size,
                self.device,
                self.compute_type,
            )
            self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        return self._model

    def extract_audio(self, video_path: str, audio_path: str) -> str:
        """Extract mono WAV audio from the video using ffmpeg.

        Applies ``audio_filter`` (default: high-pass rumble filtering + volume
        normalization) and falls back to a plain extraction if the local
        ffmpeg build doesn't support the filter (e.g. missing libebur128).
        """
        if os.path.exists(audio_path):
            logger.info("Audio already extracted: %s", audio_path)
            return audio_path

        if shutil.which(self.ffmpeg_path) is None:
            raise FFmpegNotFoundError(self.ffmpeg_path)

        logger.info("Extracting audio from video (filter=%s)", self.audio_filter)
        codec_args = [
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(self.audio_sample_rate),
            "-ac",
            str(self.audio_channels),
        ]
        cmd_filtered = [
            self.ffmpeg_path,
            "-y",
            "-i",
            video_path,
            "-vn",
            "-af",
            self.audio_filter,
            *codec_args,
            audio_path,
        ]
        result = subprocess.run(cmd_filtered, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("ffmpeg filter failed, retrying basic extraction: %s", result.stderr)
            cmd_basic = [self.ffmpeg_path, "-y", "-i", video_path, "-vn", *codec_args, audio_path]
            result_basic = subprocess.run(cmd_basic, capture_output=True, text=True)
            if result_basic.returncode != 0:
                raise FFmpegError(f"ffmpeg failed:\n{result_basic.stderr}")

        logger.info("Audio saved: %s", audio_path)
        return audio_path

    def transcribe(
        self,
        audio_path: str,
        vtt_path: str,
        language: str = "en",
        initial_prompt: str | None = None,
    ) -> str:
        """Transcribe the audio using faster-whisper and write a VTT file.

        Returns the path to the generated VTT file.
        """
        model = self._load_model()
        prompt = initial_prompt if initial_prompt is not None else self.initial_prompt
        logger.info("Transcribing audio (model=%s, language=%s)", self.model_size, language)

        # Anti-hallucination decoding configuration.
        segments, info = model.transcribe(
            audio_path,
            language=language,
            initial_prompt=prompt,
            beam_size=self.beam_size,
            temperature=list(self.temperatures),
            condition_on_previous_text=self.condition_on_previous_text,
            repetition_penalty=self.repetition_penalty,
            word_timestamps=self.word_timestamps,
            vad_filter=self.vad_filter,
        )
        logger.info("Detected language: %s (confidence: %.2f)", info.language, info.language_probability)

        os.makedirs(os.path.dirname(vtt_path) or ".", exist_ok=True)
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for i, seg in enumerate(segments):
                start = format_vtt_timestamp(seg.start)
                end = format_vtt_timestamp(seg.end)
                text = seg.text.strip()
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

        logger.info("Transcript saved: %s", vtt_path)
        return vtt_path

    def run(
        self,
        video_path: str,
        output_dir: str,
        language: str = "en",
        initial_prompt: str | None = None,
    ) -> str:
        """Full stage: extract audio -> transcribe -> return the VTT path."""
        os.makedirs(output_dir, exist_ok=True)
        audio_path = os.path.join(output_dir, "extracted_audio.wav")
        vtt_path = os.path.join(output_dir, "generated_transcript.vtt")

        self.extract_audio(video_path, audio_path)
        self.transcribe(audio_path, vtt_path, language=language, initial_prompt=initial_prompt)
        return vtt_path
