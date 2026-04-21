#!/usr/bin/env python3

import argparse
import enum
import json
import logging
import pathlib
import re
import socket
import subprocess
import sys
from functools import cached_property
from ipaddress import IPv4Network, IPv6Network
from typing import Annotated, Self, assert_never

import requests
from pydantic import BaseModel, Field
from pyroute2 import IPRoute

AUTO_BASE_DIR = pathlib.Path(__file__).absolute().parent


class Mux(enum.StrEnum):
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


def get_ip_rule_prio_offset(pfx: IPv4Network | IPv6Network) -> int:
    """Computes the IP rule priority offset based on the prefix.

    For IPv4, it is the value of the 3rd octet of the network address.
    For IPv6, it is the value of the 6th octet (bits 40-47 of the prefix).
    """
    if isinstance(pfx, IPv4Network):
        return int(pfx.network_address.packed[2])
    if isinstance(pfx, IPv6Network):
        return int(pfx.network_address.packed[5])
    assert_never(pfx)


def build_mux2id(cfgs_dir: pathlib.Path) -> dict[Mux, int]:
    """Builds the mux to ID mapping by reading OpenVPN configuration files.

    Raises:
        RuntimeError: When OpenVPN configurations are not found."""

    if not cfgs_dir.exists():
        raise RuntimeError("OpenVPN configurations not found")

    mux2id: dict[Mux, int] = {}
    dev_re = re.compile(r"^dev\s+tap(\d+)", re.MULTILINE)

    for fn in cfgs_dir.glob("*.conf"):
        try:
            mux = Mux(fn.stem)
        except ValueError:
            logging.warning("OpenVPN config %s does not match a known MuxName", fn)
            continue
        content = fn.read_text()
        match = dev_re.search(content)
        if match:
            mux2id[mux] = int(match.group(1))

    return mux2id


IXP_SPECIAL_PEERS_V4: dict[Mux, dict[int, list[int]]] = {
    Mux.amsterdam01: {
        # PeerASN: list[sessionIDs]
        6777: [27, 29],  # Route Servers
        12859: [60, 61],  # Bit
        8283: [52],  # Coloclue
    },
    Mux.seattle01: {
        33108: [1, 2],  # Route Servers
        3130: [592],  # RGNet
    },
}

IXP_SPECIAL_PEERS_V6: dict[Mux, dict[int, list[int]]] = {
    Mux.amsterdam01: {
        # PeerASN: list[sessionIDs]
        6777: [71, 72],  # Route Servers
        12859: [95, 96],  # Bit
        8283: [94],  # Coloclue
    },
    Mux.seattle01: {
        33108: [5, 6],  # Route Servers
        3130: [593],  # RGNet
    },
}

MUX_SETS: dict[str, list[Mux]] = {
    "europe": [
        Mux.vtramsterdam,
        Mux.vtrfrankfurt,
        Mux.vtrlondon,
        Mux.vtrmadrid,
        Mux.vtrmanchester,
        Mux.vtrparis,
        Mux.vtrstockholm,
        Mux.vtrwarsaw,
    ],
    "na": [
        Mux.vtratlanta,
        Mux.vtrchicago,
        Mux.vtrdallas,
        Mux.vtrlosangelas,
        Mux.vtrmiami,
        Mux.vtrnewjersey,
        Mux.vtrseattle,
        Mux.vtrsilicon,
        Mux.vtrtoronto,
    ],
    "sa": [
        Mux.vtrsantiago,
        Mux.vtrsaopaulo,
    ],
    "asia": [
        Mux.vtrbangalore,
        Mux.vtrdelhi,
        Mux.vtrmelbourne,
        Mux.vtrmumbai,
        Mux.vtrosaka,
        Mux.vtrseoul,
        Mux.vtrsingapore,
        Mux.vtrsydney,
        Mux.vtrtokyo,
    ],
    "japan": [
        Mux.vtrosaka,
        Mux.vtrtokyo,
    ],
    "india": [
        Mux.vtrbangalore,
        Mux.vtrdelhi,
        Mux.vtrmumbai,
    ],
}


class Announcement(BaseModel):
    muxes: Annotated[set[Mux], Field(min_length=1)]
    peer_ids: list[int] = Field(default_factory=list)
    """Peer IDs to announce to (communities will be computed automatically)"""
    communities: list[tuple[int, int]] = Field(default_factory=list)
    """List of communities to attach to announcement"""
    large_communities: list[tuple[int, int, int]] = Field(default_factory=list)
    """List of BGP large communities to attach to announcement"""
    prepend: Annotated[list[int], Field(max_length=5)] = Field(default_factory=list)
    """List of ASNs to prepend to AS-path"""

    def is_plain(self) -> bool:
        return (
            (not self.peer_ids)
            and (not self.communities)
            and (not self.large_communities)
            and (not self.prepend)
        )


