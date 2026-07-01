from __future__ import annotations

import sys
from pathlib import Path


AGENT_SRC = Path(__file__).resolve().parent / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from stt_whisper import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
