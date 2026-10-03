
from __future__ import annotations

from typing import Any


import numpy as np


def _slog1p(x: Any) -> Any:
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
    pass


def __getattr__(name: str) -> Any:
    if name == '_slog1p':
        return _slog1p
    if name == 'AccountScorer':
        return AccountScorer
    return _CompatPlaceholder
