#!/usr/bin/env python3

import argparse
import dataclasses
import enum
import ipaddress
import json
import logging
import pathlib
import re
import subprocess
import sys
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network

import dataclasses_json
import jinja2
import jsonschema
import requests

AUTO_BASE_DIR = pathlib.Path(__file__).absolute().parent

DEFAULT_BIRD_CFG_DIR = pathlib.Path(AUTO_BASE_DIR, "configs/bird/")
DEFAULT_BIRD4_SOCK_PATH = pathlib.Path(AUTO_BASE_DIR, "var/bird.ctl")
DEFAULT_BIRD6_SOCK_PATH = pathlib.Path(AUTO_BASE_DIR, "var/bird6.ctl")
_DEF_ANNOUNCEMENT_SCHEMA_REL = "configs/announcement_schema.json"
DEFAULT_ANNOUNCEMENT_SCHEMA = pathlib.Path(AUTO_BASE_DIR, _DEF_ANNOUNCEMENT_SCHEMA_REL)
DEFAULT_MUX2TAP_PATH = pathlib.Path(AUTO_BASE_DIR, "var/mux2dev.txt")


class MuxName(enum.StrEnum):
    amsterdam01 = "amsterdam01"
    clemson01 = "clemson01"
    grnet01 = "grnet01"
    isi01 = "isi01"
    neu01 = "neu01"
    saopaulo01 = "saopaulo01"
    seattle01 = "seattle01"
    ufmg01 = "ufmg01"
    utah01 = "utah01"
    uw01 = "uw01"
    wisc01 = "wisc01"
    vtramsterdam = "vtramsterdam"
    vtratlanta = "vtratlanta"
    vtrbangalore = "vtrbangalore"
    vtrchicago = "vtrchicago"
    vtrdallas = "vtrdallas"
    vtrdelhi = "vtrdelhi"
    vtrfrankfurt = "vtrfrankfurt"
    vtrhonolulu = "vtrhonolulu"
    vtrjohannesburg = "vtrjohannesburg"
    vtrlondon = "vtrlondon"
    vtrlosangelas = "vtrlosangelas"
    vtrmadrid = "vtrmadrid"
    vtrmanchester = "vtrmanchester"
    vtrmelbourne = "vtrmelbourne"
    vtrmexico = "vtrmexico"
    vtrmiami = "vtrmiami"
    vtrmumbai = "vtrmumbai"
    vtrnewjersey = "vtrnewjersey"
    vtrosaka = "vtrosaka"
    vtrparis = "vtrparis"
    vtrsantiago = "vtrsantiago"
    vtrsaopaulo = "vtrsaopaulo"
    vtrseattle = "vtrseattle"
    vtrseoul = "vtrseoul"
    vtrsilicon = "vtrsilicon"
    vtrsingapore = "vtrsingapore"
    vtrstockholm = "vtrstockholm"
    vtrsydney = "vtrsydney"
    vtrtelaviv = "vtrtelaviv"
    vtrtokyo = "vtrtokyo"
    vtrtoronto = "vtrtoronto"
    vtrwarsaw = "vtrwarsaw"


IXP_SPECIAL_PEERS_V4: dict[MuxName, dict[int, list[int]]] = {
    MuxName.amsterdam01: {
        6777: [27, 29],  # Route Servers
        12859: [60, 61],  # Bit
        8283: [52],  # Coloclue
    },
    MuxName.seattle01: {
        33108: [1, 2],  # Route Servers
        3130: [101, 592],  # RGNet
    },
}

IXP_SPECIAL_PEERS_V6: dict[MuxName, dict[int, list[int]]] = {
    MuxName.amsterdam01: {
        6777: [71, 72],  # Route Servers
        12859: [95, 96],  # Bit
        8283: [94],  # Coloclue
    },
    MuxName.seattle01: {
        33108: [5, 6],  # Route Servers
        3130: [112, 593],  # RGNet
    },
}

