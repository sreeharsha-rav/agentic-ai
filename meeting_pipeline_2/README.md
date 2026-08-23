# meeting-pipeline-2 (scaffold)

This is a **from-scratch structural scaffold** for the same problem
`meeting_pipeline` solves -- transcribe a meeting recording, extract the
slide/screen frames visible while each thing was said, build topic-level
multimodal context, and align meeting topics against reference documents --
restructured around clear architectural layers instead of one flat module
per stage.

**Nothing in `src/` is implemented yet.** Every file is a skeleton: a module
docstring stating its single responsibility, typed function/class
signatures, and `raise NotImplementedError` bodies with comments describing
what goes there and (where relevant) which file in the original
`../meeting_pipeline` package to port the logic from. The goal of this
scaffold is the *shape* of the system -- see `docs/architecture.md` for the
reasoning behind it -- not a working pipeline yet.

## Why restructure at all?

`meeting_pipeline` works, and its tuned algorithmic values (SSIM/MSE
thresholds, scoring weights, font-size percentiles) should be ported
verbatim -- this isn't a rewrite of *what* the pipeline does. It's a
reorganization of *where* things live, aimed at four properties:

- **Maintainable**: a change to "how we call the embedding model" or "how
  OCR backends are selected" should touch one module, not be duplicated
  across every stage that happens to need embeddings or OCR.
- **Testable**: business logic (scoring formulas, clustering rules, dedup
  algorithms) is separated from I/O (ffmpeg subprocesses, model loading,
  file reads) so it can be unit-tested with plain Python objects, no video
  files or model downloads required.
- **Extensible**: adding a 5th OCR backend, a new reference-document format,
  or swapping the embedding provider should mean *adding a file that
  implements an existing interface*, not editing a big if/elif chain
  embedded in stage logic.
- **Deployable**: a clear boundary between "domain logic" and "runtime
  wiring" makes it possible to run this as a CLI, a batch job, or a service
  without the domain code knowing or caring which.

## Directory structure

```
src/meeting_pipeline_2/
├── core/            # Pure domain layer: data models + interfaces (ports).
│                     No I/O, no third-party imports. Everything else depends
│                     on this; this depends on nothing in the package.
├── config/          # Config schema (dataclasses) + loading/merging
│                     (defaults < JSON file < CLI overrides).
├── media/            # Shared low-level media utilities: ffmpeg subprocess
│                     wrapper, video frame reading, image similarity metrics
│                     (SSIM/MSE/content-score). Used by transcribe + frames.
├── text/             # Shared text utilities: VTT parsing, OCR noise
│                     cleaning, timestamp formatting. Used by frames + context.
├── nlp/              # Shared ML-adjacent utilities: embedding provider
│                     (sentence-transformers) and keyword extraction (YAKE).
│                     Used by context + align.
├── storage/          # Artifact path resolution + JSON read/write. The only
│                     place that knows the on-disk file layout.
├── stages/           # One subpackage per pipeline stage. Each stage depends
│                     on core interfaces + the shared infra packages above --
│                     never directly on another stage.
│   ├── transcribe/
│   ├── frames/
│   ├── context/       (context/ocr/ + context/ocr/backends/ for the
│                       auto-fallback OCR chain, one file per backend)
│   └── align/          (align/ingestion/ for one file per document format)
├── pipeline/         # Orchestration: runs stages in order via the `core`
│                     interfaces only, resolves resume/stage-subset logic,
│                     writes the run manifest. Never imports a stage's
│                     concrete class -- only its interface.
├── cli.py            # Thin argparse adapter over pipeline/ + config/.
├── logging_utils.py
└── errors.py
```

See `docs/architecture.md` for the dependency-direction diagram and the
reasoning behind the layer boundaries, plus a module-by-module map back to
the equivalent logic in `../meeting_pipeline`.

## Implementing a stage

Each stage's `service.py` will implement the corresponding `core.interfaces`
protocol (e.g. `Transcriber`, `FrameExtractor`) and depend on the shared
`media`/`text`/`nlp` utilities plus its own private helper modules -- it
should never need to know about another stage's internals. `pipeline/orchestrator.py`
only ever calls stages through their `core` interface, so a stage's internal
files can be freely reorganized without touching orchestration.

## Testing philosophy

`tests/unit/` mirrors `src/` 1:1 -- pure functions (metrics, scoring,
cleaning, parsing) get direct unit tests with no model downloads or real
media files. `tests/integration/` exercises multiple stages chained together
against small fixtures, gated the same way `meeting_pipeline` gates its slow
tests (env vars, `@pytest.mark.slow`/`@pytest.mark.integration`).

## Status

Scaffold only -- see the `TODO` comments in each module. Suggested build
order: `core/` -> `config/` -> `media`/`text`/`nlp` -> one stage end to end
(start with `transcribe`, the simplest) -> `pipeline/orchestrator.py` -> `cli.py`.
