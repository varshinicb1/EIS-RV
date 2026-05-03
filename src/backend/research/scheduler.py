"""
Scheduler for Continuous Updates
===================================
Runs the pipeline periodically to fetch and process new papers.

Modes:
    - once:  Run pipeline once and exit
    - loop:  Run pipeline in a loop with configurable interval
"""

import time
import logging
import argparse
import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.backend.research.config import (
    UPDATE_INTERVAL_HOURS, LOG_FORMAT, LOG_LEVEL, LOG_DIR,
)
from src.backend.research.pipeline import ResearchPipeline

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Configure logging to console and file."""
    level = logging.DEBUG if verbose else getattr(logging, LOG_LEVEL)

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(LOG_FORMAT))

    # File handler
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, "pipeline.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    # Root logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)


def run_once(queries=None, max_per_query=10):
    """Run the pipeline once."""
    pipeline = ResearchPipeline()
    try:
        stats = pipeline.run(
            queries=queries,
            max_per_query=max_per_query,
        )
        db_stats = pipeline.get_database_stats()

        print("\n" + "=" * 60)
        print("PIPELINE RUN COMPLETE")
        print("=" * 60)
        print(stats)
        print("\nDatabase Statistics:")
        for k, v in db_stats.items():
            if isinstance(v, dict):
                print(f"  {k}:")
                for kk, vv in v.items():
                    print(f"    {kk}: {vv}")
            else:
                print(f"  {k}: {v}")
        print("=" * 60)

        return stats
    finally:
        pipeline.close()


def run_loop(interval_hours=None, max_per_query=10):
    """Run pipeline in a continuous loop."""
    interval = (interval_hours or UPDATE_INTERVAL_HOURS) * 3600

    logger.info(
        "Starting continuous pipeline (interval=%dh, max_per_query=%d)",
        interval / 3600, max_per_query,
    )

    iteration = 0
    while True:
        iteration += 1
        logger.info("--- Pipeline iteration %d ---", iteration)

        try:
            run_once(max_per_query=max_per_query)
        except KeyboardInterrupt:
            logger.info("Pipeline interrupted by user")
            break
        except Exception as e:
            logger.error("Pipeline iteration %d failed: %s", iteration, e)

        logger.info("Sleeping for %d hours until next run...", interval / 3600)
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Pipeline interrupted during sleep")
            break


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="VANL Research Paper Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run once with default settings
    python -m src.backend.research.scheduler --mode once

    # Run once with more papers
    python -m src.backend.research.scheduler --mode once --max-per-query 20

    # Run continuous loop (every 24h)
    python -m src.backend.research.scheduler --mode loop --interval 24

    # Quick test with 5 papers per query
    python -m src.backend.research.scheduler --mode once --max-per-query 5 -v
        """
    )

    parser.add_argument(
        "--mode", choices=["once", "loop"], default="once",
        help="Run mode: 'once' or 'loop' (default: once)",
    )
    parser.add_argument(
        "--max-per-query", type=int, default=10,
        help="Max papers per query per source (default: 10)",
    )
    parser.add_argument(
        "--interval", type=float, default=None,
        help="Hours between runs in loop mode (default: 24)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()
    setup_logging(verbose=args.verbose)

    if args.mode == "once":
        run_once(max_per_query=args.max_per_query)
    elif args.mode == "loop":
        run_loop(
            interval_hours=args.interval,
            max_per_query=args.max_per_query,
        )


if __name__ == "__main__":
    main()
