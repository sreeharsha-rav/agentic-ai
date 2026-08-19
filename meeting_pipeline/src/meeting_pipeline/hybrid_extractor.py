"""HybridExtractor -- Steps 1-3 of the pipeline: frame extraction.

  Step 1 - Audio-Anchored: extract frames at speech-chunk timestamps (O(1) seeks).
  Step 2 - Visual Gap Scanner: MSE-based scene detection only within silent gaps.
  Step 3 - Merge + Deduplicate: SSIM dedup across both frame sets -> one unified log.
"""

from __future__ import annotations

import json
import logging
import os

import cv2
import numpy as np

from .config import FrameExtractionConfig
from .errors import VideoOpenError
from .image_metrics import compute_ssim, content_score, laplacian_variance
from .timecodes import format_hms
from .transcript import parse_vtt_chunks

logger = logging.getLogger(__name__)


class HybridExtractor:
    def __init__(
        self,
        output_dir: str,
        ssim_threshold: float = 0.92,
        mse_threshold: float = 500.0,
        chunk_gap_seconds: float = 5.0,
        max_chunk_duration_seconds: float = 30.0,
        min_gap_duration_seconds: float = 5.0,  # ignore tiny gaps < this
        gap_sample_interval_seconds: float = 5.0,  # how often to sample during a gap
        frame_sample_count: int = 5,  # candidate frames sampled per chunk
        content_score_threshold: float = 0.15,  # below this -> webcam-only, skip frame
        intra_chunk_ssim_threshold: float = 0.85,  # below this -> new visual scene within chunk
        delete_deduped_frames: bool = False,
    ) -> None:
        self.output_dir = output_dir
        self.ssim_threshold = ssim_threshold
        self.mse_threshold = mse_threshold
        self.chunk_gap_seconds = chunk_gap_seconds
        self.max_chunk_duration_seconds = max_chunk_duration_seconds
        self.min_gap_duration_seconds = min_gap_duration_seconds
        self.gap_sample_interval_seconds = gap_sample_interval_seconds
        self.frame_sample_count = frame_sample_count
        self.content_score_threshold = content_score_threshold
        self.intra_chunk_ssim_threshold = intra_chunk_ssim_threshold
        self.delete_deduped_frames = delete_deduped_frames

        self.hybrid_dir = os.path.join(output_dir, "video", "hybrid")

    @classmethod
    def from_config(cls, output_dir: str, config: FrameExtractionConfig) -> "HybridExtractor":
        return cls(
            output_dir,
            ssim_threshold=config.ssim_threshold,
            mse_threshold=config.mse_threshold,
            chunk_gap_seconds=config.chunk_gap_seconds,
            max_chunk_duration_seconds=config.max_chunk_duration_seconds,
            min_gap_duration_seconds=config.min_gap_duration_seconds,
            gap_sample_interval_seconds=config.gap_sample_interval_seconds,
            frame_sample_count=config.frame_sample_count,
            content_score_threshold=config.content_score_threshold,
            intra_chunk_ssim_threshold=config.intra_chunk_ssim_threshold,
            delete_deduped_frames=config.delete_deduped_frames,
        )

    # ------------------------------------------------------------------ #
    #  STEP 1: VTT Parsing & Audio-Anchored Extraction                   #
    # ------------------------------------------------------------------ #

    def _parse_transcript(self, vtt_path: str) -> list[dict]:
        return parse_vtt_chunks(
            vtt_path,
            chunk_gap_seconds=self.chunk_gap_seconds,
            max_chunk_duration_seconds=self.max_chunk_duration_seconds,
        )

    # ------------------------------------------------------------------ #
    #  STEP 1 helpers: Content Filter + Intra-Chunk Scene Detection      #
    # ------------------------------------------------------------------ #

    def _extract_chunk_frames(self, cap, start_sec: float, end_sec: float):
        """
        Sample ``frame_sample_count`` frames evenly across [start_sec, end_sec].

        For each sample:
          - Compute content_score -- skip if below threshold (webcam-only).
          - Detect scene changes within the chunk using SSIM.
          - Within each scene, keep the frame with the highest sharpness
            (Laplacian variance).

        Returns a list of ``(frame_ndarray, timestamp_sec)`` -- one entry per
        distinct visual scene that passed the content filter.
        """
        duration = end_sec - start_sec
        if duration <= 0:
            return []

        n = max(1, self.frame_sample_count)
        if n == 1:
            timestamps = [start_sec + duration / 2.0]
        else:
            step = duration / (n - 1)
            timestamps = [start_sec + i * step for i in range(n)]

        # --- pass 1: collect content frames and their sharpness ---
        content_samples = []  # list of (gray_small, frame, ts, lap_var)
        for ts in timestamps:
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            ret, frame = cap.read()
            if not ret:
                continue
            score = content_score(frame)
            if score < self.content_score_threshold:
                continue  # webcam-only -- skip
            gray = cv2.cvtColor(cv2.resize(frame, (640, 360)), cv2.COLOR_BGR2GRAY)
            lap_var = laplacian_variance(gray)
            content_samples.append((gray, frame, ts, lap_var))

        if not content_samples:
            return []

        # --- pass 2: intra-chunk scene detection + best-frame selection ---
        scenes = []
        scene_best_gray = None
        scene_best_frame = None
        scene_best_ts = None
        scene_best_lap = -1.0

        for gray, frame, ts, lap_var in content_samples:
            if scene_best_gray is None:
                scene_best_gray, scene_best_frame, scene_best_ts, scene_best_lap = gray, frame, ts, lap_var
            else:
                ssim_val = compute_ssim(scene_best_gray, gray)
                if ssim_val < self.intra_chunk_ssim_threshold:
                    # scene change detected -- commit current scene's best frame
                    scenes.append((scene_best_frame, scene_best_ts))
                    scene_best_gray, scene_best_frame, scene_best_ts, scene_best_lap = gray, frame, ts, lap_var
                elif lap_var > scene_best_lap:
                    # same scene -- keep the sharper frame
                    scene_best_gray, scene_best_frame, scene_best_ts, scene_best_lap = gray, frame, ts, lap_var

        if scene_best_frame is not None:
            scenes.append((scene_best_frame, scene_best_ts))

        return scenes  # [(ndarray, float), ...]

    # ------------------------------------------------------------------ #
    #  STEP 1: Audio-Anchored Extraction (multi-frame per chunk)          #
    # ------------------------------------------------------------------ #

    def _extract_audio_anchored(self, cap, chunks: list[dict], hybrid_dir: str) -> list[dict]:
        """
        Extract a group of content frames per speech chunk.

        Each chunk emits one log entry with:
          frame_file           -- primary frame (backward compat, first scene)
          frame_files          -- all content frames from this chunk
          frame_timestamps_sec -- video timestamps for each saved frame
          scene_count          -- number of distinct visual scenes detected
          content_frames_found -- total content-passing samples before dedup
        """
        logger.info("STEP 1: Audio-Anchored Extraction (multi-frame + content filter)")
        frames = []
        last_gray = None  # gray of first frame of previous chunk (for cross-chunk dedup)
        last_file = None  # fallback frame_file when entire chunk is duplicate

        for chunk in chunks:
            scene_frames = self._extract_chunk_frames(cap, chunk["start_sec"], chunk["end_sec"])
            content_frames_found = len(scene_frames)

            if not scene_frames:
                logger.debug(
                    "[audio] %s -> no content screen detected, linking to %s",
                    chunk["transcript_start"],
                    last_file,
                )
                frames.append(
                    {
                        "source": "audio",
                        "start_sec": chunk["start_sec"],
                        "end_sec": chunk["end_sec"],
                        "transcript_start": chunk["transcript_start"],
                        "transcript_end": chunk["transcript_end"],
                        "speaker": chunk["speaker"],
                        "text": chunk["text"],
                        "frame_file": last_file,
                        "frame_files": [last_file] if last_file else [],
                        "frame_timestamps_sec": [],
                        "scene_count": 0,
                        "content_frames_found": 0,
                        "is_duplicate": True,
                    }
                )
                continue

            # Cross-chunk SSIM dedup: compare first scene frame of this chunk
            # against the saved gray of the previous chunk's first frame.
            first_frame, first_ts = scene_frames[0]
            first_gray = cv2.cvtColor(cv2.resize(first_frame, (640, 360)), cv2.COLOR_BGR2GRAY)
            is_dup = last_gray is not None and compute_ssim(last_gray, first_gray) > self.ssim_threshold

            saved_fnames: list[str] = []
            saved_ts: list[float] = []

            if is_dup:
                logger.debug(
                    "[audio] %s -> duplicate chunk, linked to %s", chunk["transcript_start"], last_file
                )
                saved_fnames = [last_file] if last_file else []
            else:
                for scene_img, scene_ts in scene_frames:
                    hh, mm, ss = int(scene_ts // 3600), int((scene_ts % 3600) // 60), int(scene_ts % 60)
                    fname = f"frame_{hh:02d}_{mm:02d}_{ss:02d}.png"
                    cv2.imwrite(os.path.join(hybrid_dir, fname), scene_img)
                    saved_fnames.append(fname)
                    saved_ts.append(round(scene_ts, 2))

                logger.debug(
                    "[audio] %s -> %d scene(s): %s", chunk["transcript_start"], len(saved_fnames), saved_fnames
                )
                last_gray = first_gray
                last_file = saved_fnames[0]

            frames.append(
                {
                    "source": "audio",
                    "start_sec": chunk["start_sec"],
                    "end_sec": chunk["end_sec"],
                    "transcript_start": chunk["transcript_start"],
                    "transcript_end": chunk["transcript_end"],
                    "speaker": chunk["speaker"],
                    "text": chunk["text"],
                    "frame_file": saved_fnames[0] if saved_fnames else None,
                    "frame_files": saved_fnames,
                    "frame_timestamps_sec": saved_ts,
                    "scene_count": len(scene_frames) if not is_dup else 0,
                    "content_frames_found": content_frames_found,
                    "is_duplicate": is_dup,
                }
            )

        unique = sum(1 for f in frames if not f["is_duplicate"])
        total_scenes = sum(f.get("scene_count", 0) for f in frames)
        no_content = sum(1 for f in frames if f.get("content_frames_found", 0) == 0)
        logger.info(
            "%d unique chunks | %d total scene frames | %d chunks with no content screen",
            unique,
            total_scenes,
            no_content,
        )
        return frames

    # ------------------------------------------------------------------ #
    #  STEP 2: Visual Gap Scanner                                         #
    # ------------------------------------------------------------------ #

    def _compute_silent_gaps(self, chunks: list[dict], transcript_end_sec: float) -> list[tuple[float, float]]:
        """Silent windows between speech chunks, capped at ``transcript_end_sec``."""
        gaps = []
        prev_end = 0.0
        for chunk in chunks:
            gap_start, gap_end = prev_end, chunk["start_sec"]
            if gap_end - gap_start >= self.min_gap_duration_seconds:
                gaps.append((gap_start, gap_end))
            prev_end = chunk["end_sec"]
        if transcript_end_sec - prev_end >= self.min_gap_duration_seconds:
            gaps.append((prev_end, transcript_end_sec))
        return gaps

    def _scan_gaps(self, cap, gaps: list[tuple[float, float]], hybrid_dir: str) -> list[dict]:
        """MSE-based scene detection within silent gap windows only."""
        logger.info("STEP 2: Visual Gap Scanner -- scanning %d silent window(s)", len(gaps))
        gap_frames = []

        for gap_start, gap_end in gaps:
            logger.debug("Scanning gap [%s -> %s]", format_hms(gap_start), format_hms(gap_end))
            t = gap_start
            last_gray = None

            while t <= gap_end:
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ret, frame = cap.read()
                if not ret:
                    t += self.gap_sample_interval_seconds
                    continue

                # Inlined rather than image_metrics.compute_mse(a, b): that
                # helper reprocesses both images every call, but here
                # last_gray is deliberately cached across iterations so each
                # step only resizes/converts the *new* frame.
                gray = cv2.cvtColor(cv2.resize(frame, (320, 180)), cv2.COLOR_BGR2GRAY).astype(np.float32)
                if last_gray is None:
                    mse = self.mse_threshold + 1  # force the first frame in a gap to be captured
                else:
                    mse = float(np.mean((gray - last_gray) ** 2))

                if mse > self.mse_threshold:
                    hh, mm, ss = int(t // 3600), int((t % 3600) // 60), int(t % 60)
                    fname = f"frame_{hh:02d}_{mm:02d}_{ss:02d}_gap.png"
                    cv2.imwrite(os.path.join(hybrid_dir, fname), frame)
                    logger.debug("[gap ] %s -> saved %s (MSE=%.0f)", format_hms(t), fname, mse)
                    last_gray = gray
                    gap_frames.append(
                        {
                            "source": "gap",
                            "start_sec": t,
                            "end_sec": min(t + self.gap_sample_interval_seconds, gap_end),
                            "transcript_start": format_hms(t),
                            "transcript_end": format_hms(min(t + self.gap_sample_interval_seconds, gap_end)),
                            "speaker": None,
                            "text": None,
                            "frame_file": fname,
                            "is_duplicate": False,
                        }
                    )

                t += self.gap_sample_interval_seconds

        logger.info("%d additional frames from gap scanner", len(gap_frames))
        return gap_frames

    # ------------------------------------------------------------------ #
    #  STEP 3: Merge + Deduplicate                                        #
    # ------------------------------------------------------------------ #

    def _merge_and_dedup(self, audio_frames: list[dict], gap_frames: list[dict], hybrid_dir: str) -> list[dict]:
        """Merge audio and gap frames sorted by time; run one final SSIM dedup pass."""
        logger.info("STEP 3: Merge + Deduplicate")
        combined = sorted(audio_frames + gap_frames, key=lambda x: x["start_sec"])

        deduped = []
        last_gray = None

        for entry in combined:
            fname = entry.get("frame_file")
            if not fname:
                # No linked frame at all (e.g. the first speech chunk in the
                # meeting was webcam-only, so there's no prior frame to link
                # to either) -- keep the entry, nothing to dedup against.
                deduped.append(entry)
                continue

            fpath = os.path.join(hybrid_dir, fname)
            if not os.path.exists(fpath):
                deduped.append(entry)
                continue

            frame = cv2.imread(fpath)
            if frame is None:
                deduped.append(entry)
                continue

            gray = cv2.cvtColor(cv2.resize(frame, (640, 360)), cv2.COLOR_BGR2GRAY)

            if last_gray is not None:
                ssim = compute_ssim(last_gray, gray)
                if ssim > self.ssim_threshold:
                    logger.debug(
                        "[dedup] %s -> duplicate removed (SSIM=%.3f)", entry["transcript_start"], ssim
                    )
                    if self.delete_deduped_frames:
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
                    continue  # drop the entry (and optionally its file)

            last_gray = gray
            entry["start_time_format"] = format_hms(entry["start_sec"])
            entry["end_time_format"] = format_hms(entry["end_sec"])
            deduped.append(entry)

        logger.info("%d unique frames after merge dedup", len(deduped))
        return deduped

    # ------------------------------------------------------------------ #
    #  PUBLIC: run full hybrid pipeline                                    #
    # ------------------------------------------------------------------ #

    def run(self, video_path: str, vtt_path: str) -> list[dict]:
        os.makedirs(self.hybrid_dir, exist_ok=True)

        logger.info("Parsing VTT transcript")
        chunks = self._parse_transcript(vtt_path)
        logger.info("%d speech chunks", len(chunks))

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise VideoOpenError(video_path)

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        video_duration = total_frames / fps if fps > 0 else 0
        logger.info("Video: %s (%d frames @ %.1f fps)", format_hms(video_duration), int(total_frames), fps)

        # Gap scanning spans the entire video -- important slides/code are
        # often left on screen silently after the last spoken word.
        transcript_end_sec = video_duration

        audio_frames = self._extract_audio_anchored(cap, chunks, self.hybrid_dir)
        gaps = self._compute_silent_gaps(chunks, transcript_end_sec)
        gap_frames = self._scan_gaps(cap, gaps, self.hybrid_dir)

        cap.release()

        unified = self._merge_and_dedup(audio_frames, gap_frames, self.hybrid_dir)

        log_path = os.path.join(self.output_dir, "hybrid_enriched_log.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(unified, f, indent=2)

        logger.info("Done. Frames folder: %s | Unified log: %s", self.hybrid_dir, log_path)
        logger.info(
            "Total entries: %d | Audio-sourced: %d | Gap-sourced: %d",
            len(unified),
            sum(1 for e in unified if e["source"] == "audio"),
            sum(1 for e in unified if e["source"] == "gap"),
        )

        return unified
