"""Compatibility shim for the saved training artifacts.

The model artefacts in risk_out/ were created in the original training environment
and may pickle custom classes from a module named risk_sentinel. The backend uses
those artefacts verbatim, so we provide a lightweight compatibility layer that
allows unpickling without changing the trained model logic itself.
"""

from __future__ import annotations

from typing import Any


import numpy as np


def _slog1p(x: Any) -> Any:
    """Signed log1p transformation: sign(x) * log1p(|x|)."""
    x_arr = np.asarray(x, dtype=float)
    return np.sign(x_arr) * np.log1p(np.abs(x_arr))


class _CompatPlaceholder:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return _CompatPlaceholder(*args, **kwargs)

    def __setstate__(self, state: Any) -> None:
        if isinstance(state, dict):
            self.__dict__.update(state)
        elif isinstance(state, tuple):
            self.state = state

    def __getstate__(self) -> dict[str, Any]:
        return self.__dict__

    def __getattr__(self, name: str) -> Any:
        return None


class AccountScorer(_CompatPlaceholder):
    """Account risk scorer class unpickled from training artifacts."""
    pass


def __getattr__(name: str) -> Any:
    """Return a placeholder class for any custom symbol referenced by a saved artefact."""
    if name == '_slog1p':
        return _slog1p
    if name == 'AccountScorer':
        return AccountScorer
    return _CompatPlaceholder
