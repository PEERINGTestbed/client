from ipaddress import IPv4Network, IPv6Network
import pathlib

BASEDIR = pathlib.Path(__file__).resolve().parents[3]
PREFIXES: list[IPv4Network | IPv6Network] = [
    IPv4Network("184.164.226.0/24"),
    IPv4Network("184.164.227.0/24"),
    IPv4Network("184.164.247.0/24"),
    IPv4Network("184.164.254.0/24"),
]

TARGETS_FILE = pathlib.Path("data/targets.txt")
ANNOUNCEMENT_DURATION = 5400
PROPAGATION_TIME = 600
PER_PFX_PPS = 1000

