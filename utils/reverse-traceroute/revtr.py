# from __future__ import annotations
import logging
import requests
import dataclasses
import enum
import json
from ipaddress import IPv4Address
from typing import Optional

import simplejson
import simplejson.errors


DEFAULT_TIMEOUT = 32.0
BATCH_SIZE = 1000


class RevTrApi:
    def __init__(self, apikey: str, controller: str = "revtr.ccs.neu.edu") -> None:
        self.apikey = str(apikey)
        self.ctrl = str(controller)
        self.header = {
            "Revtr-Key": self.apikey,
        }

    def sources(self):
        url = f"https://{self.ctrl}/api/v1/sources"
        resp = requests.get(url, headers=self.header, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def atlas_reset(self, vp: IPv4Address):
        url = f"https://{self.ctrl}/api/v1/atlas/clean"
        headers = dict(self.header)
        headers.update({"source": str(vp)})
        resp = requests.post(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def atlas_rebuild(self, vp: IPv4Address):
        url = f"https://{self.ctrl}/api/v1/atlas/run"
        headers = dict(self.header)
        headers.update({"source": str(vp)})
        try:
            resp = requests.post(url, headers=headers, timeout=DEFAULT_TIMEOUT)
            # These requests timeout, but Kevin says they are honored by the RevTr backend
            resp.raise_for_status()
        except (requests.exceptions.ReadTimeout, requests.exceptions.HTTPError):
            logging.info("Error when making atlas rebuild request (this is OK)")
            return None
        return resp.json()

    def launch(self, vp: IPv4Address, remote: IPv4Address, label: str):
        url = f"https://{self.ctrl}/api/v1/revtr"
        data = {
            "revtrs": [
                {
                    "src": str(vp),
                    "dst": str(remote),
                    "label": label,
                }
            ]
        }
        resp = requests.post(
            url, data=json.dumps(data), headers=self.header, timeout=DEFAULT_TIMEOUT
        )
        resp.raise_for_status()
        return resp.json()

    def batch(self, pairs: list[tuple[str, str]], label: str):
        if len(pairs) > BATCH_SIZE:
            raise ValueError("Batch size too large")
        url = f"https://{self.ctrl}/api/v1/revtr"
        revtrs = [
            {
                "src": vp,
                "dst": remote,
                "label": label,
            }
            for vp, remote in pairs
        ]
        data = {"revtrs": revtrs}
        try:
            resp = requests.post(
                url, data=json.dumps(data), headers=self.header, timeout=DEFAULT_TIMEOUT
            )
            # These requests timeout, but Kevin says they are honored by the RevTr backend
            # resp.raise_for_status()
        except requests.exceptions.ReadTimeout:
            logging.info("ReadTimeout when submitting RevTr request, powering through")
            return None
        if resp.status_code == 502:
            logging.info("502 Bad Gateway when submitting RevTr request, powering through")
            return None
        try:
            return resp.json()
        except (simplejson.errors.JSONDecodeError):
            logging.info("JSON error from RevTr server; response body follows:")
            logging.info("%s", resp.text)
            logging.info("%s", pairs[0:5])
            return None

    def multibatch(self, pairs: list[tuple[str, str]], label: str) -> None:
        i = 0
        while i * BATCH_SIZE < len(pairs):
            batch = pairs[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
            self.batch(batch, f"{label}_{i}")
            i += 1

    def fetch(self, label: str):
        url = f"https://{self.ctrl}/api/v1/revtr?label={label}"
        resp = requests.get(url, headers=self.header)
        resp.raise_for_status()
        result = resp.json()
        return result


class RevTrHopType(enum.IntEnum):
    DUMMY = 0
    DST_REV_SEGMENT = 1
    DST_SYM_REV_SEGMENT = 2
    TR_TO_SRC_REV_SEGMENT = 3
    TR_TO_SRC_REV_SEGMENT_BETWEEN = 4
    RR_REV_SEGMENT = 5
    SPOOF_RR_REV_SEGMENT = 6
    TS_ADJ_REV_SEGMENT = 7
    SPOOF_TS_ADJ_REV_SEGMENT = 8
    SPOOF_TS_ADJ_REV_SEGMENT_TS_ZERO = 9
    SPOOF_TS_ADJ_REV_SEGMENT_TS_ZERO_DOUBLE_STAMP = 10


@dataclasses.dataclass
class RevTrHop:
    ip: IPv4Address
    asn: Optional[int]
    asname: Optional[str]
    cc: Optional[str]
    hoptype: RevTrHopType

    def __str__(self) -> str:
        return f"{self.ip} {self.asn} ({self.asname}) {self.cc} {self.hoptype.name}"


class RevTrMeasurement:
    def __init__(self, jsondata, ip2asn, namedb) -> None:
        self.status: str = str(jsondata["status"])
        self.stop_reason: str = str(jsondata["stopReason"])

        if self.stop_reason == "FAILED":
            raise ValueError("Reverse Traceroute failed")

        self.vp: IPv4Address = IPv4Address(jsondata["src"])
        self.remote: IPv4Address = IPv4Address(jsondata["dst"])
        self.orig_hops: list[RevTrHop] = []

        path = jsondata["path"]
        for hop in path:
            ip = IPv4Address(hop["hop"])
            hoptype = RevTrHopType[hop["type"]]
            asn, _prefix = ip2asn.lookup(hop["hop"])
            if asn is None:
                self.orig_hops.append(RevTrHop(ip, asn, None, None, hoptype))
                continue
            asname = namedb.short(asn)
            cc = namedb.cc(asn)
            self.orig_hops.append(RevTrHop(ip, asn, asname, cc, hoptype))

        self.is_trustworthy: bool = not self.contains_interdomain_assume_symmetry()
        self.hops: list[RevTrHop] = self.remove_as_loop_from_revtr_path()

    def __str__(self) -> str:
        header = f"Reverse Traceroute from remote {self.remote} to VP {self.vp}"
        hopstrs = [f"  {str(h)}" for h in self.orig_hops]
        return "\n".join([header] + hopstrs)

    def contains_interdomain_assume_symmetry(self):
        for i, hop in enumerate(self.orig_hops[:-1]):
            nexthop = self.orig_hops[i + 1]
            if nexthop.hoptype != RevTrHopType.DST_SYM_REV_SEGMENT:
                continue
            if hop.asn != nexthop.asn:
                return True  # Could return i
        return False

    def remove_as_loop_from_revtr_path(self):
        tr_between_index = [
            i
            for i, hop in enumerate(self.orig_hops)
            if hop.hoptype == RevTrHopType.TR_TO_SRC_REV_SEGMENT_BETWEEN
        ]
        if not tr_between_index:
            # Nothing to do
            return self.orig_hops

        first_idx = tr_between_index[0]
        before_idx = first_idx - 1
        before_asn = self.orig_hops[before_idx].asn
        if before_asn is None:
            # Don't know previous ASN, give up
            return self.orig_hops

        loop_indexes = [
            i
            for i, hop in enumerate(self.orig_hops)
            if i > before_idx and hop.asn == before_asn
        ]
        if not loop_indexes:
            # No loop
            return self.orig_hops

        loop_index = loop_indexes[0]
        hops = self.orig_hops[:first_idx]
        hops.extend(self.orig_hops[loop_index:])
        assert hops[first_idx] == self.orig_hops[loop_index]
        assert hops[before_idx].asn == hops[first_idx].asn
        return hops