MUX_SETS: dict[str, list[MuxName]] = {
    "europe": [
        MuxName.vtramsterdam,
        MuxName.vtrfrankfurt,
        MuxName.vtrlondon,
        MuxName.vtrmadrid,
        MuxName.vtrmanchester,
        MuxName.vtrparis,
        MuxName.vtrstockholm,
        MuxName.vtrwarsaw,
    ],
    "na": [
        MuxName.vtratlanta,
        MuxName.vtrchicago,
        MuxName.vtrdallas,
        MuxName.vtrlosangelas,
        MuxName.vtrmiami,
        MuxName.vtrnewjersey,
        MuxName.vtrseattle,
        MuxName.vtrsilicon,
        MuxName.vtrtoronto,
    ],
    "sa": [
        MuxName.vtrsantiago,
        MuxName.vtrsaopaulo,
    ],
    "asia": [
        MuxName.vtrbangalore,
        MuxName.vtrdelhi,
        MuxName.vtrmelbourne,
        MuxName.vtrmumbai,
        MuxName.vtrosaka,
        MuxName.vtrseoul,
        MuxName.vtrsingapore,
        MuxName.vtrsydney,
        MuxName.vtrtokyo,
    ],
    "japan": [
        MuxName.vtrosaka,
        MuxName.vtrtokyo,
    ],
    "india": [
        MuxName.vtrbangalore,
        MuxName.vtrdelhi,
        MuxName.vtrmumbai,
    ],
}


@dataclasses_json.dataclass_json
@dataclasses.dataclass
class Announcement:
    muxes: list[MuxName]
    peer_ids: list[int] = dataclasses.field(default_factory=list)
    """Peer IDs to announce to (communities will be computed automatically)"""
    communities: list[tuple[int, int]] = dataclasses.field(default_factory=list)
    """List of communities to attach to announcement"""
    prepend: list[int] = dataclasses.field(default_factory=list)
    """List of ASNs to prepend to AS-path"""


@dataclasses_json.dataclass_json
@dataclasses.dataclass
class Update:
    withdraw: list[MuxName] = dataclasses.field(default_factory=list)
    announce: list[Announcement] = dataclasses.field(default_factory=list)
    description: str | None = None


@dataclasses_json.dataclass_json
@dataclasses.dataclass
class UpdateSet:
    prefix2update: dict[str, Update]


class Vultr:
    @staticmethod
    def communities_do_not_announce(upstreams: list[int]) -> list[tuple[int, int]]:
        return [(64600, asn) for asn in upstreams]

    @staticmethod
    def communities_prepend_thrice(upstreams: list[int]) -> list[tuple[int, int]]:
        return [(64603, asn) for asn in upstreams]

    @staticmethod
    def communities_announce_to_upstreams(
        upstreams: list[int],
    ) -> list[tuple[int, int]]:
        return [(20473, 6000)] + [(64699, asn) for asn in upstreams]


class PeeringCommunities:
    @staticmethod
    def do_not_announce(peer_id: int) -> tuple[int, int]:
        return (47065, 1000 + peer_id)

    @staticmethod
    def announce_to(peer_id: int) -> tuple[int, int]:
        return (47065, peer_id)


