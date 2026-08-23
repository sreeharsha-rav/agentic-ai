"""Unit tests for `config/schema.py` + `config/loader.py`.

Port reference: `../../../meeting_pipeline/tests/test_config.py` -- round-trip
(`to_dict`/`from_dict`/JSON), unknown-field-raises-ValueError, and
`.replace()`-produces-a-copy-without-mutating-original behaviors all
transfer directly once `loader.py`'s functions are implemented.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="config/loader.py not yet implemented")
def test_json_round_trip_preserves_all_fields():
    ...


@pytest.mark.skip(reason="config/loader.py not yet implemented")
def test_unknown_field_in_json_raises_value_error():
    ...


@pytest.mark.skip(reason="config/loader.py not yet implemented")
def test_merge_overrides_does_not_mutate_original():
    ...
