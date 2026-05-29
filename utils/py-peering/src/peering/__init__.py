from __future__ import annotations

import enum
import ipaddress
import itertools
import json
import logging
import pathlib
import re
import socket
import subprocess
from functools import cached_property, lru_cache
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
)
import time
from collections.abc import Iterable, Mapping
from typing import (
    Any,
    Callable,
    Iterator,
    Literal,
    Self,
    TypeAlias,
    assert_never,
    overload,
)

from pydantic import BaseModel, Field
from pyroute2 import IPRoute  # pyright: ignore

BASE_TABLE_NUM = 14000
MIN_ROUND_WAIT = 300
IPAddress: TypeAlias = IPv4Address | IPv6Address
IPInterface: TypeAlias = IPv4Interface | IPv6Interface
IPNetwork: TypeAlias = IPv4Network | IPv6Network


class Mux(enum.StrEnum):
    amsterdam01 = "amsterdam01"
    cfuseast1 = "cfuseast1"
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


class Announcement(BaseModel):
    muxes: set[Mux] = Field(min_length=1)
    """List of muxes announcement will be made to"""
    peer_ids: list[int] = Field(default_factory=list[int])
    """Peer IDs to announce to (communities will be computed automatically)"""
    communities: list[tuple[int, int]] = Field(default_factory=list[tuple[int, int]], max_length=20)
    """List of communities to attach to announcement"""
    large_communities: list[tuple[int, int, int]] = Field(default_factory=list[tuple[int, int, int]], max_length=20)  # fmt: off
    """List of BGP large communities to attach to announcement"""
    prepend: list[int] = Field(default_factory=list[int], max_length=5)
    """List of ASNs to prepend to AS-path"""

    def is_plain(self) -> bool:
        return (
            (not self.peer_ids)
            and (not self.communities)
            and (not self.large_communities)
            and (not self.prepend)
        )


class Update(BaseModel):
    withdraw: set[Mux] = Field(default_factory=set[Mux])
    announce: list[Announcement] = Field(default_factory=list[Announcement])
    description: str | None = None

    def is_unicast(self) -> bool:
        return len(self.announce) == 1 and len(self.announce[0].muxes) == 1

    def find_egress_mux(self, egress_priority: list[Mux]) -> Mux:
        """Get the preferred egress mux for the update.

        Plain announcements are preferred over annotated announcements, and the
        caller-provided priority list breaks ties.
        """
        assert self.announce

        announcing: set[Mux] = set()
        announcing_plain: set[Mux] = set()
        for ann in self.announce:
            announcing.update(ann.muxes)
            if ann.is_plain():
                announcing_plain.update(ann.muxes)

        assert not (self.withdraw & announcing)

        # We give higher priority to muxes in egress_priority; then
        # prefer muxes making plain announcements over muxes making
        # annotated announcements:
        for mux in egress_priority:
            if mux in announcing_plain:
                return mux
        for mux in egress_priority:
            if mux in announcing:
                return mux
        if announcing_plain:
            return next(iter(announcing_plain))
        return next(iter(announcing))


