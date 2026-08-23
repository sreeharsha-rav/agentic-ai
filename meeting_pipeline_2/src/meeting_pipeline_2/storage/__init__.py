"""Storage layer: artifact path resolution + JSON read/write.

This is the only part of the codebase that should know the on-disk file
layout (which filenames live under `output_dir`, in what subdirectory).
Stages receive an `ArtifactPaths` instance (see `core/models.py`) rather than
constructing paths themselves -- that's what lets the on-disk layout change
in one place without touching stage logic.
"""
