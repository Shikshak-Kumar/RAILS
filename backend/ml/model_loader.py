from __future__ import annotations

import json
import joblib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.config import MODEL_ROOT


@dataclass
class LoadedModel:
    model_name: str
    model_version: str
    pipeline: Any
    feature_order: list[str]
    metadata: dict[str, Any]


class ModelLoader:

    def __init__(self, model_root: Path | None = None) -> None:
        self.model_root = model_root or MODEL_ROOT
        self._cache: dict[str, LoadedModel] = {}

    def _resolve_version_dir(self, model_name: str) -> Path:
        model_dir = self.model_root / model_name
        if not model_dir.exists():
            raise FileNotFoundError(f'Model directory missing for {model_name!r}: {model_dir}')
        latest_file = model_dir / 'LATEST'
        if not latest_file.exists():
            raise FileNotFoundError(f'LATEST pointer missing for {model_name!r}')
        version = latest_file.read_text(encoding='utf-8').strip()
        if not version:
            raise ValueError(f'LATEST is empty for {model_name!r}')
        version_dir = model_dir / version
        if not version_dir.exists():
            raise FileNotFoundError(f'Version directory missing for {model_name!r} -> {version_dir}')
        return version_dir

    def load(self, model_name: str) -> LoadedModel:
        if model_name in self._cache:
            return self._cache[model_name]

        version_dir = self._resolve_version_dir(model_name)
        metadata_path = version_dir / 'metadata.json'
        feature_path = version_dir / 'feature_order.json'
        pipeline_path = version_dir / 'pipeline.joblib'

        for path in (metadata_path, feature_path, pipeline_path):
            if not path.exists():
                raise FileNotFoundError(f'Model artifact missing for {model_name!r}: {path}')

        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        feature_order = json.loads(feature_path.read_text(encoding='utf-8'))
        pipeline = joblib.load(pipeline_path)
        self._fix_pipeline_compatibility(pipeline)

        loaded = LoadedModel(
            model_name=model_name,
            model_version=metadata.get('model_version') or version_dir.name,
            pipeline=pipeline,
            feature_order=list(feature_order),
            metadata=metadata,
        )
        self._cache[model_name] = loaded
        return loaded

    @staticmethod
    def _fix_pipeline_compatibility(pipe_or_dict: Any) -> None:
        if isinstance(pipe_or_dict, dict):
            if 'model' in pipe_or_dict:
                ModelLoader._fix_pipeline_compatibility(pipe_or_dict['model'])
            if 'scorer' in pipe_or_dict and hasattr(pipe_or_dict['scorer'], 'iso'):
                ModelLoader._fix_pipeline_compatibility(pipe_or_dict['scorer'].iso)
            return
        if hasattr(pipe_or_dict, 'named_steps'):
            for _, step in pipe_or_dict.named_steps.items():
                if hasattr(step, '_fit_dtype') and not hasattr(step, '_fill_dtype'):
                    step._fill_dtype = step._fit_dtype

    def status(self, model_name: str) -> dict[str, Any]:
        try:
            loaded = self.load(model_name)
            return {
                'model_name': model_name,
                'available': True,
                'status': 'available',
                'model_version': loaded.model_version,
                'artifact_loaded': True,
                'metadata_loaded': bool(loaded.metadata),
                'feature_order_loaded': bool(loaded.feature_order),
            }
        except Exception as exc:
            return {
                'model_name': model_name,
                'available': False,
                'status': 'unavailable',
                'model_version': None,
                'artifact_loaded': False,
                'metadata_loaded': False,
                'feature_order_loaded': False,
                'error': str(exc),
            }


MODEL_LOADER = ModelLoader()


def load_model(model_name: str) -> LoadedModel:
    return MODEL_LOADER.load(model_name)


def load_all_models() -> dict[str, LoadedModel]:
    names = ['fraud_model', 'anomaly_model', 'account_risk_model', 'liquidity_model', 'credit_model']
    return {name: load_model(name) for name in names}
