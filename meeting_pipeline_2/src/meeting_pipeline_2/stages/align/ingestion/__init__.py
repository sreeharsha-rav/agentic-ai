"""One module per reference-document format, each satisfying
`core.interfaces.DocumentIngester`.

Adding a new supported format means adding one new file here that
implements `base.DocumentIngester` and registering its extension(s) in
`service.py`'s dispatch table -- nothing else needs to change (see
../../../../../docs/architecture.md's extension-points table).
"""
