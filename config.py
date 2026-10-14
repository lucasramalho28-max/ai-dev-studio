import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'
WORKSPACE = BASE / 'workspace'
DEFAULT_MODEL = 'qwen2.5-coder:3b'
PORT = int(os.environ.get('STUDIO_PORT', '5050'))
