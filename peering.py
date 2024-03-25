#!/usr/bin/env python3

import argparse
import dataclasses
import ipaddress
import json
import logging
import os
import pathlib
import subprocess
import sys
from typing import Optional

import dataclasses_json
import jinja2
import jsonschema
import requests


DEFAULT_BIRD_CFG_DIR = pathlib.Path("configs/bird/")
DEFAULT_BIRD4_SOCK_PATH = pathlib.Path("var/bird.ctl")
DEFAULT_BIRD6_SOCK_PATH = pathlib.Path("var/bird6.ctl")
DEFAULT_ANNOUNCEMENT_SCHEMA = pathlib.Path("configs/announcement_schema.json")


IPNetwork = ipaddress.IPv4Network  # | ipaddress.IPv6Network
MuxName = str
# MuxName should be upgraded to a enum.StrEnum when Bookworm and Ubuntu
# 24.04LTS come out with Python 3.11

MUXES = [
    "amsterdam01",
    "clemson01",
    # "gatech01",
    "grnet01",
    "isi01",
    "neu01",
    "saopaulo01",
    "seattle01",
    "ufmg01",
    "utah01",
    "uw01",
    "wisc01",
    "vtramsterdam",
    "vtratlanta",
    "vtrbangalore",
    "vtrchicago",
    "vtrdallas",
    "vtrdelhi",
    "vtrfrankfurt",
    "vtrhonolulu",
    "vtrjohannesburg",
    "vtrlondon",
    "vtrlosangelas",
    "vtrmadrid",
    "vtrmanchester",
    "vtrmelbourne",
    "vtrmexico",
    "vtrmiami",
    "vtrmumbai",
    "vtrnewyork",
    "vtrosaka",
    "vtrparis",
    "vtrsantiago",
    "vtrsaopaulo",
    "vtrseattle",
    "vtrseoul",
    "vtrsilicon",
    "vtrsingapore",
    "vtrstockholm",
    "vtrsydney",
    "vtrtelaviv",
    "vtrtokyo",
    "vtrtoronto",
    "vtrwarsaw",
]


@dataclasses_json.dataclass_json
@dataclasses.dataclass
class Announcement:
    muxes: list[MuxName]
    peer_ids: list[int]
    communities: list[tuple[int, int]]
    prepend: list[int]


@dataclasses_json.dataclass_json
@dataclasses.dataclass
class Update:
    withdraw: list[MuxName]
    announce: list[Announcement]


@dataclasses_json.dataclass_json
@dataclasses.dataclass
class UpdateSet:
    prefix2update: dict[str, Update]


class Vultr:
    @staticmethod
    def communities_do_not_announce(upstreams: list[int]) -> list[tuple[int, int]]:
        return [(64600, asn) for asn in upstreams]

    @staticmethod
    def communities_announce_to_upstreams(upstreams: list[int]) -> list[tuple[int, int]]:
        return [(20473, 6000)] + [(64699, asn) for asn in upstreams]


class AnnouncementController:
    def __init__(
        self,
        bird_cfg_dir: pathlib.Path = DEFAULT_BIRD_CFG_DIR,
        bird4_sock: pathlib.Path = DEFAULT_BIRD4_SOCK_PATH,
        schema_file: pathlib.Path = DEFAULT_ANNOUNCEMENT_SCHEMA,
    ) -> None:
        with open(schema_file, encoding="utf8") as fd:
            self.schema = json.load(fd)
        self.bird_cfg_dir = bird_cfg_dir
        self.bird_sock = bird4_sock
        self.config_template = self.__load_config_template()
        self.__create_routes()

    def __load_config_template(self) -> jinja2.Template:
        path = os.path.join(self.bird_cfg_dir, "templates")
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(path))
        return env.get_template("export_mux_pfx.jinja2")

    def __config_file(self, prefix: str, mux: MuxName) -> pathlib.Path:
        assert ipaddress.ip_network(prefix) is not None
        prefix = prefix.replace("/", "-")
        prefix = prefix.replace(":", "i")  # removing colon from v6 prefixes
        fn = f"export_{mux}_{prefix}.conf"
        return self.bird_cfg_dir / "prefix-filters" / fn

    def __create_routes(self) -> None:
        path = os.path.join(self.bird_cfg_dir, "route-announcements")
        os.makedirs(path, exist_ok=True)
        for pfx in self.schema["definitions"]["allocatedPrefix"]["enum"]:
            fpath = os.path.join(path, pfx.replace("/", "-"))
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

    def withdraw(self, prefix: str, mux: Optional[MuxName] = None) -> None:
        if mux is None:
            for emux in MUXES:
                self.withdraw(prefix, emux)
            return
        try:
            os.unlink(self.__config_file(prefix, mux))
        except FileNotFoundError:
            pass

    def announce(self, prefix: str, ann: Announcement) -> None:
        for mux in ann.muxes:
            with open(self.__config_file(prefix, mux), "w", encoding="utf8") as fd:
                data = self.config_template.render(prefix=prefix, spec=ann.to_dict())
                fd.write(data)

    def reload_config(self) -> None:
        cmd = f"birdc -s {self.bird_sock}"
        proc = subprocess.Popen(
            cmd.split(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _stdout, _stderr = proc.communicate(b"configure\n")
        r = proc.wait()
        if r != 0:
            logging.warning("BIRD reconfigure exited with status %d", r)
            logging.warning("%s", _stdout)
            logging.warning("%s", _stderr)


class ExperimentController:
    def __init__(
        self, url, token, refresh=None, schema_fn="configs/experiment_schema.json"
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
        )

        resp.raise_for_status()
        return resp.json()

    def deploy(self, experiment):
        self.validate(experiment)
        try:
            uri = f"{self.url}/api/"
            response = self.post_request(experiment, uri)
            return response
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

    # "A refresh token is a special token that is used to obtain additional access tokens.
    # This allows you to have short-lived access tokens without having to collect credentials
    # every time one expires."
    # https://developer.okta.com/docs/guides/refresh-tokens/main/

    def refresh_token(self):
        uri = f"{self.url}/token/refresh/"
        data = {"refresh": self.refresh}
        response = self.post_request(data, uri)
        self.token = response["access"]
        return response


def create_parser():
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


def main():
    parser = create_parser()
    args = parser.parse_args()

    if args.announcement:
        with open(args.announcement, "r", encoding="utf8") as announcement_json_fd:
            announcement = json.load(announcement_json_fd)
        bird_cfg_dir = pathlib.Path("configs/bird")
        bird_sock = pathlib.Path("var/bird.ctl")
        schema_fn = pathlib.Path("configs/announcement_schema.json")

        ctrl = AnnouncementController(bird_cfg_dir, bird_sock, schema_fn)
        ctrl.deploy(announcement)
    elif args.experiment and args.url:
        token_fn = "certs/token.json"
        schema_fn = "configs/experiment_schema.json"
        with open(args.experiment, "r", encoding="utf8") as experiment_json_fd:
            experiment = json.load(experiment_json_fd)
        with open(token_fn, "r", encoding="utf8") as token_json_fd:
            token = json.load(token_json_fd)

        ctrl = ExperimentController(
            url=args.url, token=token["access"], schema_fn=schema_fn
        )
        response = ctrl.deploy(experiment)
        print(response)
    elif args.experiment and not args.url:
        parser.error("Note: --url is required when --experiment is set")


if __name__ == "__main__":
    sys.exit(main())
