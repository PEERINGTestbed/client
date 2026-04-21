import socket
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
)
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from pyroute2 import IPRoute  # pyright: ignore

from peering import Announcement, DataPlane, Mux, Update, prefix2id

REPO_ROOT = Path(__file__).resolve().parents[3]
IFNAME = "lo"
V4IFACE = IPv4Interface("184.164.224.1/24")
V6IFACE = IPv6Interface("2804:269c:3::1/48")


class TestModels:
    def test_prefix2id_ipv4(self) -> None:
        prefix = IPv4Network("184.164.224.0/24")
        assert prefix2id(prefix) == 224

    def test_prefix2id_ipv6(self) -> None:
        prefix = IPv6Network("2804:269c:3::/48")
        assert prefix2id(prefix) == int(prefix.network_address.packed[5])
        assert prefix2id(prefix) == 3

    def test_announcement_is_plain(self) -> None:
        assert Announcement(muxes={Mux.ufmg01}).is_plain()
        assert not Announcement(muxes={Mux.ufmg01}, peer_ids=[1]).is_plain()

    def test_update_is_unicast(self) -> None:
        update = Update(announce=[Announcement(muxes={Mux.ufmg01})])
        assert update.is_unicast()
        update = Update(announce=[Announcement(muxes={Mux.ufmg01, Mux.amsterdam01})])
        assert not update.is_unicast()

    def test_find_egress_mux_prefers_by_priority(self) -> None:
        update = Update(
            announce=[
                Announcement(muxes={Mux.ufmg01}, prepend=[64500]),
                Announcement(muxes={Mux.clemson01}),
            ]
        )
        assert update.find_egress_mux([Mux.ufmg01]) == Mux.ufmg01

    def test_find_egress_mux_prefers_plain_announcement_with_priority(self) -> None:
        update = Update(
            announce=[
                Announcement(muxes={Mux.ufmg01}, prepend=[64500]),
                Announcement(muxes={Mux.clemson01}),
            ]
        )
        assert update.find_egress_mux([Mux.ufmg01, Mux.clemson01]) == Mux.clemson01

    def test_find_egress_mux_prefers_plain_announcement(self) -> None:
        update = Update(
            announce=[
                Announcement(muxes={Mux.ufmg01}, prepend=[64500]),
                Announcement(muxes={Mux.clemson01}),
            ]
        )
        assert update.find_egress_mux([]) == Mux.clemson01


class TestDataPlane:
    def setup_method(self) -> None:
        self._cleanup_test_ips()

    def teardown_method(self) -> None:
        self._cleanup_test_ips()

    def _cleanup_test_ips(self) -> None:
        ips_to_remove: list[IPv4Interface | IPv6Interface] = [V4IFACE, V6IFACE]
        with IPRoute() as ipr:
            idxs = ipr.link_lookup(ifname=IFNAME)
            if not idxs:
                return
            lo_idx = idxs[0]
            for ipiface in ips_to_remove:
                prefixlen = ipiface.network.prefixlen
                family = socket.AF_INET if ipiface.version == 4 else socket.AF_INET6
                if DataPlane.is_assigned(ipiface, ifname=IFNAME):
                    ipr.addr(
                        "del",
                        index=lo_idx,
                        address=str(ipiface.ip),
                        prefixlen=prefixlen,
                        family=family,
                    )

    @staticmethod
    def _get_rules_with_priority(priority: int, family: int) -> list[Any]:
        with IPRoute() as ipr:
            return list(ipr.get_rules(family=family, priority=priority))

    @staticmethod
    def _get_default_routes(table: int, family: int) -> list[Any]:
        with IPRoute() as ipr:
            return [
                route
                for route in ipr.get_routes(family=family, table=table)
                if route.get("dst_len") == 0
            ]

    def test_assign_ip_v4(self) -> None:
        assert not DataPlane.is_assigned(V4IFACE, ifname=IFNAME)
        DataPlane.assign_ip(V4IFACE, ifname=IFNAME)
        assert DataPlane.is_assigned(V4IFACE, ifname=IFNAME)
        DataPlane.assign_ip(V4IFACE, ifname=IFNAME)

    def test_assign_ip_v6(self) -> None:
        assert not DataPlane.is_assigned(V6IFACE, ifname=IFNAME)
        DataPlane.assign_ip(V6IFACE, ifname=IFNAME)
        assert DataPlane.is_assigned(V6IFACE, ifname=IFNAME)
        DataPlane.assign_ip(V6IFACE, ifname=IFNAME)

    def test_assign_ip_interface_not_found(self) -> None:
        with pytest.raises(RuntimeError, match="Interface nonexistent_if not found"):
            DataPlane.assign_ip(V4IFACE, ifname="nonexistent_if")
        with pytest.raises(RuntimeError, match="Interface nonexistent_if not found"):
            DataPlane.assign_ip(V6IFACE, ifname="nonexistent_if")

    @pytest.mark.parametrize("interface", [V4IFACE, V6IFACE])
    def test_unassign_ip(self, interface: IPv4Interface | IPv6Interface) -> None:
        assert not DataPlane.is_assigned(interface, ifname=IFNAME)
        DataPlane.assign_ip(interface, ifname=IFNAME)
        assert DataPlane.is_assigned(interface, ifname=IFNAME)

        DataPlane.unassign_ip(interface, ifname=IFNAME)
        assert not DataPlane.is_assigned(interface, ifname=IFNAME)

        DataPlane.unassign_ip(interface, ifname=IFNAME)

    def test_is_connected_v4_success(self) -> None:
        assert DataPlane.is_connected(IPv4Address("127.0.0.1"))

    def test_is_connected_v6_success(self) -> None:
        assert DataPlane.is_connected(IPv6Address("::1"))

    def test_is_connected_fail(self) -> None:
        assert not DataPlane.is_connected(IPv4Address("8.8.8.8"))

    def test_mux2id(self) -> None:
        dp = DataPlane(basedir=REPO_ROOT)
        assert dp.mux2id[Mux.amsterdam01] == 5

    def test_update_and_unset_egresses(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        dp = DataPlane(basedir=REPO_ROOT)
        interface = V4IFACE
        gateway = V4IFACE.ip + 1
        prefix = interface.network
        table = dp.get_egress_table(prefix)
        family = socket.AF_INET if prefix.version == 4 else socket.AF_INET6

        monkeypatch.setattr(dp, "get_openvpn_gateway", Mock(return_value=gateway))

        assert self._get_rules_with_priority(table, family) == []
        assert self._get_default_routes(table, family) == []

        DataPlane.assign_ip(interface, ifname=IFNAME)
        assert DataPlane.is_connected(gateway)
        prefix2mux = dp.update_egresses(
            {prefix: Update(withdraw=set(), announce=[Announcement(muxes={Mux.amsterdam01})])},
            [Mux.amsterdam01],
        )

        assert prefix2mux == {prefix: Mux.amsterdam01}

        rules = self._get_rules_with_priority(table, family)
        assert len(rules) == 1
        assert rules[0].get("table") == table
        assert rules[0].get_attr("FRA_SRC") == str(prefix.network_address)
        assert rules[0].get("src_len") == prefix.prefixlen

        routes = self._get_default_routes(table, family)
        assert len(routes) == 1
        assert routes[0].get("table") == table
        assert routes[0].get_attr("RTA_GATEWAY") == str(gateway)

        dp.unset_egresses([prefix])

        assert self._get_rules_with_priority(table, family) == []
        assert self._get_default_routes(table, family) == []
