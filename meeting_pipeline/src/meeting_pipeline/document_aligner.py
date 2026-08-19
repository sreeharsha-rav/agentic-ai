"""DocumentAligner -- Step 5 of the pipeline.

meeting_context.json -> aligned_context.json

Reads the rich topic-level context already built by MeetingContextBuilder
(transcript, OCR visual texts, keywords, frame list) and correlates it with
one or more external reference documents using three signals:

  Signal 1 - Semantic cosine  (sentence-transformers, all-MiniLM-L6-v2)
  Signal 2 - Keyword Jaccard  (YAKE keyword sets, topic vs chunk)
  Signal 3 - OCR text overlap (words from frame OCR that appear in a doc chunk)

Supported external document formats:
  .pdf            -> per-page text (PyMuPDF)
  .docx           -> per-paragraph groups (python-docx)
  .pptx           -> per-slide text (python-pptx)
  .md/.txt        -> per-double-newline block, with header breadcrumbs
  .png/.jpg/.jpeg -> OCR via OCREngine (same fallback chain as MeetingContextBuilder)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from .config import AlignmentConfig, OCRConfig
from .ocr_engine import OCREngine
from .text_cleaning import clean_ocr_text, normalize_whitespace, token_set

logger = logging.getLogger(__name__)


class DocumentAligner:
    """Aligns meeting topics (MeetingContextBuilder output) against external
    documents using multi-signal composite scoring, in two stages: a global
    document-level match, then a local section/chunk-level match within the
    winning document(s).
    """

    def __init__(
        self,
        output_dir: str,
        similarity_threshold: float = 0.25,
        high_confidence_threshold: float = 0.45,
        stage1_promote_threshold: float = 0.40,
        ocr_boost_weight: float = 0.35,
        keyword_boost_weight: float = 0.15,
        global_score_weight: float = 0.60,
        chunk_score_weight: float = 0.40,
        title_containment_threshold: float = 0.60,
        title_containment_boost: float = 0.90,
        embedding_model: str = "all-MiniLM-L6-v2",
        embedding_device: str = "cpu",
        embedding_batch_size: int = 32,
        keyword_ngram_size: int = 2,
        keyword_candidates: int = 10,
        min_pdf_chunk_chars: int = 30,
        min_pptx_chunk_chars: int = 20,
        min_text_block_chars: int = 25,
        min_image_ocr_chars: int = 20,
        ocr_config: OCRConfig | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.threshold = similarity_threshold
        self.high_confidence_threshold = high_confidence_threshold
        self.stage1_promote_threshold = stage1_promote_threshold
        self.ocr_boost_weight = ocr_boost_weight
        self.keyword_boost_weight = keyword_boost_weight
        self.global_score_weight = global_score_weight
        self.chunk_score_weight = chunk_score_weight
        self.title_containment_threshold = title_containment_threshold
        self.title_containment_boost = title_containment_boost
        self.embedding_batch_size = embedding_batch_size
        self.min_pdf_chunk_chars = min_pdf_chunk_chars
        self.min_pptx_chunk_chars = min_pptx_chunk_chars
        self.min_text_block_chars = min_text_block_chars
        self.min_image_ocr_chars = min_image_ocr_chars

        # Reuses OCREngine from ocr_engine.py for a consistent fallback chain
        # with MeetingContextBuilder -- a plain sibling import, no sys.path hack.
        logger.info("Initialising OCR engine for image documents")
        self.ocr_engine = OCREngine(ocr_config or OCRConfig())

        logger.info("Loading %s on %s", embedding_model, embedding_device)
        from sentence_transformers import SentenceTransformer

        self.embed_model = SentenceTransformer(embedding_model, device=embedding_device)
        logger.info("DocumentAligner ready")

        self.kw_extractor = None
        try:
            import yake

            self.kw_extractor = yake.KeywordExtractor(lan="en", n=keyword_ngram_size, top=keyword_candidates, features=None)
        except Exception as exc:
            logger.debug("yake unavailable, keyword extraction disabled: %s", exc)

    @classmethod
    def from_config(
        cls, output_dir: str, alignment_config: AlignmentConfig, ocr_config: OCRConfig | None = None
    ) -> "DocumentAligner":
        return cls(
            output_dir,
            similarity_threshold=alignment_config.similarity_threshold,
            high_confidence_threshold=alignment_config.high_confidence_threshold,
            stage1_promote_threshold=alignment_config.stage1_promote_threshold,
            ocr_boost_weight=alignment_config.ocr_boost_weight,
            keyword_boost_weight=alignment_config.keyword_boost_weight,
            global_score_weight=alignment_config.global_score_weight,
            chunk_score_weight=alignment_config.chunk_score_weight,
            title_containment_threshold=alignment_config.title_containment_threshold,
            title_containment_boost=alignment_config.title_containment_boost,
            embedding_model=alignment_config.embedding_model,
            embedding_device=alignment_config.embedding_device,
            embedding_batch_size=alignment_config.embedding_batch_size,
            keyword_ngram_size=alignment_config.keyword_ngram_size,
            keyword_candidates=alignment_config.keyword_candidates,
            min_pdf_chunk_chars=alignment_config.min_pdf_chunk_chars,
            min_pptx_chunk_chars=alignment_config.min_pptx_chunk_chars,
            min_text_block_chars=alignment_config.min_text_block_chars,
            min_image_ocr_chars=alignment_config.min_image_ocr_chars,
            ocr_config=ocr_config,
        )

    # ------------------------------------------------------------------
    # Scoring helpers -- both are pure functions of their arguments (no
    # instance state), kept as staticmethods so they're unit-testable
    # without constructing a DocumentAligner (which loads sentence-transformers).
    # ------------------------------------------------------------------

    def _extract_keywords(self, text: str) -> list[str]:
        if not text or not self.kw_extractor:
            return []
        try:
            return [kw.lower() for kw, _ in self.kw_extractor.extract_keywords(text)]
        except Exception as exc:
            logger.debug("Keyword extraction failed: %s", exc)
            return []

    @staticmethod
    def _keyword_jaccard(kw_a: list[str], kw_b: list[str]) -> float:
        if not kw_a or not kw_b:
            return 0.0
        a, b = set(kw_a), set(kw_b)
        union = len(a | b)
        return len(a & b) / union if union else 0.0

    @staticmethod
    def _ocr_overlap_score(
        visual_hierarchy: dict | None,
        visual_texts: list[str] | None,
        chunk_text: str,
        title_containment_threshold: float = 0.60,
        title_containment_boost: float = 0.90,
    ) -> float:
        """
        Computes visual-to-document match score using:
          1. Title containment: high weight if visual titles overlap with the doc chunk.
          2. Content overlap: token Jaccard/containment between visual text and doc chunk.
        """
        if not chunk_text:
            return 0.0
        chunk_tokens = token_set(chunk_text)
        if not chunk_tokens:
            return 0.0

        best_score = 0.0

        titles = visual_hierarchy.get("titles", []) if isinstance(visual_hierarchy, dict) else []
        for title in titles:
            t_tokens = token_set(title)
            if t_tokens:
                overlap = len(t_tokens & chunk_tokens) / len(t_tokens)
                if overlap >= title_containment_threshold:
                    best_score = max(best_score, title_containment_boost * overlap)

        all_visuals = list(visual_texts or [])
        if isinstance(visual_hierarchy, dict):
            all_visuals.extend(visual_hierarchy.get("content", []))

        for v_text in all_visuals:
            if not v_text or len(v_text.strip()) < 5:
                continue
            v_tokens = token_set(v_text)
            if v_tokens:
                forward_ratio = len(v_tokens & chunk_tokens) / len(v_tokens)
                backward_ratio = len(v_tokens & chunk_tokens) / len(chunk_tokens)
                best_score = max(best_score, forward_ratio, backward_ratio)

        return min(best_score, 1.0)

    # ------------------------------------------------------------------
    # Document ingestion (two-stage: global document profiles + section chunks)
    # ------------------------------------------------------------------

    def ingest_documents(self, docs_input) -> dict:
        """
        Ingests external documents and builds:
          1. Document-level profiles: {doc_name, title, headers, global_text, keywords}
          2. Section-level chunks: {chunk_id, text, source, page_or_slide, section_hierarchy, keywords}
        """
        image_exts = {".png", ".jpg", ".jpeg"}
        supported = {".pdf", ".docx", ".pptx", ".md", ".txt"} | image_exts

        if isinstance(docs_input, (str, Path)):
            p = Path(docs_input)
            paths = sorted(f for f in p.rglob("*") if f.suffix.lower() in supported) if p.is_dir() else [p]
        else:
            paths = [Path(p) for p in docs_input]

        docs_store: dict = {"documents": {}, "chunks_by_doc": {}, "all_chunks": []}

        for path in paths:
            ext = path.suffix.lower()
            logger.info("Ingesting %s", path.name)
            chunks: list[dict] = []
            try:
                if ext == ".pdf":
                    chunks = self._ingest_pdf(path, self.min_pdf_chunk_chars)
                elif ext == ".docx":
                    chunks = self._ingest_docx(path, self.min_pdf_chunk_chars)
                elif ext == ".pptx":
                    chunks = self._ingest_pptx(path, self.min_pptx_chunk_chars)
                elif ext in (".md", ".txt"):
                    chunks = self._ingest_text(path, self.min_text_block_chars)
                elif ext in image_exts:
                    chunks = self._ingest_image(path, self.min_image_ocr_chars)
                else:
                    logger.warning("Unsupported document type: %s", ext)
            except Exception as exc:
                logger.error("Failed to ingest %s: %s", path.name, exc)

            if not chunks:
                continue

            for chunk in chunks:
                chunk["keywords"] = self._extract_keywords(chunk["text"])

            doc_title = path.stem.replace("_", " ").replace("-", " ")
            headers = [c.get("section_hierarchy", "") for c in chunks if c.get("section_hierarchy")]
            combined_text = " ".join(c["text"] for c in chunks)
            doc_profile_text = (
                f"Document: {path.name} | Title: {doc_title}\n"
                f"Key Sections: {' | '.join(list(dict.fromkeys(headers))[:10])}\n{combined_text[:3000]}"
            )

            docs_store["documents"][path.name] = {
                "source": path.name,
                "title": doc_title,
                "profile_text": doc_profile_text,
                "headers": list(dict.fromkeys(headers)),
                "token_set": token_set(combined_text),
                "keywords": self._extract_keywords(combined_text[:5000]),
            }
            docs_store["chunks_by_doc"][path.name] = chunks
            docs_store["all_chunks"].extend(chunks)
            logger.info("%d chunk(s) indexed for %s", len(chunks), path.name)

        logger.info(
            "Ingest total: %d chunk(s) across %d document(s)",
            len(docs_store["all_chunks"]),
            len(docs_store["documents"]),
        )
        return docs_store

    @staticmethod
    def _ingest_pdf(path: Path, min_chars: int = 30) -> list[dict]:
        import fitz

        chunks = []
        with fitz.open(str(path)) as doc:
            for i, page in enumerate(doc):
                text = normalize_whitespace(page.get_text())
                if len(text) > min_chars:
                    chunks.append(
                        {"chunk_id": f"{path.stem}_page_{i + 1}", "text": text, "source": path.name, "page_or_slide": i + 1}
                    )
        return chunks

    @staticmethod
    def _ingest_docx(path: Path, min_chars: int = 30) -> list[dict]:
        # Shares min_pdf_chunk_chars's default (30) -- the original source
        # had no separate docx threshold. Note: only the mid-document flush
        # (triggered by a blank paragraph) enforces min_chars; the final
        # flush at end-of-document does not -- preserved as-is from source.
        import docx

        doc = docx.Document(str(path))
        chunks, buffer, buf_start = [], [], None
        for i, para in enumerate(doc.paragraphs):
            text = normalize_whitespace(para.text)
            if not text:
                if buffer:
                    combined = " ".join(buffer)
                    if len(combined) > min_chars:
                        chunks.append(
                            {"chunk_id": f"{path.stem}_para_{buf_start}", "text": combined, "source": path.name, "page_or_slide": buf_start}
                        )
                    buffer, buf_start = [], None
                continue
            if buf_start is None:
                buf_start = i
            buffer.append(text)
        if buffer:
            chunks.append(
                {"chunk_id": f"{path.stem}_para_{buf_start}", "text": " ".join(buffer), "source": path.name, "page_or_slide": buf_start}
            )
        return chunks

    @staticmethod
    def _ingest_pptx(path: Path, min_chars: int = 20) -> list[dict]:
        try:
            from pptx import Presentation
        except ImportError:
            logger.warning("python-pptx not installed, skipping %s", path.name)
            return []

        prs = Presentation(str(path))
        chunks = []
        for i, slide in enumerate(prs.slides):
            texts = []
            for shape in slide.shapes:
                if hasattr(shape, "text_frame"):
                    for para in shape.text_frame.paragraphs:
                        t = normalize_whitespace(para.text)
                        if t:
                            texts.append(t)
                elif hasattr(shape, "text") and shape.text.strip():
                    texts.append(normalize_whitespace(shape.text))
            combined = " ".join(texts)
            if len(combined) > min_chars:
                chunks.append({"chunk_id": f"{path.stem}_slide_{i + 1}", "text": combined, "source": path.name, "page_or_slide": i + 1})
        return chunks

    @staticmethod
    def _ingest_text(path: Path, min_chars: int = 25) -> list[dict]:
        """Hierarchical Markdown/text ingestion: tracks #/##/### header
        hierarchy and prepends structural breadcrumbs to every child block,
        so downstream embeddings carry document section context."""
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        chunks = []
        h1 = h2 = h3 = ""
        current_block: list[str] = []
        block_idx = 0

        def _flush(block: list[str]) -> None:
            nonlocal block_idx
            clean_b = normalize_whitespace(" ".join(block))
            if len(clean_b) > min_chars:
                headers = [h for h in (h1, h2, h3) if h]
                breadcrumb = " > ".join(headers) if headers else path.stem
                chunks.append(
                    {
                        "chunk_id": f"{path.stem}_block_{block_idx}",
                        "text": f"[{breadcrumb}]\n{clean_b}",
                        "source": path.name,
                        "section_hierarchy": breadcrumb,
                        "page_or_slide": block_idx + 1,
                    }
                )
                block_idx += 1

        for line in lines:
            line_str = line.strip()
            if line_str.startswith("# "):
                h1 = line_str.lstrip("# ").strip()
                h2 = h3 = ""
            elif line_str.startswith("## "):
                h2 = line_str.lstrip("# ").strip()
                h3 = ""
            elif line_str.startswith("### "):
                h3 = line_str.lstrip("# ").strip()

            if not line_str:
                if current_block:
                    _flush(current_block)
                    current_block = []
            else:
                current_block.append(line_str)

        if current_block:
            _flush(current_block)

        return chunks

    def _ingest_image(self, path: Path, min_chars: int = 20) -> list[dict]:
        """OCR an image external document (diagram, whiteboard, screenshot, exported slide)."""
        raw = self.ocr_engine.extract(str(path))
        text = clean_ocr_text(raw) if raw else ""
        if len(text) > min_chars:
            return [{"chunk_id": f"{path.stem}_ocr", "text": text, "source": path.name, "page_or_slide": 1}]
        logger.warning("No usable OCR text from %s", path.name)
        return []

    # ------------------------------------------------------------------
    # Two-stage reverse alignment (document-first -> section breakdown)
    # ------------------------------------------------------------------

    def align(self, context_path: str, docs_store) -> list[dict]:
        """
        Stage 1 (global document identification): score every topic against
        whole-document profiles (title, headers, global embedding,
        vocabulary), selecting the primary winning document(s).

        Stage 2 (local section/chunk breakdown): zoom into the winning
        document(s) to isolate active sections/slides/chunks, preventing
        small generic chunks in unrelated files from producing false positives.
        """
        logger.info("Loading %s", context_path)
        with open(context_path, encoding="utf-8") as f:
            topics = json.load(f)

        if isinstance(docs_store, list):
            doc_profiles: dict = {}
            chunks_by_doc: dict = {}
            for c in docs_store:
                chunks_by_doc.setdefault(c["source"], []).append(c)
            for src, chs in chunks_by_doc.items():
                txt = " ".join(c["text"] for c in chs)
                doc_profiles[src] = {
                    "source": src,
                    "profile_text": f"Document: {src}\n{txt[:3000]}",
                    "token_set": token_set(txt),
                    "keywords": self._extract_keywords(txt[:4000]),
                }
        else:
            doc_profiles = docs_store.get("documents", {})
            chunks_by_doc = docs_store.get("chunks_by_doc", {})

        if not doc_profiles:
            logger.warning("No documents loaded. Topics will have empty matches.")
            for t in topics:
                t["document_matches"] = []
            return topics

        doc_names = list(doc_profiles.keys())
        doc_profile_texts = [doc_profiles[d]["profile_text"] for d in doc_names]

        logger.info("Embedding %d global document profile(s)", len(doc_names))
        doc_profile_embs = self.embed_model.encode(
            doc_profile_texts, batch_size=self.embedding_batch_size, show_progress_bar=False,
            convert_to_numpy=True, normalize_embeddings=True,
        )

        topic_queries = [t.get("searchable_query") or "" for t in topics]
        logger.info("Embedding %d topic quer(ies)", len(topics))
        topic_embs = self.embed_model.encode(
            topic_queries, batch_size=self.embedding_batch_size, show_progress_bar=False,
            convert_to_numpy=True, normalize_embeddings=True,
        )

        global_doc_matrix = np.dot(topic_embs, doc_profile_embs.T)

        logger.info("Executing two-stage reverse alignment (document -> section)")
        for i, topic in enumerate(topics):
            topic_kw = [k.lower() for k in topic.get("keywords", [])]
            topic_ocr = [t for t in topic.get("visual_texts", []) if len(t.strip()) > 5]
            topic_hierarchy = topic.get("visual_hierarchy", {})

            # Stage 1: score & identify matching documents globally.
            candidate_docs = []
            for d_idx, doc_name in enumerate(doc_names):
                d_profile = doc_profiles[doc_name]
                s_doc_sem = float(global_doc_matrix[i, d_idx])
                s_doc_kw = self._keyword_jaccard(topic_kw, d_profile.get("keywords", []))
                s_doc_ocr = self._ocr_overlap_score(
                    topic_hierarchy, topic_ocr, d_profile.get("profile_text", ""),
                    self.title_containment_threshold, self.title_containment_boost,
                )
                doc_score = min(
                    s_doc_sem + (self.ocr_boost_weight * s_doc_ocr) + (self.keyword_boost_weight * s_doc_kw), 1.0
                )
                if doc_score >= self.threshold:
                    candidate_docs.append(
                        {"document": doc_name, "global_score": round(doc_score, 3), "semantic": round(s_doc_sem, 3), "ocr_score": round(s_doc_ocr, 3)}
                    )

            candidate_docs.sort(key=lambda x: x["global_score"], reverse=True)

            # Stage 2: local section/chunk breakdown for identified documents.
            topic_matched_docs = []
            detailed_matches = []

            primary_candidates = [c for c in candidate_docs if c["global_score"] >= self.stage1_promote_threshold]
            if not primary_candidates and candidate_docs:
                primary_candidates = [candidate_docs[0]]  # fallback to top candidate

            for cand in primary_candidates:
                doc_name = cand["document"]
                doc_chunks = chunks_by_doc.get(doc_name, [])
                if not doc_chunks:
                    continue

                chunk_texts = [c["text"] for c in doc_chunks]
                chunk_embs = self.embed_model.encode(
                    chunk_texts, batch_size=self.embedding_batch_size, show_progress_bar=False,
                    convert_to_numpy=True, normalize_embeddings=True,
                )
                chunk_sims = np.dot(chunk_embs, topic_embs[i])

                doc_sections = []
                best_chunk_score = cand["global_score"]

                for c_idx, chunk in enumerate(doc_chunks):
                    s_c_sem = float(chunk_sims[c_idx])
                    s_c_kw = self._keyword_jaccard(topic_kw, chunk.get("keywords", []))
                    s_c_ocr = self._ocr_overlap_score(
                        topic_hierarchy, topic_ocr, chunk["text"],
                        self.title_containment_threshold, self.title_containment_boost,
                    )
                    c_composite = min(s_c_sem + (self.ocr_boost_weight * s_c_ocr) + (self.keyword_boost_weight * s_c_kw), 1.0)

                    if c_composite >= self.threshold:
                        sec_name = chunk.get("section_hierarchy") or chunk.get("chunk_id")
                        if sec_name and sec_name not in doc_sections:
                            doc_sections.append(sec_name)
                        best_chunk_score = max(best_chunk_score, c_composite)

                        detailed_matches.append(
                            {
                                "source": doc_name,
                                "chunk_id": chunk["chunk_id"],
                                "section_hierarchy": chunk.get("section_hierarchy", ""),
                                "page_or_slide": chunk.get("page_or_slide"),
                                "score": round(c_composite, 3),
                                "score_breakdown": {
                                    "semantic": round(s_c_sem, 3),
                                    "ocr_boost": round(self.ocr_boost_weight * s_c_ocr, 3),
                                    "keyword_boost": round(self.keyword_boost_weight * s_c_kw, 3),
                                },
                                "chunk_text_preview": chunk["text"][:300],
                            }
                        )

                combined_score = round(
                    self.global_score_weight * cand["global_score"] + self.chunk_score_weight * best_chunk_score, 3
                )

                if combined_score >= self.high_confidence_threshold:
                    topic_matched_docs.append(
                        {
                            "document": doc_name,
                            "highest_confidence_score": round(best_chunk_score, 3),
                            "global_document_score": cand["global_score"],
                            "combined_score": combined_score,
                            "sections_matched": doc_sections,
                            "match_count": len(doc_sections),
                        }
                    )

            topic_matched_docs.sort(key=lambda x: (x["combined_score"], x["global_document_score"]), reverse=True)
            detailed_matches.sort(key=lambda x: x["score"], reverse=True)

            topic["detailed_chunk_matches"] = detailed_matches
            topic["document_matches"] = topic_matched_docs

            if topic_matched_docs:
                best_sources = ", ".join(f"{d['document']} ({d['highest_confidence_score']:.2f})" for d in topic_matched_docs)
                logger.info(
                    "[topic_%03d] %s-%s: %d confirmed doc(s) -> %s",
                    i, topic.get("start_time", "?"), topic.get("end_time", "?"), len(topic_matched_docs), best_sources,
                )

        matched = sum(1 for t in topics if t.get("document_matches"))
        logger.info("%d/%d topics aligned (high_confidence >= %s)", matched, len(topics), self.high_confidence_threshold)
        return topics

    # ------------------------------------------------------------------
    # Save + run
    # ------------------------------------------------------------------

    def save(self, topics: list[dict], output_path: str | None = None) -> str:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        intermediate_path = self.output_dir / "aligned_context_intermediate_detailed.json"
        with open(intermediate_path, "w", encoding="utf-8") as f:
            json.dump(topics, f, indent=2)
        logger.info("Detailed intermediate trace -> %s", intermediate_path)

        clean_aligned = []
        for t in topics:
            matched_docs = t.get("document_matches", [])
            primary_doc = matched_docs[0] if matched_docs else None
            clean_aligned.append(
                {
                    "topic_id": t.get("topic_id"),
                    "start_time": t.get("start_time"),
                    "end_time": t.get("end_time"),
                    "duration_sec": t.get("duration_sec"),
                    "speakers": t.get("speakers", []),
                    "transcript": t.get("transcript_aggregated", ""),
                    "primary_frame": t.get("primary_frame"),
                    "has_document_alignment": bool(primary_doc),
                    "primary_linked_document": primary_doc["document"] if primary_doc else None,
                    "highest_confidence_score": primary_doc["highest_confidence_score"] if primary_doc else 0.0,
                    "sections_matched": primary_doc["sections_matched"] if primary_doc else [],
                    "all_high_confidence_documents": matched_docs,
                }
            )

        out = Path(output_path) if output_path else self.output_dir / "aligned_context.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(clean_aligned, f, indent=2)
        logger.info("Clean aggregated aligned context -> %s", out)
        return str(out)

    def run(self, context_path: str, docs_input, output_path: str | None = None) -> str:
        """Full stage: ingest docs -> two-stage reverse align -> save -> return path."""
        docs_store = self.ingest_documents(docs_input)
        aligned = self.align(context_path, docs_store)
        return self.save(aligned, output_path)
