"""Command-line runner for the reproducible SalesLens ETL full refresh."""

import logging
import sys
import time

from .config import get_settings
from .extract import extract_processed_data
from .load import load_full_refresh
from .transform import build_dimensions


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    log = logging.getLogger("saleslens.etl").info
    started = time.perf_counter()
    try:
        log("ETL started")
        settings = get_settings()
        sources = extract_processed_data(settings.processed_dir, log)
        log("Extract completed")
        dimensions = build_dimensions(sources)
        log("Transform completed")
        results = load_full_refresh(settings.connection_kwargs, dimensions, sources, log)
        log("Validation completed: %s", results)
        log("ETL completed successfully in %.2f seconds", time.perf_counter() - started)
        return 0
    except Exception as error:
        logging.getLogger("saleslens.etl").exception("ETL failed: %s", error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
