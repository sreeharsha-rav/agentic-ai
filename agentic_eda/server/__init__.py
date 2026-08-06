"""FastAPI server exposing the Agentic EDA pipeline as a streaming web API.

The agents themselves stay untouched apart from an optional `on_event` progress
hook; this package adds upload, manual triggering, SSE event streaming, and
artifact serving on top of them.
"""
