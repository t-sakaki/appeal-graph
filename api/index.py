import sys
from pathlib import Path

# src/ 以下のモジュール（app.py, agent.py, graph_context.py 等）を読み込めるようにする
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from app import app  # noqa: E402
