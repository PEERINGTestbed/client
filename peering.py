#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys

import jinja2
import jsonschema
import requests


class AnnouncementController:
    def __init__(
        self, bird_cfg_dir, bird_sock, schema_fn="configs/announcement_schema.json"
    ):
        with open(schema_fn, encoding="utf8") as fd:
            self.schema = json.load(fd)
        self.bird_cfg_dir = str(bird_cfg_dir)
        self.bird_sock = str(bird_sock)
        self.config_template = self.__load_config_template()
        self.__create_routes()

    def __load_config_template(self):
        path = os.path.join(self.bird_cfg_dir, "templates")
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(path))
        return env.get_template("export_mux_pfx.jinja2")

    def __config_file(self, prefix, mux):
        pfxfstr = prefix.replace("/", "-")
        fn = f"export_{mux}_{pfxfstr}.conf"
        return os.path.join(self.bird_cfg_dir, "prefix-filters", fn)

    def __create_routes(self):
        path = os.path.join(self.bird_cfg_dir, "route-announcements")
        os.makedirs(path, exist_ok=True)
        for pfx in self.schema["definitions"]["allocatedPrefix"]["enum"]:
            fpath = os.path.join(path, pfx.replace("/", "-"))
            fd = open(fpath, "w", encoding="utf8")
            fd.write(f"route {pfx} unreachable;\n")
            fd.close()

    def validate(self, announcement):
        jsonschema.validate(announcement, self.schema)

    def deploy(self, announcement):
        self.validate(announcement)
        self.update_config(announcement)
        self.reload_config()

    def update_config(self, announcement):
        self.validate(announcement)
        for prefix, announce in announcement.items():
            for mux in announce.get("withdraw", list()):
                self.withdraw(prefix, mux)
            for spec in announce.get("announce", list()):
                self.announce(prefix, spec)

    def withdraw(self, prefix, mux):
        try:
            os.unlink(self.__config_file(prefix, mux))
        except FileNotFoundError:
            pass

    def announce(self, prefix, spec):
        for mux in spec["muxes"]:
            with open(self.__config_file(prefix, mux), "w", encoding="utf8") as fd:
                fd.write(self.config_template.render(prefix=prefix, spec=spec))

    def reload_config(self):
        cmd = f"birdc -s {self.bird_sock}"
        proc = subprocess.Popen(
            cmd.split(),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _stdout, _stderr = proc.communicate(b"configure\n")


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
        bird_cfg_dir = "configs/bird"
        bird_sock = "var/bird.ctl"
        schema_fn = "configs/announcement_schema.json"

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