class Update(BaseModel):
    withdraw: set[Mux] = Field(default_factory=set)
    announce: list[Announcement] = Field(default_factory=list)
    description: str | None = None

    def find_egress_mux(
        self,
        egress_priority: list[Mux] | None,
    ) -> Mux:
        """Get egress prioritizing plain announcements from muxes in priority list."""
        assert self.announce

        announcing: set[Mux] = set()
        announcing_plain: set[Mux] = set()
        for ann in self.announce:
            announcing.update(ann.muxes)
            if ann.is_plain():
                announcing_plain.update(ann.muxes)

        assert not (self.withdraw & announcing)

        if egress_priority is not None:
            for mux in egress_priority:
                if mux in announcing_plain:
                    return mux
            for mux in egress_priority:
                if mux in announcing:
                    return mux

        if announcing_plain:
            return next(iter(announcing_plain))

        return next(iter(announcing))


class UpdateSet(BaseModel):
    prefix2update: dict[IPv4Network | IPv6Network, Update]


class ControllerConfig(BaseModel):
    prefixes: list[IPv4Network | IPv6Network]
    bird_cfg_dir: pathlib.Path
    bird4_sock: pathlib.Path
    bird6_sock: pathlib.Path
    openvpn_cfg_dir: pathlib.Path
    base_ip_rule_prio: int

    @classmethod
    def from_basedir(
        cls,
        path: pathlib.Path,
        read_prefixes: bool = True,
        base_ip_rule_prio: int = 4000,
    ) -> Self:
        prefixes = []
        if read_prefixes:
            p4fp = path / "prefixes.txt"
            p6fp = path / "prefixes6.txt"
            if p4fp.exists():
                prefixes.extend([IPv4Network(v) for v in p4fp.read_text().splitlines()])
                prefixes.extend([IPv6Network(v) for v in p6fp.read_text().splitlines()])
        return cls(
            prefixes=prefixes,
            bird_cfg_dir=path / "configs/bird/",
            bird4_sock=path / "var/bird.ctl",
            bird6_sock=path / "var/bird6.ctl",
            openvpn_cfg_dir=path / "configs/openvpn/",
            base_ip_rule_prio=base_ip_rule_prio,
        )


class Experiment(BaseModel):
    description: str
    email: str
    rounds: list[dict[str, Update]]


