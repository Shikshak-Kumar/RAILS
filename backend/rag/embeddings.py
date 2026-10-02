from __future__ import annotations

import hashlib


def hash_embedding(text: str, dim: int = 8) -> list[float]:
    vector: list[float] = []
    for index in range(dim):
        digest = hashlib.sha256(f'{text}:{index}'.encode('utf-8')).hexdigest()
        vector.append(int(digest[:8], 16) / float(0xFFFFFFFF))
    return vector


__all__ = ['hash_embedding']
