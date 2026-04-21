#!/usr/bin/env python3
import argparse
import logging
import re
import subprocess
import sys
import time
from pathlib import Path

# Resolve the project root to import peering
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(PROJECT_ROOT))
from peering import build_mux2id

# Configure logging to output to stderr
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_measurements(src_addr: str, mux: str, targets_fn: Path) -> None:
    """Executes long-lived and short-lived scamper instances for latency measurement."""
    # Resolve the OpenVPN configs directory relative to this script
    script_dir = Path(__file__).parent.resolve()
    openvpn_cfgs = script_dir.parent.parent / "configs" / "openvpn"

    mux2id = build_mux2id(openvpn_cfgs)

    if not mux2id:
        logger.error(f"No OpenVPN configurations found in {openvpn_cfgs}")
        sys.exit(1)

    if mux not in mux2id:
        logger.error(f"Mux '{mux}' not found in OpenVPN configurations.")
        sys.exit(1)

    muxid = mux2id[mux]
    gateway = f"100.{64 + muxid}.128.1"

    # Extract the third octet for the filename
    try:
        octet = src_addr.split(".")[2]
    except IndexError:
        logger.error(f"Invalid source address format '{src_addr}'.")
        sys.exit(1)

    pkts_per_sec = 200
    probe_method = "ICMP-echo"
    max_probes = 6
    max_replies = 3

    # Start the long-lived scamper instance
    long_lived_output = f"{octet}-{mux}-output.warts.xz"
    long_lived_cmd = [
        "scamper",
        "-o",
        long_lived_output,
        "-O",
        "warts.xz",
        "-p",
        str(pkts_per_sec),
        "-f",
        str(targets_fn),
        "-c",
        f"ping -S {src_addr} -P {probe_method} -o {max_replies} -c {max_probes}",
    ]

    long_proc = None
    try:
        long_proc = subprocess.Popen(long_lived_cmd)  # noqa: S603
        logger.info(f"Started long-lived scamper instance (PID: {long_proc.pid})")

        consecutive_failures = 0
        # Run short-lived instances every second while the long-lived one is active
        while long_proc.poll() is None:
            start_time = time.time()
            timestamp = f"{start_time:.9f}"
            short_lived_output = f"{octet}-{mux}-{timestamp}.warts.xz"

            short_lived_cmd = [
                "scamper",
                "-o",
                short_lived_output,
                "-O",
                "warts.xz",
                "-p",
                str(pkts_per_sec),
                "-i",
                gateway,
                "-c",
                f"ping -S {src_addr} -c 4 -i 0.1 -w 0.5",
            ]

            # Execute and wait for short-lived instance
            try:
                subprocess.check_call(short_lived_cmd)  # noqa: S603
                consecutive_failures = 0
            except subprocess.CalledProcessError:
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    logger.error("Too many consecutive failures, aborting.")
                    long_proc.terminate()
                    break

            # Ensure we start the next instance 1 second after the current one started
            elapsed = time.time() - start_time
            sleep_time = 1.0 - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        long_proc.wait()
        logger.info("Long-lived scamper instance has finished.")

    except FileNotFoundError:
        logger.error("'scamper' command not found.")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nMeasurement interrupted by user. Cleaning up...")
        if long_proc is not None:
            long_proc.terminate()
            long_proc.wait()


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure latency using scamper")

    parser.add_argument(
        "-s",
        dest="src_addr",
        type=str,
        help="Source IP address",
        required=True,
        metavar="<addr>",
        default=None,
    )
    parser.add_argument(
        "-m",
        dest="mux",
        type=str,
        help="Mux identifier",
        required=True,
        metavar="<mux>",
        default=None,
    )
    parser.add_argument(
        "-t",
        dest="targets_fn",
        type=Path,
        help="File containing targets to probe",
        required=True,
        metavar="<targets>",
        default=None,
    )

    args = parser.parse_args()

    run_measurements(src_addr=args.src_addr, mux=args.mux, targets_fn=args.targets_fn)


if __name__ == "__main__":
    main()
