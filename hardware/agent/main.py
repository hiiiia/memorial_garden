"""`python3 -m hardware.agent.main` 실행을 위한 패키지 진입점."""

import asyncio

from .src.main import main


if __name__ == "__main__":
    asyncio.run(main())