class DataPlane:
    def __init__(self, basedir: pathlib.Path, base_table_num: int = BASE_TABLE_NUM) -> None:
        target = basedir / "configs/openvpn/amsterdam01.conf"
        if not target.exists():
            logging.error("DataPlane basedir error; %s does not exist", target)
            raise ValueError(f"{target} does not exist")
        self.basedir = basedir
        self.base_table_num = base_table_num

    @cached_property
    def mux2id(self) -> dict[Mux, int]:
        return build_mux2id(self.basedir / "configs/openvpn")

    @overload
    def get_openvpn_gateway(
        self, mux: Mux, version: Literal[4], peerid: int = 0
    ) -> IPv4Address: ...

    @overload
    def get_openvpn_gateway(
        self, mux: Mux, version: Literal[6], peerid: int = 0
    ) -> IPv6Address: ...

    def get_openvpn_gateway(self, mux: Mux, version: Literal[4, 6], peerid: int = 0) -> IPAddress:
        if version == 4:
            return self.get_openvpn_gateway_v4(mux, peerid)
        if version == 6:
            return self.get_openvpn_gateway_v6(mux, peerid)
        assert_never()

    def get_openvpn_gateway_v4(self, mux: Mux, peerid: int = 0) -> IPv4Address:
        muxid = self.mux2id[mux]
        if peerid == 0:
            return IPv4Address(f"100.{64 + muxid}.128.1")
        return IPv4Address(f"100.{64 + muxid}.{peerid // 256}.{peerid % 256}")

    def get_openvpn_gateway_v6(self, mux: Mux, peerid: int = 0) -> IPv6Address:
        muxid = self.mux2id[mux]
        if peerid == 0:
            return IPv6Address(f"2804:269c:ff00:{muxid:x}:1::1")
        return IPv6Address(f"2804:269c:ff00:{muxid:x}::{peerid:x}")

    def update_egresses(
        self,
        prefix2update: Mapping[IPNetwork, Update],
        egress_priority: list[Mux] = [],
    ) -> dict[IPNetwork, Mux]:
        prefixes = set(prefix2update)
        self.unset_egresses(prefixes)
        pfx2mux: dict[IPNetwork, Mux] = {}

        for pfx, upd in prefix2update.items():
            if not upd.announce:
                continue

            egress_mux = upd.find_egress_mux(egress_priority)
            gw = self.get_openvpn_gateway(egress_mux, pfx.version)
            family = socket.AF_INET6 if pfx.version == 6 else socket.AF_INET

            tid = self.get_egress_table(pfx)
            with IPRoute() as ip:
                logging.info("pyroute2: rule add from %s lookup %d", pfx, tid)
                ip.rule("add", priority=tid, table=tid, src=str(pfx), family=family)
                logging.info("pyroute2: route add default via %s table %d", gw, tid)
                ip.route("add", dst="default", gateway=str(gw), table=tid, family=family)

            pfx2mux[pfx] = egress_mux
        return pfx2mux

    def unset_egresses(self, prefixes: Iterable[IPNetwork]) -> None:
        for pfx in set(prefixes):
            tid = self.get_egress_table(pfx)
            with IPRoute() as ip:
                logging.info("pyroute2: flush route table %d", tid)
                ip.flush_routes(table=tid)
                logging.info("pyroute2: rule del prio %d", tid)
                ip.flush_rules(priority=tid)

    def get_egress_table(self, prefix: IPNetwork) -> int:
        """Computes the IP routing table number and rule priority for a source prefix."""
        return self.base_table_num + prefix2id(prefix)

    @staticmethod
    def assign_ip(ip: IPInterface, ifname: str = "lo") -> None:
        """Assigns the given IP address to the interface if not already assigned."""
        if DataPlane.is_assigned(ip, ifname):
            return

        family = socket.AF_INET if ip.version == 4 else socket.AF_INET6
        with IPRoute() as ipr:
            idxs = ipr.link_lookup(ifname=ifname)
            if not idxs:
                raise RuntimeError(f"Interface {ifname} not found")
            ifindex = idxs[0]
            prefixlen = ip.network.prefixlen
            logging.info("assigning %s to interface %s", ip, ifname)
            ipr.addr("add", index=ifindex, address=str(ip), prefixlen=prefixlen, family=family)

    @staticmethod
    def unassign_ip(ip: IPInterface, ifname: str = "lo") -> None:
        """Removes the given IP address from the interface if present."""
        if not DataPlane.is_assigned(ip, ifname):
            return

        family = socket.AF_INET if ip.version == 4 else socket.AF_INET6
        with IPRoute() as ipr:
            idxs = ipr.link_lookup(ifname=ifname)
            if not idxs:
                raise RuntimeError(f"Interface {ifname} not found")
            ifindex = idxs[0]
            prefixlen = ip.network.prefixlen
            logging.info("removing %s from interface %s", ip, ifname)
            ipr.addr("del", index=ifindex, address=str(ip), prefixlen=prefixlen, family=family)

    @staticmethod
    def is_assigned(ip: IPInterface, ifname: str = "lo") -> bool:
        """Checks if the given IP interface is assigned to the interface."""
        family = socket.AF_INET if ip.version == 4 else socket.AF_INET6
        with IPRoute() as ipr:
            idxs = ipr.link_lookup(ifname=ifname)
            if not idxs:
                raise RuntimeError(f"Interface {ifname} not found")
            ifindex = idxs[0]
            prefixlen = ip.network.prefixlen

            for addr in ipr.get_addr(index=ifindex, family=family):
                if addr.get("prefixlen") != prefixlen:
                    continue
                for attr in addr.get("attrs", []):
                    if attr[0] in ("IFA_ADDRESS", "IFA_LOCAL") and attr[1] == str(ip.ip):
                        return True
            return False

    @staticmethod
    def is_connected(gateway: IPAddress) -> bool:
        """Checks whether one interface is on the same subnet as gateway."""
        family = socket.AF_INET if gateway.version == 4 else socket.AF_INET6
        with IPRoute() as ipr:
            for addr in ipr.get_addr(family=family):
                prefixlen = addr["prefixlen"]
                for attr in addr.get("attrs", []):
                    if attr[0] in ("IFA_ADDRESS", "IFA_LOCAL"):
                        address = attr[1]
                        net = ipaddress.ip_network(f"{address}/{prefixlen}", strict=False)
                        if gateway in net:
                            return True
            return False


