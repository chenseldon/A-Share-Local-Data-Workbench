from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from app.free_stockdb_sdk import configure_free_stockdb_sdk_path


def load_real_sdk_module(module_name: str) -> ModuleType:
    status = configure_free_stockdb_sdk_path()
    if not status.configured_path:
        raise ImportError(status.error or f"free-stockdb SDK path is not configured for {module_name}.")
    module_path = Path(status.configured_path) / f"{module_name}.py"
    if not module_path.is_file():
        raise ImportError(status.error or f"free-stockdb SDK module is missing: {module_path}")
    spec = importlib.util.spec_from_file_location(f"_free_stockdb_real_{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load free-stockdb SDK module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

