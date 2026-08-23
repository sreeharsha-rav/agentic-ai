"""Configuration layer: schema (what's configurable) separated from loading
(how a config is assembled from defaults / a JSON file / CLI overrides).

Port reference: `meeting_pipeline/config.py`, which mixes both concerns in
one file. Splitting them here means `schema.py` stays a pure, dependency-free
description of every tunable value (safe to import from anywhere, including
`core/`-adjacent test code), while `loader.py` owns the precedence rules and
any filesystem/argparse interaction.
"""
