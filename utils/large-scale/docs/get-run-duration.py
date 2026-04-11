#!/usr/bin/env python3

import argparse
import datetime
import json
import logging
import pathlib


def get_run_duration(run_path: pathlib.Path) -> None:
    """
    Calculates the start and end times of a PEERING large-scale measurement run
    by scanning all phase and round directories for timestamps.json files.
    """
    if not run_path.is_dir():
        logging.error("%s is not a directory.", run_path)
        return

    earliest_start = float("inf")
    latest_end = float("-inf")
    found_data = False

    logging.debug("Scanning run directory: %s", run_path.absolute())
    # The data hierarchy is: Run -> Phase -> Round -> timestamps.json
    for phase_dir in run_path.iterdir():
        if phase_dir.is_dir() and phase_dir.name.startswith("phase"):
            logging.debug("Processing phase: %s", phase_dir.name)
            for round_dir in phase_dir.iterdir():
                if round_dir.is_dir() and round_dir.name.startswith("round"):
                    logging.debug("  Processing round: %s", round_dir.name)
                    ts_file = round_dir / "timestamps.json"
                    if not ts_file.exists():
                        logging.debug("    No timestamps.json in %s", round_dir.name)
                        continue
                    try:
                        with open(ts_file, encoding="utf8") as f:
                            timestamps = json.load(f)
                            start = timestamps.get("round-start")
                            end = timestamps.get("round-end")
                            if isinstance(start, (int, float)):
                                logging.debug("    Found start time: %s", start)
                                earliest_start = min(earliest_start, start)
                                found_data = True
                            if isinstance(end, (int, float)):
                                logging.debug("    Found end time: %s", end)
                                latest_end = max(latest_end, end)
                                found_data = True
                    except (OSError, json.JSONDecodeError):
                        logging.warning("    Error reading %s", ts_file)
                        continue

    if not found_data:
        logging.info("No timing information found in %s", run_path.absolute())
        return

    # Convert Unix timestamps to datetime objects
    start_dt = datetime.datetime.fromtimestamp(earliest_start)
    end_dt = datetime.datetime.fromtimestamp(latest_end)
    duration = end_dt - start_dt

    logging.info("Measurement Campaign: %s", run_path.absolute())
    logging.info("Start Date: %s", start_dt.strftime("%Y-%m-%d"))
    logging.info("Start Time: %s (Exact: %s)", start_dt.strftime("%H:%M:%S"), earliest_start)
    logging.info("End Date:   %s", end_dt.strftime("%Y-%m-%d"))
    logging.info("End Time:   %s (Exact: %s)", end_dt.strftime("%H:%M:%S"), latest_end)
    logging.info("Total Duration: %s", duration)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Calculate start/end times and dates for a PEERING measurement run."
    )
    parser.add_argument(
        "--run-path",
        metavar="DIR",
        type=pathlib.Path,
        dest="run_path",
        help="Path to the base directory of the measurement campaign (e.g., ~/data/peering-largescale25-experiments/run7)",
        required=True,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        dest="debug",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    get_run_duration(args.run_path)
    return 0


if __name__ == "__main__":
    main()