class AnnouncementController:
    def __init__(
        self,
        prefixes: list[IPv4Network | IPv6Network],
        bird_cfg_dir: pathlib.Path = DEFAULT_BIRD_CFG_DIR,
        bird4_sock: pathlib.Path = DEFAULT_BIRD4_SOCK_PATH,
        bird6_sock: pathlib.Path = DEFAULT_BIRD6_SOCK_PATH,
        schema_file: pathlib.Path = DEFAULT_ANNOUNCEMENT_SCHEMA,
        mux2tap_file: pathlib.Path = DEFAULT_MUX2TAP_PATH,
    ) -> None:
        assert bird_cfg_dir.exists(), str(bird_cfg_dir)
        self.bird_cfg_dir = pathlib.Path(bird_cfg_dir)
        assert bird4_sock.exists() or bird6_sock.exists()
        self.bird4_sock = bird4_sock
        self.bird6_sock = bird6_sock
        with open(schema_file, encoding="utf8") as fd:
            self.schema = json.load(fd)
        self.mux2id: dict[str, int] = {}
        with open(mux2tap_file, encoding="utf8") as fd:
            for line in fd:
                mux, tapdev = line.strip().split()
                assert tapdev.startswith("tap")
                self.mux2id[mux] = int(tapdev.removeprefix("tap"))
        self.config_template = self.__load_config_template()
        self.prefixes = prefixes
        self.__create_routes()

    def __load_config_template(self) -> jinja2.Template:
        path = self.bird_cfg_dir / "templates"
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(path), autoescape=True)
        return env.get_template("export_mux_pfx.jinja2")

    def __config_file(self, prefix: str, mux: MuxName) -> pathlib.Path:
        assert ipaddress.ip_network(prefix) is not None
        prefix = prefix.replace("/", "-")
        prefix = prefix.replace(":", "i")  # removing colon from v6 prefixes
        fn = f"export_{mux}_{prefix}.conf"
        return self.bird_cfg_dir / "prefix-filters" / fn

    def __create_routes(self) -> None:
        path = self.bird_cfg_dir / "route-announcements"
        path.mkdir(parents=True, exist_ok=True)
        for pfx in self.prefixes:
            fpath = path / pfx.replace("/", "-")
            fd = open(fpath, "w", encoding="utf8")
            fd.write(f"route {pfx} unreachable;\n")
            fd.close()

    def validate(self, updates: UpdateSet) -> None:
        d = {pfx: upd.to_dict() for pfx, upd in updates.prefix2update.items()}
        jsonschema.validate(d, self.schema)

    def deploy(self, updates: UpdateSet) -> None:
        self.validate(updates)
        for prefix, update in updates.prefix2update.items():
            for mux in update.withdraw:
                self.withdraw(prefix, mux)
            for announcement in update.announce:
                self.announce(prefix, announcement)
        self.reload_config()

    def withdraw(self, prefix: str, mux: MuxName | None = None) -> None:
        if mux is None or mux == "all":
            for emux in MuxName:
                self.withdraw(prefix, emux)
            return
        try:
            self.__config_file(prefix, mux).unlink()
        except FileNotFoundError:
            pass

    def announce(self, prefix: str, ann: Announcement) -> None:
        for mux in ann.muxes:
            with open(self.__config_file(prefix, mux), "w", encoding="utf8") as fd:
                data = self.config_template.render(prefix=prefix, spec=ann.to_dict())
                fd.write(data)

    def reload_config(self) -> None:
        for execname, sockpath in [
            ("birdc", self.bird4_sock),
            ("birdc6", self.bird6_sock),
        ]:
            if not sockpath.exists() or not sockpath.is_socket():
                logging.info("%s is not a unix socket, skipping", sockpath)
                continue

            cmd = f"{execname} -s {sockpath}"
            proc = subprocess.Popen(  # noqa: S603
                cmd.split(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = proc.communicate(b"configure\n")
            r = proc.wait()
            if r != 0:
                logging.warning("%s reconfigure exited with status %d", execname, r)
                logging.warning("%s", stdout)
                logging.warning("%s", stderr)
                raise RuntimeError("Reconfiguring BIRD failed")

    def set_egress(
        self,
        prio: int,
        srcip: str | IPv4Address | IPv6Address,
        mux: str,
        peerid: int | None,
    ) -> None:
        assert ipaddress.ip_address(srcip)
        muxid = self.mux2id[mux]
        if peerid is None:
            gateway = f"100.{64 + muxid}.128.1"
        else:
            gateway = f"100.{64 + muxid}.{peerid // 256}.{peerid % 256}"

        cmd = f"ip rule add from {srcip} lookup {prio} prio {prio}"
        _run_check_log(cmd, True)

        cmd = f"ip route flush table {prio}"
        _run_check_log(cmd, False)

        cmd = f"ip route add default via {gateway} table {prio}"
        _run_check_log(cmd, True)

    def unset_egress(self, prio: int) -> None:
        cmd = f"ip route flush table {prio}"
        _run_check_log(cmd, False)
        try:
            cmd = f"ip rule del prio {prio}"
            while True:
                # Remove rules until none are left and CalledProcessError is raised
                _run_check_log(cmd, True, False)
        except subprocess.CalledProcessError:
            pass


PROTOCOL_REGEX = re.compile(r"up(?P<peerid>\d+)_(?P<asn>\d+)")


def protocol_to_peerid_asn(proto: str) -> tuple[int, int]:
    m = PROTOCOL_REGEX.match(proto)
    if not m:
        raise ValueError(f"Invalid protocol name {proto}")
    peerid = int(m.group("peerid"))
    asn = int(m.group("asn"))
    return (peerid, asn)


def _run_check_log(cmd: str, check: bool, log_errors: bool = True) -> None:
    try:
        logging.info("running %s", cmd)
        subprocess.run(cmd.split(), capture_output=True, check=check)  # noqa: S603
    except subprocess.CalledProcessError as cpe:
        if log_errors:
            logging.error("stdout: %s", cpe.stdout)
            logging.error("stderr: %s", cpe.stderr)
        raise


class ExperimentController:
    def __init__(
        self,
        url: str,
        token: str,
        refresh: str | None = None,
        schema_fn: str = "configs/experiment_schema.json",
    ):
        self.url = url
        self.token = token  # access-token
        self.refresh = refresh  # refresh-token
        self.set_schema(schema_fn)

    def set_schema(self, schema_fn):
        with open(schema_fn, encoding="utf8") as fd:
            self.schema = json.load(fd)

    def validate(self, experiment):
        jsonschema.validate(experiment["experiment"], self.schema)

    def post_request(self, data, uri):
        resp = requests.post(
            uri,
            json=data,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=5.0,
        )
        # If the response is successful, no Exception will be raised
        resp.raise_for_status()
        return resp.json()

    def get_request(self, uri, detailed=""):
        resp = requests.get(
            f"{uri}{detailed}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=5.0,
        )

        resp.raise_for_status()
        return resp.json()

    def deploy(self, experiment):
        self.validate(experiment)
        try:
            uri = f"{self.url}/api/"
            return self.post_request(experiment, uri)
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
            return http_err

    def retrieve(self, detailed=""):
        try:
            uri = f"{self.url}/api/"
            response = self.get_request(uri, detailed)
            return response
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
            return http_err

    # "A refresh token is a special token that is used to obtain additional access
    # tokens. This allows you to have short-lived access tokens without having to
    # collect credentials every time one expires."
    # https://developer.okta.com/docs/guides/refresh-tokens/main/

    def refresh_token(self):
        uri = f"{self.url}/token/refresh/"
        data = {"refresh": self.refresh}
        response = self.post_request(data, uri)
        self.token = response["access"]
        return response


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--announcement",
        metavar="announcement_json",
        type=str,
        dest="announcement",
        help="Deploy announcement via CLI",
    )
    group.add_argument(
        "--experiment",
        metavar="experiment_json",
        type=str,
        dest="experiment",
        help="Deploy experiment via HTTP request",
    )
    parser.add_argument(
        "--url",
        type=str,
        dest="url",
        help="PEERING site URL",
    )
    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    if args.announcement:
        with open(args.announcement, encoding="utf8") as announcement_json_fd:
            announcement = json.load(announcement_json_fd)
        bird_cfg_dir = pathlib.Path("configs/bird")
        bird_sock = pathlib.Path("var/bird.ctl")
        schema_fn = pathlib.Path("configs/announcement_schema.json")

        ctrl = AnnouncementController(bird_cfg_dir, bird_sock, schema_fn)
        ctrl.deploy(announcement)
    elif args.experiment and args.url:
        token_fn = "certs/token.json"
        schema_fn = "configs/experiment_schema.json"
        with open(args.experiment, encoding="utf8") as experiment_json_fd:
            experiment = json.load(experiment_json_fd)
        with open(token_fn, encoding="utf8") as token_json_fd:
            token = json.load(token_json_fd)

        ctrl = ExperimentController(
            url=args.url,
            token=token["access"],
            schema_fn=schema_fn,
        )
        response = ctrl.deploy(experiment)
        print(response)
    elif args.experiment and not args.url:
        parser.error("Note: --url is required when --experiment is set")

    return 0


if __name__ == "__main__":
    sys.exit(main())
