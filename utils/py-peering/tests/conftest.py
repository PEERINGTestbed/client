from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Iterable
from typing import cast

import pytest
from pyroute2 import IPRoute  # type: ignore


# Pytest imports this module before startup hooks run. Then pytest_cmdline_main
# executes very early: the first process re-execs itself inside `unshare`, while
# the child process sees PEERING_TEST_NETNS_ACTIVE and continues normally.
# pytest_sessionstart then brings `lo` up inside that isolated network namespace
# before collection and test execution proceed.


NETNS_ENVVAR = "PEERING_TEST_NETNS_ACTIVE"


def pytest_cmdline_main(config: pytest.Config) -> int | None:
    if os.environ.get(NETNS_ENVVAR):
        return None

    if sys.platform != "linux":
        raise pytest.UsageError(
            "tests require Linux because they run in an isolated network namespace"
        )

    unshare = shutil.which("unshare")
    if unshare is None:
        raise pytest.UsageError("tests require the `unshare` command")

    env = os.environ.copy()
    env[NETNS_ENVVAR] = "1"
    command = [
        unshare,
        "--user",
        "--map-root-user",
        "--net",
        sys.executable,
        "-m",
        "pytest",
        *sys.argv[1:],
    ]
    return subprocess.run(command, env=env, check=False).returncode


def pytest_sessionstart(session: pytest.Session) -> None:
    if not os.environ.get(NETNS_ENVVAR):
        return

    with IPRoute() as ipr:
        idxs = tuple(cast(Iterable[int], ipr.link_lookup(ifname="lo")))  # pyright: ignore[reportUnknownMemberType]
        if not idxs:
            raise RuntimeError("Loopback interface not found in test network namespace")
        ipr.link("set", index=idxs[0], state="up")  # pyright: ignore[reportUnknownMemberType]
