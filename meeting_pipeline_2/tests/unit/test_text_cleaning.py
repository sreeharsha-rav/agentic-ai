"""Unit tests for `text/cleaning.py`.

Port reference: `../../../meeting_pipeline/tests/test_text_cleaning.py` --
cases for each noise-pattern category (file paths, taskbar clocks, meeting
chrome, browser boilerplate), `is_meaningful_text`'s length/letter-ratio/
word-count gate, and `extra_noise_patterns` being applied after the built-in
set.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="text/cleaning.py not yet implemented")
def test_strips_file_path_breadcrumbs():
    ...


@pytest.mark.skip(reason="text/cleaning.py not yet implemented")
def test_strips_taskbar_clock_and_battery():
    ...


@pytest.mark.skip(reason="text/cleaning.py not yet implemented")
def test_meaningless_text_cleans_to_empty_string():
    ...


@pytest.mark.skip(reason="text/cleaning.py not yet implemented")
def test_extra_noise_patterns_applied_after_builtin_set():
    ...
