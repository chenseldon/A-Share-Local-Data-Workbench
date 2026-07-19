from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path


SDK_PATH_ENV = "ASHARE_FREE_STOCKDB_SDK_PATH"
DEFAULT_SDK_PATH = Path("D:/Edge/free-stockdb-main/pybao")
REQUIRED_MODULE_FILES = ("stock_sdk.py", "zhibiao.py")


@dataclass(frozen=True)
class FreeStockdbSdkStatus:
    configured_path: str | None
    path_exists: bool
    stock_sdk_available: bool
    zhibiao_available: bool
    error: str | None

    @property
    def ready(self) -> bool:
        return self.stock_sdk_available and self.zhibiao_available


def _candidate_paths() -> tuple[Path, ...]:
    configured = os.getenv(SDK_PATH_ENV)
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    candidates.append(DEFAULT_SDK_PATH)
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return tuple(unique)


def _valid_sdk_path(path: Path) -> bool:
    return path.is_dir() and all((path / filename).is_file() for filename in REQUIRED_MODULE_FILES)


def configure_free_stockdb_sdk_path() -> FreeStockdbSdkStatus:
    for candidate in _candidate_paths():
        if _valid_sdk_path(candidate):
            path_text = str(candidate)
            if path_text not in sys.path:
                sys.path.insert(0, path_text)
            return free_stockdb_sdk_status(configured_path=path_text)
    return free_stockdb_sdk_status(configured_path=str(_candidate_paths()[0]))


def free_stockdb_sdk_status(configured_path: str | None = None) -> FreeStockdbSdkStatus:
    configured = configured_path or os.getenv(SDK_PATH_ENV) or str(DEFAULT_SDK_PATH)
    path = Path(configured)
    stock_sdk_available = importlib.util.find_spec("stock_sdk") is not None
    zhibiao_available = importlib.util.find_spec("zhibiao") is not None
    path_exists = _valid_sdk_path(path)
    error = None
    if not stock_sdk_available or not zhibiao_available:
        error = f"Set {SDK_PATH_ENV} to the free-stockdb pybao directory containing stock_sdk.py and zhibiao.py."
    return FreeStockdbSdkStatus(
        configured_path=configured,
        path_exists=path_exists,
        stock_sdk_available=stock_sdk_available,
        zhibiao_available=zhibiao_available,
        error=error,
    )

