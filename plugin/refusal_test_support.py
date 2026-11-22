"""Test-only classification of wrapper namespace preflight refusals."""

import pytest


def skip_namespace_refusal(result):
    stderr = result.stderr
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", "replace")
    # A failed mapped-userns probe alone is insufficient: some hosts degrade
    # successfully. Classify only the actual wrapper's fail-closed result.
    if result.returncode == 2 and (
        "terminal-jail: namespace creation failed (unshare exit 1)" in stderr
        or "terminal-jail: auto-sandbox modify unavailable (unshare exit 1" in stderr
    ):
        pytest.skip("HOST-DENIED-USERNS: wrapper could not create its namespace")