def prefix2id(prefix: IPNetwork) -> int:
    """Computes an identifier for a prefix based on one of its octets.

    For IPv4, it is based off the value of the 3rd octet of the network address.
    For IPv6, it is based off the value of the 6th octet (bits 40-47 of the prefix).
    """
    if isinstance(prefix, IPv4Network):
        return int(prefix.network_address.packed[2])
    if isinstance(prefix, IPv6Network):  # pyright: ignore[reportUnnecessaryIsInstance]
        return int(prefix.network_address.packed[5])
    assert_never(prefix)


class ControlPlane:
    class Config(BaseModel):
        prefixes: list[IPNetwork]
        bird_cfg_dir: pathlib.Path
        bird4_sock: pathlib.Path
        bird6_sock: pathlib.Path
        openvpn_cfg_dir: pathlib.Path

        @classmethod
        def from_basedir(
            cls,
            path: pathlib.Path,
            prefixes: list[IPNetwork],
        ) -> Self:
            return cls(
                prefixes=prefixes,
                bird_cfg_dir=path / "configs/bird",
                bird4_sock=path / "var/bird.ctl",
                bird6_sock=path / "var/bird6.ctl",
                openvpn_cfg_dir=path / "configs/openvpn",
            )

    class PeeringCommunities:
        @staticmethod
        def do_not_announce(peer_id: int) -> tuple[int, int]:
            return (47065, 1000 + peer_id)

        @staticmethod
        def announce_to(peer_id: int) -> tuple[int, int]:
            return (47065, peer_id)

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

    def __init__(self, config: ControlPlane.Config) -> None:
        assert config.bird_cfg_dir.exists(), str(config.bird_cfg_dir)
        assert config.bird4_sock.exists() or config.bird6_sock.exists()
        self.config = config
        self.last_updates: dict[IPNetwork, Update] | None = None
        self._create_routes()

    def deploy(
        self,
        prefix2update: dict[IPNetwork, Update],
    ) -> None:
        self.last_updates = prefix2update
        for prefix, update in prefix2update.items():
            for mux in update.withdraw:
                self.withdraw(prefix, mux)
            for announcement in update.announce:
                self._announce(prefix, announcement)
        self._reload_config()

    def withdraw(
        self,
        prefix: IPNetwork | None = None,
        mux: Mux | Literal["all"] | None = None,
    ) -> None:
        if prefix is None:
            if self.last_updates:
                for pfx in self.last_updates:
                    self._withdraw_prefix(pfx, mux)
                self._reload_config()
            else:
                m = "withdraw call with no prefixes and no prior announcement"
                logging.warning(m)
            return

        self._withdraw_prefix(prefix, mux)
        self._reload_config()

    def _withdraw_prefix(self, prefix: IPNetwork, mux: Mux | Literal["all"] | None) -> None:
        if mux is None or mux == "all":
            for emux in Mux:
                self._config_file(prefix, emux).unlink(missing_ok=True)
            return

        self._config_file(prefix, mux).unlink(missing_ok=True)

    def _announce(self, prefix: IPNetwork, ann: Announcement) -> None:
        for mux in ann.muxes:
            config_file = self._config_file(prefix, mux)
            data = ControlPlane._render_bird_config(prefix, ann)
            config_file.write_text(data, encoding="utf8")

    def _config_file(self, prefix: IPNetwork, mux: Mux) -> pathlib.Path:
        pfx_str = str(prefix).replace("/", "-").replace(":", "i")
        fn = f"export_{mux}_{pfx_str}.conf"
        return self.config.bird_cfg_dir / "prefix-filters" / fn

    def _create_routes(self) -> None:
        path = self.config.bird_cfg_dir / "route-announcements"
        path.mkdir(parents=True, exist_ok=True)
        for pfx in self.config.prefixes:
            fpath = path / str(pfx).replace("/", "-")
            fpath.write_text(f"route {pfx} unreachable;\n", encoding="utf8")

    def _reload_config(self) -> None:
        for execname, sockpath in [
            ("birdc", self.config.bird4_sock),
            ("birdc6", self.config.bird6_sock),
        ]:
            if not sockpath.exists() or not sockpath.is_socket():
                logging.debug("%s is not a unix socket, skipping", sockpath)
                continue

            proc = subprocess.Popen(  # noqa: S603
                [execname, "-s", str(sockpath)],
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

    @staticmethod
    def _render_bird_config(prefix: IPNetwork, ann: Announcement) -> str:
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


class Sequencer:
    class Config(BaseModel):
        description: str
        basedir: pathlib.Path
        outdir: pathlib.Path
        prefixes: list[IPNetwork]
        round_duration: int
        withdraw_every_round: bool
        withdraw_duration: int
        egress_priority: list[Mux]
        updates: list[Update]

    class RoundCallback[CallbackData](BaseModel):
        name: str
        func: Callable[
            [
                dict[IPNetwork, Update],  # prefix2update
                dict[IPNetwork, Mux],  # prefix2egress
                pathlib.Path,  # round_outdir
                CallbackData,
            ],
            dict[str, float],  # event label-to-timestamp mapping
        ]
        data: CallbackData

    def __init__(self, config: Sequencer.Config) -> None:
        self.config = config
        self.control_plane = ControlPlane(
            ControlPlane.Config.from_basedir(config.basedir, config.prefixes)
        )
        self.data_plane = DataPlane(config.basedir)
        logging.info(
            "Sequencer using %d prefixes to issue %d updates",
            len(self.config.prefixes),
            len(self.config.updates),
        )

    def run(self, callbacks: list[RoundCallback[Any]], first_round: int = 0) -> None:
        self.data_plane.unset_egresses(self.config.prefixes)
        self.control_plane.withdraw()

        tstamps: dict[str, float] = {}
        done = False
        roundidx = first_round
        updates_iter = itertools.islice(
            self.config.updates, first_round * len(self.config.prefixes), None
        )

        while not done:
            logging.info("#####################################################")
            logging.info("Starting round %d", roundidx)
            tstamps["round-start"] = time.time()

            pfx2upd = self._collect_updates(updates_iter)
            if not pfx2upd:
                done = True
                break

            tstamps["deploy-pfx2ann"] = time.time()
            pfx2mux = self.data_plane.update_egresses(pfx2upd, self.config.egress_priority)
            self.control_plane.deploy(pfx2upd)

            round_outdir = self.config.outdir / f"round{roundidx}"
            round_outdir.mkdir(parents=True, exist_ok=True)
            self._save_round_artifacts(round_outdir, pfx2upd, pfx2mux)

            self._run_callbacks(callbacks, pfx2upd, pfx2mux, round_outdir, tstamps)
            self._wait_for_round_duration(tstamps)

            self.data_plane.unset_egresses(self.config.prefixes)

            if self.config.withdraw_every_round:
                self._withdraw_after_round(roundidx, tstamps)

            outfd = round_outdir / "timestamps.json"
            outfd.write_text(json.dumps(tstamps, indent=2), encoding="utf8")

            roundidx += 1

    def _collect_updates(self, updates_iter: Iterator[Update]) -> dict[IPNetwork, Update]:
        pfx2upd: dict[IPNetwork, Update] = {}
        for prefix in self.config.prefixes:
            try:
                pfx2upd[prefix] = next(updates_iter)
            except StopIteration:
                break
        return pfx2upd

    def _save_round_artifacts(
        self,
        round_outdir: pathlib.Path,
        pfx2upd: dict[IPNetwork, Update],
        pfx2mux: dict[IPNetwork, Mux],
    ) -> None:
        logging.debug("Saving announcements.json and egresses.json for %s", round_outdir)
        announcements = {str(pfx): upd.model_dump(mode="json") for pfx, upd in pfx2upd.items()}
        outfd = round_outdir / "announcements.json"
        outfd.write_text(json.dumps(announcements, indent=2), encoding="utf8")
        egresses = {str(pfx): str(mux) for pfx, mux in pfx2mux.items()}
        outfd = round_outdir / "egresses.json"
        outfd.write_text(json.dumps(egresses, indent=2), encoding="utf8")

    def _run_callbacks(
        self,
        callbacks: list[RoundCallback[Any]],
        pfx2upd: dict[IPNetwork, Update],
        pfx2mux: dict[IPNetwork, Mux],
        round_outdir: pathlib.Path,
        tstamps: dict[str, float],
    ) -> None:
        logging.info("Running callbacks for %s", round_outdir)
        tstamps["callbacks-start"] = time.time()
        for cb in callbacks:
            tstamps[f"cb-{cb.name}-start"] = time.time()
            cb_tstamps = cb.func(pfx2upd, pfx2mux, round_outdir, cb.data)
            tstamps[f"cb-{cb.name}-end"] = time.time()
            duration = tstamps[f"cb-{cb.name}-end"] - tstamps[f"cb-{cb.name}-start"]
            logging.info("    %s completed in %fs", cb.name, duration)
            cb_tstamps = {f"cb-{cb.name}/{k}": v for k, v in cb_tstamps.items()}
            tstamps.update(cb_tstamps)
        tstamps["callbacks-end"] = time.time()

    def _wait_for_round_duration(self, tstamps: dict[str, float]) -> None:
        cb_duration = tstamps["callbacks-end"] - tstamps["callbacks-start"]
        spare_time = self.config.round_duration - cb_duration
        logging.info("Callbacks completed in %fs (%ds to spare)", cb_duration, spare_time)
        round_wait = max(MIN_ROUND_WAIT, spare_time)
        logging.info("Sleeping %fs to complete round duration", round_wait)
        time.sleep(round_wait)
        tstamps["round-end"] = time.time()

    def _withdraw_after_round(self, roundidx: int, tstamps: dict[str, float]) -> None:
        logging.info("Starting withdraw after round %d", roundidx)
        tstamps["withdraw-start"] = time.time()
        self.control_plane.withdraw()
        logging.info("Waiting %ds for withdrawals to converge", self.config.withdraw_duration)
        time.sleep(self.config.withdraw_duration)
        tstamps["withdraw-end"] = time.time()


@lru_cache(maxsize=3)
def build_mux2id(cfgs_dir: pathlib.Path) -> dict[Mux, int]:
    """Builds the mux to ID mapping by reading OpenVPN configuration files.

    Raises:
        RuntimeError: When OpenVPN configurations are not found."""

    if not (cfgs_dir / "amsterdam01.conf").exists():
        cfgs_dir = cfgs_dir / "configs/openvpn"
        if not (cfgs_dir / "amsterdam01.conf").exists():
            raise RuntimeError("OpenVPN configurations not found")

    mux2id: dict[Mux, int] = {}
    dev_re = re.compile(r"^dev\s+tap(\d+)", re.MULTILINE)

    for fn in sorted(cfgs_dir.glob("*.conf")):
        try:
            mux = Mux(fn.stem)
        except ValueError:
            logging.warning("OpenVPN config %s does not match a known MuxName", fn)
            continue
        content = fn.read_text()
        match = dev_re.search(content)
        if match:
            mux2id[mux] = int(match.group(1))

    assert mux2id
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


PROTOCOL_REGEX = re.compile(r"up(?P<peerid>\d+)_(?P<asn>\d+)")


def protocol_to_peerid_asn(proto: str) -> tuple[int, int]:
    m = PROTOCOL_REGEX.match(proto)
    if not m:
        raise ValueError(f"Invalid protocol name {proto}")
    peerid = int(m.group("peerid"))
    asn = int(m.group("asn"))
    return (peerid, asn)
