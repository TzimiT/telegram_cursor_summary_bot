import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _resolve_data_dir():
    raw = os.getenv("DATA_DIR")
    if not raw:
        return ROOT_DIR
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


DATA_DIR = _resolve_data_dir()


def resolve_data_path(path):
    path = Path(path)
    if path.is_absolute():
        return path
    return DATA_DIR / path
