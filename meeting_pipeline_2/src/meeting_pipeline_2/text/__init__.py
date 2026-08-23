"""Shared text utilities: WebVTT parsing, OCR noise cleaning, timestamp
formatting.

Used by `stages/frames/` (VTT -> speech chunks), `stages/context/` (OCR
cleaning, timestamp display), and `stages/align/` (text normalization).
Pure text-in/text-out functions -- no video/model dependencies.
"""
