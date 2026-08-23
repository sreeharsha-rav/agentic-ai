"""Shared ML-adjacent utilities: embedding provider + keyword extraction.

Used by `stages/context/` (optional, topic-boundary semantic drift) and
`stages/align/` (required, semantic/keyword scoring signals). Both stages
depend on the `core.interfaces.EmbeddingProvider`/`KeywordExtractor`
protocols, not on these concrete classes directly, so the model/library
backing either can be swapped via `config/` without touching stage logic
(see docs/architecture.md's extension-points table).
"""
