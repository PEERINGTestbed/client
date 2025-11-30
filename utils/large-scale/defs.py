import pathlib

import peering

PROPAGATION_TIME = 600
ANNOUNCEMENT_DURATION = 5400

BIRD_CFG_DIR = pathlib.Path("../../", peering.DEFAULT_BIRD_CFG_DIR)
BIRD4_SOCK_PATH = pathlib.Path("../../", peering.DEFAULT_BIRD4_SOCK_PATH)
ANNOUNCEMENT_SCHEMA = pathlib.Path("../../", peering.DEFAULT_ANNOUNCEMENT_SCHEMA)

TARGETS_FILE = pathlib.Path("data/targets.txt")
CATCHMENTS_DIR = pathlib.Path("../measure-catchments")
MEASURE_CATCHMENTS_NUM_ROUNDS = 2
CATCHMENTS_PINGER_PPS = 5000

# used for iproute2 rule prio and verfploeter ICMP IDs
# must be less than 30000 to come BEFORE the default rules
PREFIX_ID_BASE = 14000

EGRESS_PREFS: list[peering.MuxName] = [
    peering.MuxName.ufmg01,
    peering.MuxName.uw01,
    peering.MuxName.clemson01,
]

PREFIXES: list[str] = [
    "184.164.224.0/24",
    "184.164.225.0/24",
    "184.164.226.0/24",
    "184.164.227.0/24",
    "184.164.232.0/24",
    "184.164.233.0/24",
    "184.164.238.0/24",
    "184.164.239.0/24",
    "184.164.246.0/24",
    "184.164.247.0/24",
    "184.164.248.0/24",
    "184.164.249.0/24",
    "184.164.250.0/24",
    "184.164.251.0/24",
]

VULTR_PROVIDERS_20251103 = [
    174,
    1299,
    2914,
    3257,
    3356,
    3491,
    4755,
    7922,
    9498,
]
VULTR_PROVIDERS = VULTR_PROVIDERS_20251103
