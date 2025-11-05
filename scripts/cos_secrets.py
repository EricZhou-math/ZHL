"""
Local COS secrets loader.

Reads `.secrets/cos.env` and returns a dict of values, then optionally
exports them to `os.environ` so existing scripts can keep using
environment variables.

Keys supported:
  - COS_SECRET_ID (required)
  - COS_SECRET_KEY (required)
  - COS_REGION (required)
  - COS_BUCKET (required)
  - COS_PREFIX (optional)
"""
import os
from pathlib import Path
from typing import Dict

BASE = Path(__file__).resolve().parent.parent
SECRETS_DIR = BASE / '.secrets'
ENV_FILE = SECRETS_DIR / 'cos.env'


def _parse_env_line(line: str):
    line = line.strip()
    if not line or line.startswith('#'):
        return None, None
    if '=' not in line:
        return None, None
    key, val = line.split('=', 1)
    key = key.strip()
    val = val.strip().strip('"').strip("'")
    return key, val


def load_cos_env() -> Dict[str, str]:
    cfg: Dict[str, str] = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            for raw in f:
                k, v = _parse_env_line(raw)
                if k:
                    cfg[k] = v
    return cfg


def export_to_environ(cfg: Dict[str, str], overwrite: bool = False) -> None:
    for k, v in cfg.items():
        if overwrite or (os.environ.get(k) is None):
            if v is not None:
                os.environ[k] = v