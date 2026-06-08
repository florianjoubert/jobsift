"""Entry point for the daily run (invoked by launchd)."""

import logging
import sys
from pathlib import Path

# Resolve the log path from the project root, regardless of the working directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOG_PATH = _PROJECT_ROOT / "data" / "bot.log"
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_LOG_PATH),
    ],
)


def main():
    from app.api.runner import execute_run

    summary = execute_run()
    logging.getLogger(__name__).info(f"Run terminé : {summary.model_dump()}")


if __name__ == "__main__":
    main()