class ExperimentEnvelope(BaseModel):
    experiment: Experiment


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
    def __init__(self, config: ControllerConfig) -> None:
        assert config.bird_cfg_dir.exists(), str(config.bird_cfg_dir)
        self.config = config
        assert config.bird4_sock.exists() or config.bird6_sock.exists()
        self.last_updates: UpdateSet | None = None
        self.__create_routes()

    @staticmethod
    def render_bird_config(
        prefix: IPv4Network | IPv6Network, ann: Announcement
    ) -> str:
        lines = [f"if ( net = {prefix} ) then {{"]
        for asn in reversed(ann.prepend):
            lines.append(f"    bgp_path.prepend({asn});")
        for c in ann.peer_ids:
            lines.append(f"    bgp_community.add((47065,{c}));")
        for c1, c2 in ann.communities:
            lines.append(f"    bgp_community.add(({c1},{c2}));")
        for c1, c2, c3 in ann.large_communities:
            lines.append(f"    bgp_large_community.add(({c1},{c2},{c3}));")
        lines.append("    accept;")
        lines.append("}")
        return "\n".join(lines) + "\n"

    def __config_file(
        self, prefix: IPv4Network | IPv6Network, mux: Mux
    ) -> pathlib.Path:
        pfx_str = str(prefix).replace("/", "-")
        pfx_str = pfx_str.replace(":", "i")  # removing colon from v6 prefixes
        fn = f"export_{mux}_{pfx_str}.conf"
        return self.config.bird_cfg_dir / "prefix-filters" / fn

    def __create_routes(self) -> None:
        path = self.config.bird_cfg_dir / "route-announcements"
        path.mkdir(parents=True, exist_ok=True)
        for pfx in self.config.prefixes:
            fpath = path / str(pfx).replace("/", "-")
            fd = open(fpath, "w", encoding="utf8")
            fd.write(f"route {pfx} unreachable;\n")
            fd.close()

    @cached_property
    def mux2id(self) -> dict[Mux, int]:
        return build_mux2id(self.config.openvpn_cfg_dir)

    def deploy(
        self,
        updates: UpdateSet,
        set_egress: bool = False,
        egress_priority: list[Mux] | None = None,
    ) -> None:
        self.last_updates = updates
        for prefix, update in updates.prefix2update.items():
            for mux in update.withdraw:
                self.withdraw(prefix, mux, set_egress)
            for announcement in update.announce:
                self.announce(prefix, announcement)
        self.reload_config()

        if set_egress:
            for prefix, update in updates.prefix2update.items():
                if not update.announce:
                    continue
                egress_mux = update.find_egress_mux(egress_priority)
                self.set_egress(prefix, egress_mux, None)

    def withdraw(
        self,
        prefix: IPv4Network | IPv6Network | None = None,
        mux: Mux | None = None,
        unset_egress: bool = False,
    ) -> None:
        if prefix is None:
            if self.last_updates:
                for pfx in self.last_updates.prefix2update:
                    self.withdraw(pfx, mux, unset_egress)
            else:
                m = "withdraw call with no prefixes and no prior announcement"
                logging.warning(m)
            return

        if unset_egress:
            self.unset_egress(prefix)

        if mux is None or mux == "all":
            for emux in Mux:
                self.withdraw(prefix, emux)
            return

        try:
            self.__config_file(prefix, mux).unlink()
        except FileNotFoundError:
            pass

    def announce(self, prefix: IPv4Network | IPv6Network, ann: Announcement) -> None:
        for mux in ann.muxes:
            with open(self.__config_file(prefix, mux), "w", encoding="utf8") as fd:
                data = AnnouncementController.render_bird_config(prefix, ann)
                fd.write(data)

    def reload_config(self) -> None:
        for execname, sockpath in [
            ("birdc", self.config.bird4_sock),
            ("birdc6", self.config.bird6_sock),
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
        prefix: IPv4Network | IPv6Network,
        mux: Mux,
        peerid: int | None,
    ) -> None:
        prio = self.config.base_ip_rule_prio + get_ip_rule_prio_offset(prefix)

        muxid = self.mux2id[mux]
        if isinstance(prefix, IPv4Network):
            if peerid is None:
                gateway = f"100.{64 + muxid}.128.1"
            else:
                gateway = f"100.{64 + muxid}.{peerid // 256}.{peerid % 256}"
        elif isinstance(prefix, IPv6Network):
            if peerid is None:
                gateway = f"2804:269c:ff00:{muxid:x}:1::1"
            else:
                gateway = f"2804:269c:ff00:{muxid:x}::{peerid:x}"
        else:
            assert_never(prefix)

        family = socket.AF_INET6 if isinstance(prefix, IPv6Network) else socket.AF_INET

        with IPRoute() as ip:
            logging.info(
                "pyroute2: rule add from %s lookup %d prio %d",
                prefix,
                prio,
                prio,
            )
            ip.rule("add", priority=prio, table=prio, src=str(prefix), family=family)

            logging.info("pyroute2: flushing route table %d", prio)
            ip.flush_routes(table=prio)

            logging.info("pyroute2: route add default via %s table %d", gateway, prio)
            ip.route("add", dst="default", gateway=gateway, table=prio)

    def unset_egress(self, prefix: IPv4Network | IPv6Network) -> None:
        prio = self.config.base_ip_rule_prio + get_ip_rule_prio_offset(prefix)
        logging.info("Unsetting egress for prefix %s (prio %d)", prefix, prio)
        with IPRoute() as ip:
            ip.flush_routes(table=prio)
            for rule in ip.get_rules(priority=prio):
                try:
                    ip.rule("del", **rule)
                except Exception as e:
                    logging.debug("failed to delete rule: %s", e)


PROTOCOL_REGEX = re.compile(r"up(?P<peerid>\d+)_(?P<asn>\d+)")


def protocol_to_peerid_asn(proto: str) -> tuple[int, int]:
    m = PROTOCOL_REGEX.match(proto)
    if not m:
        raise ValueError(f"Invalid protocol name {proto}")
    peerid = int(m.group("peerid"))
    asn = int(m.group("asn"))
    return (peerid, asn)


class ExperimentController:
    def __init__(
        self,
        url: str,
        token: str,
        refresh: str | None = None,
    ):
        self.url = url
        self.token = token  # access-token
        self.refresh = refresh  # refresh-token

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
        ExperimentEnvelope.model_validate(experiment)
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
    parser.add_argument(
        "--set-egress",
        action="store_true",
        dest="set_egress",
        help="Set egress rules after deployment",
    )
    parser.add_argument(
        "--egress-priority",
        type=str,
        nargs="+",
        dest="egress_priority",
        help="List of muxes in priority order for egress",
    )
    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    if args.announcement:
        with open(args.announcement, encoding="utf8") as announcement_json_fd:
            announcement_dict = json.load(announcement_json_fd)
            announcement = UpdateSet.model_validate(
                {"prefix2update": announcement_dict}
            )
        config = ControllerConfig.from_basedir(AUTO_BASE_DIR)
        ctrl = AnnouncementController(config)
        ctrl.deploy(
            announcement,
            set_egress=args.set_egress,
            egress_priority=args.egress_priority,
        )
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
