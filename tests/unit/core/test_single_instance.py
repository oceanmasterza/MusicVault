"""Tests for musicvault.core.single_instance."""

from __future__ import annotations

from musicvault.core.single_instance import is_main_process


def test_is_main_process_true_in_tests() -> None:
    assert is_main_process() is True
