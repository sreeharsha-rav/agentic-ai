"""One module per OCR backend, each satisfying `core.interfaces.OCRBackend`.

Adding a 5th backend means adding one new file here that implements
`base.OCRBackendProtocol` and registering it in `engine.py`'s priority list
-- nothing else in the codebase needs to change (see
../../../../../docs/architecture.md's extension-points table).
"""
