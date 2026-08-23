"""Shared typing helper for OCR backend implementations.

Backends implement `core.interfaces.OCRBackend` structurally (via
`typing.Protocol`) -- this module exists as the one place to put anything
genuinely shared across backend implementations (e.g. a common raw-box
tuple type) as that need arises. Kept intentionally thin/empty for now to
avoid inventing shared structure before two real backends reveal what they
actually have in common.
"""

from __future__ import annotations

# TODO: if backend implementations converge on shared helpers (e.g. a
# common "load image, get width/height" step), factor it in here. Until
# then, each backend module in this package is self-contained.
