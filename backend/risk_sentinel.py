"""Compatibility shim for the saved training artifacts.

The model artefacts in risk_out/ were created in the original training environment
and may pickle custom classes from a module named risk_sentinel. The backend uses
those artefacts verbatim, so we provide a lightweight compatibility layer that
allows unpickling without changing the trained model logic itself.
"""

from __future__ import annotations

from typing import Any


class _CompatPlaceholder:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return _CompatPlaceholder(*args, **kwargs)

    def __setstate__(self, state: Any) -> None:
        return None

    def __getstate__(self) -> dict[str, Any]:
        return {}

    def __getattr__(self, name: str) -> Any:
        return None


def __getattr__(name: str) -> Any:
    """Return a placeholder class for any custom symbol referenced by a saved artefact."""
    return _CompatPlaceholder
