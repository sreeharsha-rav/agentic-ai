"""MeetingContextBuilder -- Step 4 of the pipeline.

hybrid_enriched_log.json -> meeting_context.json

Builds rich topic-level multimodal context: groups speech segments into
topic clusters (silence gaps + duration cap + semantic drift), runs OCR +
spatial decomposition on every linked frame, strips meeting-wide boilerplate
UI text via document-frequency filtering, and produces a searchable
per-topic query string combining transcript, visual hierarchy, and keywords.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

from .config import ContextConfig, OCRConfig
from .ocr_engine import OCREngine
from .text_cleaning import clean_ocr_text, is_meaningful_text, normalize_whitespace
from .timecodes import format_clock

logger = logging.getLogger(__name__)


class MeetingContextBuilder:
    def __init__(
        self,
        output_dir: str,
        topic_gap_sec: float = 30.0,
        max_topic_duration_sec: float = 120.0,
        topic_similarity_threshold: float = 0.68,
        min_segments_before_semantic_split: int = 2,
        embeddings_enabled: bool = True,
        embedding_model: str = "all-MiniLM-L6-v2",
        embedding_device: str = "cpu",
        embedding_batch_size: int = 32,
        boilerplate_document_frequency: float = 0.65,
        min_frames_for_boilerplate: int = 4,
        dedup_jaccard_threshold: float = 0.65,
        keyword_ngram_size: int = 2,
        keyword_candidates: int = 6,
        max_keywords: int = 8,
        max_visual_content_lines: int = 15,
        searchable_query_max_chars: int = 6000,
        ocr_config: OCRConfig | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.topic_gap_sec = topic_gap_sec
        self.max_topic_duration_sec = max_topic_duration_sec
        self.topic_similarity_threshold = topic_similarity_threshold
        self.min_segments_before_semantic_split = min_segments_before_semantic_split
        self.embedding_batch_size = embedding_batch_size
        self.boilerplate_document_frequency = boilerplate_document_frequency
        self.min_frames_for_boilerplate = min_frames_for_boilerplate
        self.dedup_jaccard_threshold = dedup_jaccard_threshold
        self.max_keywords = max_keywords
        self.max_visual_content_lines = max_visual_content_lines
        self.searchable_query_max_chars = searchable_query_max_chars

        self._ocr_config = ocr_config or OCRConfig()
        self.ocr_engine = OCREngine(self._ocr_config)
        self.spatial_ocr_mode = self._ocr_config.spatial_mode
        self.ocr_enabled = self._ocr_config.enabled

        self.embed_model = None
        self.use_embedding = embeddings_enabled
        if self.use_embedding:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info("Loading %s on %s", embedding_model, embedding_device)
                self.embed_model = SentenceTransformer(embedding_model, device=embedding_device)
            except Exception as exc:
                logger.warning("Embedding model load failed (%s), falling back to time-based grouping", exc)
                self.use_embedding = False

        self.kw_extractor = None
        try:
            import yake

            self.kw_extractor = yake.KeywordExtractor(lan="en", n=keyword_ngram_size, top=keyword_candidates, features=None)
        except Exception as exc:
            logger.debug("yake unavailable, keyword extraction disabled: %s", exc)

    @classmethod
    def from_config(
        cls, output_dir: str, context_config: ContextConfig, ocr_config: OCRConfig | None = None
    ) -> "MeetingContextBuilder":
        return cls(
            output_dir,
            topic_gap_sec=context_config.topic_gap_sec,
            max_topic_duration_sec=context_config.max_topic_duration_sec,
            topic_similarity_threshold=context_config.topic_similarity_threshold,
            min_segments_before_semantic_split=context_config.min_segments_before_semantic_split,
            embeddings_enabled=context_config.embeddings_enabled,
            embedding_model=context_config.embedding_model,
            embedding_device=context_config.embedding_device,
            embedding_batch_size=context_config.embedding_batch_size,
            boilerplate_document_frequency=context_config.boilerplate_document_frequency,
            min_frames_for_boilerplate=context_config.min_frames_for_boilerplate,
            dedup_jaccard_threshold=context_config.dedup_jaccard_threshold,
            keyword_ngram_size=context_config.keyword_ngram_size,
            keyword_candidates=context_config.keyword_candidates,
            max_keywords=context_config.max_keywords,
            max_visual_content_lines=context_config.max_visual_content_lines,
            searchable_query_max_chars=context_config.searchable_query_max_chars,
            ocr_config=ocr_config,
        )

    # ------------------------------------------------------------------ #

    def build_frame_aligned_timeline(self, log_path: str, frames_dir: str | None = None):
        logger.info("Step 1: loading %s", log_path)
        with open(log_path, encoding="utf-8") as f:
            log = json.load(f)
        log = sorted(log, key=lambda x: x.get("start_sec", 0))
        audio_entries = [e for e in log if e.get("source") == "audio" and e.get("text")]
        gap_entries = [e for e in log if e.get("source") == "gap"]
        logger.info("Total %d | Audio %d | Gap %d", len(log), len(audio_entries), len(gap_entries))
        logger.info("Spatial OCR mode: %s", self.spatial_ocr_mode)

        clean_timeline = []
        ocr_cache: dict[str, dict] = {}
        for i, entry in enumerate(audio_entries):
            frame_files = entry.get("frame_files") or ([entry.get("frame_file")] if entry.get("frame_file") else [])
            frame_timestamps = entry.get("frame_timestamps_sec") or [entry.get("start_sec")] * len(frame_files)
            frames_aligned = []
            for idx, ff in enumerate(frame_files):
                if not ff:
                    continue
                ts_sec = float(frame_timestamps[idx]) if idx < len(frame_timestamps) else float(entry.get("start_sec", 0))
                ocr_text = ""
                spatial_data = {"titles": [], "content": [], "details": [], "flat_text": ""}

                if frames_dir and self.ocr_enabled:
                    fp = Path(frames_dir) / ff
                    if ff in ocr_cache:
                        cached = ocr_cache[ff]
                        ocr_text = cached.get("flat_text", "")
                        spatial_data = cached
                    elif fp.exists():
                        if self.spatial_ocr_mode == "spatial_hierarchical":
                            spatial_data = self.ocr_engine.extract_spatial(str(fp))
                            ocr_text = spatial_data.get("flat_text", "")
                        else:
                            ocr_text = clean_ocr_text(
                                self.ocr_engine.extract(str(fp)),
                                extra_noise_patterns=self._ocr_config.extra_noise_patterns,
                                max_chars=self._ocr_config.max_clean_text_chars,
                            )
                            spatial_data = {
                                "titles": [],
                                "content": [ocr_text] if ocr_text else [],
                                "details": [],
                                "flat_text": ocr_text,
                            }
                        ocr_cache[ff] = spatial_data

                frames_aligned.append(
                    {
                        "file": ff,
                        "timestamp_sec": ts_sec,
                        "timestamp": format_clock(ts_sec),
                        "is_primary": ff == entry.get("frame_file"),
                        "ocr_text": ocr_text,
                        "spatial_titles": spatial_data.get("titles", []),
                        "spatial_content": spatial_data.get("content", []),
                        "spatial_details": spatial_data.get("details", []),
                    }
                )
            clean_timeline.append(
                {
                    "segment_id": f"seg_{i:03d}",
                    "start_sec": float(entry.get("start_sec", 0)),
                    "end_sec": float(entry.get("end_sec", 0)),
                    "start_time": entry.get("transcript_start") or format_clock(entry.get("start_sec", 0)),
                    "end_time": entry.get("transcript_end") or format_clock(entry.get("end_sec", 0)),
                    "duration_sec": round(float(entry.get("end_sec", 0) - entry.get("start_sec", 0)), 2),
                    "speaker": entry.get("speaker", "Unknown"),
                    "transcript": normalize_whitespace(entry.get("text", "")),
                    "frames": frames_aligned,
                    "frame_count": len(frames_aligned),
                }
            )
        logger.info("Built %d segments, %d OCR'd", len(clean_timeline), len(ocr_cache))
        return clean_timeline, gap_entries

    def build_topics(self, clean_timeline: list[dict]) -> list[list[dict]]:
        """Groups chronological segments into topic blocks via temporal + semantic boundaries."""
        logger.info("Step 2: topics window gap=%ss", self.topic_gap_sec)
        if not clean_timeline:
            return []

        embeddings = None
        if self.use_embedding and self.embed_model:
            try:
                texts = [f"{s['speaker']}: {s['transcript']}" for s in clean_timeline]
                logger.info("Batch embedding...")
                embeddings = self.embed_model.encode(
                    texts,
                    batch_size=self.embedding_batch_size,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                )
            except Exception as exc:
                logger.warning("Embedding failed (%s), using time-based grouping only", exc)
                embeddings = None

        topics: list[list[dict]] = []
        cur: list[dict] = []
        cur_start = None
        cur_mean = None
        for idx, seg in enumerate(clean_timeline):
            if not cur:
                cur = [seg]
                cur_start = seg["start_sec"]
                if embeddings is not None:
                    cur_mean = embeddings[idx]
                continue

            gap = seg["start_sec"] - cur[-1]["end_sec"]
            dur = seg["end_sec"] - cur_start
            split = False

            if gap > self.topic_gap_sec:
                split = True
            elif dur > self.max_topic_duration_sec:
                split = True
            elif embeddings is not None:
                sim = float(np.dot(embeddings[idx], cur_mean))
                if sim < self.topic_similarity_threshold and len(cur) >= self.min_segments_before_semantic_split:
                    split = True
                if not split:
                    n = len(cur)
                    cur_mean = (cur_mean * n + embeddings[idx]) / (n + 1)
                    cur_mean = cur_mean / ((cur_mean**2).sum() ** 0.5 + 1e-9)

            if split:
                topics.append(cur)
                cur = [seg]
                cur_start = seg["start_sec"]
                if embeddings is not None:
                    cur_mean = embeddings[idx]
            else:
                cur.append(seg)

        if cur:
            topics.append(cur)
        logger.info("%d segs -> %d topics", len(clean_timeline), len(topics))
        return topics

    def build_matchable_context(self, topics: list[list[dict]]) -> list[dict]:
        """Synthesizes multimodal context dicts for each topic cluster."""
        logger.info("Step 3: building contexts (mode=%s)", self.spatial_ocr_mode)

        # Meeting-wide OCR-token document frequency, to identify static UI chrome.
        all_unique_frames: dict[str, set[str]] = {}
        for segs in topics:
            for s in segs:
                for fr in s["frames"]:
                    if fr["file"] not in all_unique_frames and fr.get("ocr_text"):
                        all_unique_frames[fr["file"]] = set(re.findall(r"\b[a-zA-Z]{3,}\b", fr["ocr_text"].lower()))

        total_ocr_frames = len(all_unique_frames)
        boilerplate_tokens: set[str] = set()
        if total_ocr_frames >= self.min_frames_for_boilerplate:
            token_frame_counts: dict[str, int] = defaultdict(int)
            for f_tokens in all_unique_frames.values():
                for tok in f_tokens:
                    token_frame_counts[tok] += 1
            for tok, cnt in token_frame_counts.items():
                if (cnt / total_ocr_frames) > self.boilerplate_document_frequency:
                    boilerplate_tokens.add(tok)
            if boilerplate_tokens:
                logger.info("Identified %d static meeting-wide UI boilerplate token(s)", len(boilerplate_tokens))

        def _clean_and_dedup(text_list: list[str]) -> list[str]:
            uniq: list[str] = []
            seen_sets: list[set[str]] = []
            for t in text_list:
                if not t:
                    continue
                if boilerplate_tokens:
                    filtered = [w for w in t.split() if w.lower() not in boilerplate_tokens]
                    cleaned_t = " ".join(filtered).strip()
                else:
                    cleaned_t = t.strip()
                if not is_meaningful_text(cleaned_t):
                    continue
                cur_set = set(re.findall(r"\b[a-zA-Z]{3,}\b", cleaned_t.lower()))
                if not cur_set:
                    continue
                if not any(
                    (len(cur_set & s) / max(len(cur_set | s), 1)) > self.dedup_jaccard_threshold for s in seen_sets
                ):
                    seen_sets.append(cur_set)
                    uniq.append(cleaned_t)
            return uniq

        contexts = []
        for tid, segs in enumerate(topics):
            start_sec = min(s["start_sec"] for s in segs)
            end_sec = max(s["end_sec"] for s in segs)

            spk_map: dict[str, list[str]] = defaultdict(list)
            for s in segs:
                spk_map[s["speaker"]].append(s["transcript"])
            agg_transcript = "\n".join(f"{spk}: {' '.join(t)}" for spk, t in spk_map.items())

            all_frames = []
            seen = set()
            raw_titles, raw_content, raw_details, all_ocr_texts = [], [], [], []

            for s in segs:
                for fr in s["frames"]:
                    if fr["file"] not in seen:
                        seen.add(fr["file"])
                        all_frames.append(fr)
                        if fr.get("ocr_text"):
                            all_ocr_texts.append(fr["ocr_text"])
                        raw_titles.extend(fr.get("spatial_titles", []))
                        raw_content.extend(fr.get("spatial_content", []))
                        raw_details.extend(fr.get("spatial_details", []))
            all_frames = sorted(all_frames, key=lambda x: x["timestamp_sec"])

            clean_titles = _clean_and_dedup(raw_titles)
            clean_content = _clean_and_dedup(raw_content if raw_content else all_ocr_texts)
            clean_details = _clean_and_dedup(raw_details)
            uniq_ocr = clean_titles + clean_content

            keywords: list[str] = []
            if self.kw_extractor:
                try:
                    comb = agg_transcript + " " + " ".join(clean_titles * 2 + clean_content)
                    if comb.strip():
                        kws = self.kw_extractor.extract_keywords(comb)
                        keywords = [k for k, _ in kws][: self.max_keywords]
                except Exception as exc:
                    logger.debug("Keyword extraction failed for topic_%03d: %s", tid, exc)

            searchable_parts = [agg_transcript]
            if clean_titles:
                searchable_parts.append(f"[VISUAL_TITLES]: {' | '.join(clean_titles)}")
            if clean_content:
                searchable_parts.append(
                    f"[VISUAL_CONTENT]: {' | '.join(clean_content[: self.max_visual_content_lines])}"
                )
            if keywords:
                searchable_parts.append(f"[KEYWORDS]: {', '.join(keywords)}")
            searchable = "\n".join(searchable_parts)

            contexts.append(
                {
                    "topic_id": f"topic_{tid:03d}",
                    "start_sec": float(start_sec),
                    "end_sec": float(end_sec),
                    "start_time": format_clock(start_sec),
                    "end_time": format_clock(end_sec),
                    "duration_sec": round(float(end_sec - start_sec), 2),
                    "speakers": list(spk_map.keys()),
                    "segment_ids": [s["segment_id"] for s in segs],
                    "segment_count": len(segs),
                    "transcript_aggregated": agg_transcript,
                    "visual_hierarchy": {"titles": clean_titles, "content": clean_content, "details": clean_details},
                    "visual_texts": uniq_ocr,
                    "keywords": keywords,
                    "frames": all_frames,
                    "frame_count": len(all_frames),
                    "primary_frame": all_frames[0]["file"] if all_frames else None,
                    "searchable_query": searchable[: self.searchable_query_max_chars],
                }
            )
        return contexts

    def save(self, clean_timeline: list[dict], gap_entries: list[dict], contexts: list[dict]):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        p1 = self.output_dir / "meeting_timeline_clean.json"
        with open(p1, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "meta": {
                        "total_segments": len(clean_timeline),
                        "ocr_backend": self.ocr_engine.backend,
                        "embedding_used": self.use_embedding,
                        "spatial_ocr_mode": self.spatial_ocr_mode,
                    },
                    "timeline": clean_timeline,
                    "gap_visuals": gap_entries,
                },
                f,
                indent=2,
            )
        p2 = self.output_dir / "meeting_context.json"
        with open(p2, "w", encoding="utf-8") as f:
            json.dump(contexts, f, indent=2)
        p3 = self.output_dir / "meeting_context_for_matching.jsonl"
        with open(p3, "w", encoding="utf-8") as f:
            for ctx in contexts:
                f.write(
                    json.dumps(
                        {
                            "topic_id": ctx["topic_id"],
                            "start_sec": ctx["start_sec"],
                            "end_sec": ctx["end_sec"],
                            "searchable_query": ctx["searchable_query"],
                            "frame_count": ctx["frame_count"],
                            "primary_frame": ctx["primary_frame"],
                        }
                    )
                    + "\n"
                )
        logger.info("Saved to %s: %s, %s, %s", self.output_dir, p1.name, p2.name, p3.name)
        return p1, p2, p3

    def run(self, log_path: str, frames_dir: str | None = None):
        clean, gaps = self.build_frame_aligned_timeline(log_path, frames_dir)
        topics = self.build_topics(clean)
        ctx = self.build_matchable_context(topics)
        return self.save(clean, gaps, ctx)
