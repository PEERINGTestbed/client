#!/usr/bin/env python3
"""Generate docker-compose.yml from templates and config/prefixes.txt.

Reads the compose template and expands, per IPv4 prefix in prefixes.txt:

* one full backend network definition (templates/backend.template.yml)
* one peering-service attachment to that network
  (templates/peering-backend-attach.template.yml)
* one revtrvp service attached only to that backend
  (templates/revtrvp.template.yml)

Placeholders in templates/backend.template.yml:
  __NETWORK_NAME__   -> unique Compose network key starting with ``backend-``
  __BRIDGE_NAME__    -> unique host bridge name (<=15 chars; Docker IFNAMSIZ)
  __PREFIX__         -> the prefix as written (e.g. 184.164.231.0/24)
  __PREFIX_GATEWAY__ -> first three octets + .253 (e.g. 184.164.231.253)

Placeholders in templates/peering-backend-attach.template.yml:
  __NETWORK_NAME__      -> same Compose network key as the backend network
  __PREFIX_PEERING_IP__ -> first three octets + .254 (peering's address on
                          that backend, e.g. 184.164.231.254)

Placeholders in templates/revtrvp.template.yml:
  __SERVICE_NAME__      -> unique Compose service key starting with ``revtrvp-``
  __NETWORK_NAME__      -> the single backend network for this VP's prefix
  __PREFIX__            -> the prefix as written
  __PREFIX_PEERING_IP__ -> peering's .254 address (used as REVTR_GATEWAY)
  __PREFIX_REVTRVP_IP__ -> first three octets + .1 (this VP's address)

Markers in templates/docker-compose.template.yml:
  __BACKEND_NETS__           -> under top-level ``networks:``
  __PEERING_BACKEND_NETS__   -> under ``services.peering.networks``
  __REVTRVP_SERVICES__       -> under top-level ``services:`` (after peering)
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


# Markers in the compose template where rendered blocks are inserted.
BACKEND_NETS_MARKER = "__BACKEND_NETS__"
PEERING_BACKEND_NETS_MARKER = "__PEERING_BACKEND_NETS__"
REVTRVP_SERVICES_MARKER = "__REVTRVP_SERVICES__"

# Placeholders shared / used across the per-prefix templates.
SERVICE_NAME_PLACEHOLDER = "__SERVICE_NAME__"
NETWORK_NAME_PLACEHOLDER = "__NETWORK_NAME__"
BRIDGE_NAME_PLACEHOLDER = "__BRIDGE_NAME__"
PREFIX_PLACEHOLDER = "__PREFIX__"
PREFIX_GATEWAY_PLACEHOLDER = "__PREFIX_GATEWAY__"
PREFIX_PEERING_IP_PLACEHOLDER = "__PREFIX_PEERING_IP__"
PREFIX_REVTRVP_IP_PLACEHOLDER = "__PREFIX_REVTRVP_IP__"

# Compose key prefixes for generated per-prefix resources.
NETWORK_NAME_PREFIX = "backend-"
SERVICE_NAME_PREFIX = "revtrvp-"

# Linux interface name limit (IFNAMSIZ); Docker rejects longer bridge names.
MAX_BRIDGE_NAME_LEN = 15

# Well-known host addresses within each /24 PEERING prefix.
HOST_SIDE_GATEWAY_OCTET = 253  # parked IPAM/host-bridge gateway
PEERING_CONTAINER_OCTET = 254  # peering service address on each backend
REVTRVP_CONTAINER_OCTET = 1  # revtrvp service address on its backend


def prefix_host(prefix: str, last_octet: int) -> str:
    """Build ``a.b.c.<last_octet>`` from an IPv4 prefix like ``a.b.c.0/24``."""
    # Split on '.' so "184.164.231.0/24" yields ["184", "164", "231", "0/24"].
    octets = prefix.split(".")
    if len(octets) < 3:
        raise ValueError(f"prefix must have at least three octets: {prefix!r}")
    return f"{octets[0]}.{octets[1]}.{octets[2]}.{last_octet}"


def prefix_gateway(prefix: str) -> str:
    """Host-side bridge gateway IP (.253) for ``prefix``."""
    return prefix_host(prefix, HOST_SIDE_GATEWAY_OCTET)


def prefix_peering_ip(prefix: str) -> str:
    """Peering container address (.254) on the backend for ``prefix``."""
    return prefix_host(prefix, PEERING_CONTAINER_OCTET)


def prefix_revtrvp_ip(prefix: str) -> str:
    """Revtrvp container address (.1) on the backend for ``prefix``."""
    return prefix_host(prefix, REVTRVP_CONTAINER_OCTET)


def sanitize_prefix_for_name(prefix: str) -> str:
    """Turn ``184.164.231.0/24`` into a Compose-safe token ``184-164-231-0-24``."""
    return prefix.replace(".", "-").replace("/", "-")


def network_name_for_prefix(prefix: str) -> str:
    """Build a unique Compose network key for ``prefix``."""
    return f"{NETWORK_NAME_PREFIX}{sanitize_prefix_for_name(prefix)}"


def service_name_for_prefix(prefix: str) -> str:
    """Build a unique Compose service key for the revtrvp of ``prefix``."""
    return f"{SERVICE_NAME_PREFIX}{sanitize_prefix_for_name(prefix)}"


def bridge_name_for_prefix(prefix: str) -> str:
    """Build a unique host bridge name for ``prefix`` within IFNAMSIZ.

    Prefer a short readable form ``bk`` + network octets without dots. If that
    would exceed Docker's 15-character limit, fall back to a stable short hash.
    """
    # "184.164.231.0/24" -> network address octets before the mask.
    network_addr = prefix.split("/", 1)[0]
    compact = "bk" + network_addr.replace(".", "")
    if len(compact) <= MAX_BRIDGE_NAME_LEN:
        return compact
    # Stable, collision-resistant short name when the compact form is too long.
    digest = hashlib.sha1(prefix.encode("utf-8")).hexdigest()[
        : MAX_BRIDGE_NAME_LEN - 2
    ]
    return f"bk{digest}"


def load_prefixes(prefixes_path: Path) -> list[str]:
    """Return non-empty, non-comment lines from the prefixes file."""
    prefixes: list[str] = []
    for line in prefixes_path.read_text(encoding="utf-8").splitlines():
        # Strip inline whitespace; ignore blanks and '#' comment lines.
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        prefixes.append(stripped)
    return prefixes


def render_template_per_prefix(prefixes: list[str], template: str) -> str:
    """Render ``template`` once per prefix, substituting all known placeholders.

    Placeholders absent from a given template are left alone by ``str.replace``
    only when they do not appear; we still compute every substitution so one
    helper can drive backend, peering-attach, and revtrvp templates.
    """
    blocks: list[str] = []
    for prefix in prefixes:
        rendered = (
            template.replace(SERVICE_NAME_PLACEHOLDER, service_name_for_prefix(prefix))
            .replace(NETWORK_NAME_PLACEHOLDER, network_name_for_prefix(prefix))
            .replace(BRIDGE_NAME_PLACEHOLDER, bridge_name_for_prefix(prefix))
            .replace(PREFIX_PLACEHOLDER, prefix)
            .replace(PREFIX_GATEWAY_PLACEHOLDER, prefix_gateway(prefix))
            .replace(PREFIX_PEERING_IP_PLACEHOLDER, prefix_peering_ip(prefix))
            .replace(PREFIX_REVTRVP_IP_PLACEHOLDER, prefix_revtrvp_ip(prefix))
        )
        # Normalize trailing newlines so adjacent blocks concatenate cleanly.
        blocks.append(rendered.rstrip("\n"))
    return "\n".join(blocks)


def generate_compose(
    compose_template: str,
    backend_template: str,
    peering_attach_template: str,
    revtrvp_template: str,
    prefixes: list[str],
) -> str:
    """Substitute rendered per-prefix blocks for all compose template markers."""
    markers = (
        BACKEND_NETS_MARKER,
        PEERING_BACKEND_NETS_MARKER,
        REVTRVP_SERVICES_MARKER,
    )
    for marker in markers:
        if marker not in compose_template:
            raise ValueError(f"compose template is missing {marker!r} marker")

    return (
        compose_template.replace(
            BACKEND_NETS_MARKER,
            render_template_per_prefix(prefixes, backend_template),
        )
        .replace(
            PEERING_BACKEND_NETS_MARKER,
            render_template_per_prefix(prefixes, peering_attach_template),
        )
        .replace(
            REVTRVP_SERVICES_MARKER,
            render_template_per_prefix(prefixes, revtrvp_template),
        )
    )


def default_repo_root() -> Path:
    """Resolve the repository root as the parent of this script's directory."""
    return Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    """CLI for regenerating docker-compose.yml from repo-relative defaults."""
    root = default_repo_root()
    parser = argparse.ArgumentParser(
        description=(
            "Generate docker-compose.yml from templates, expanding one backend "
            "network, peering attachment, and revtrvp service per prefix in "
            "config/prefixes.txt."
        )
    )
    parser.add_argument(
        "--compose-template",
        type=Path,
        default=root / "templates" / "docker-compose.template.yml",
        help="Path to docker-compose.template.yml",
    )
    parser.add_argument(
        "--backend-template",
        type=Path,
        default=root / "templates" / "backend.template.yml",
        help="Path to backend.template.yml",
    )
    parser.add_argument(
        "--peering-attach-template",
        type=Path,
        default=root / "templates" / "peering-backend-attach.template.yml",
        help="Path to peering-backend-attach.template.yml",
    )
    parser.add_argument(
        "--revtrvp-template",
        type=Path,
        default=root / "templates" / "revtrvp.template.yml",
        help="Path to revtrvp.template.yml",
    )
    parser.add_argument(
        "--prefixes",
        type=Path,
        default=root / "config" / "prefixes.txt",
        help="Path to prefixes.txt (one IPv4 prefix per line)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "docker-compose.yml",
        help="Destination path for the generated compose file",
    )
    return parser.parse_args()


def main() -> None:
    """Load templates + prefixes, render, and write docker-compose.yml."""
    args = parse_args()

    compose_template = args.compose_template.read_text(encoding="utf-8")
    backend_template = args.backend_template.read_text(encoding="utf-8")
    peering_attach_template = args.peering_attach_template.read_text(
        encoding="utf-8"
    )
    revtrvp_template = args.revtrvp_template.read_text(encoding="utf-8")
    prefixes = load_prefixes(args.prefixes)
    if not prefixes:
        raise SystemExit(f"no prefixes found in {args.prefixes}")

    rendered = generate_compose(
        compose_template,
        backend_template,
        peering_attach_template,
        revtrvp_template,
        prefixes,
    )
    # Ensure the output file ends with a single trailing newline.
    args.output.write_text(rendered.rstrip("\n") + "\n", encoding="utf-8")
    print(
        f"wrote {args.output} "
        f"({len(prefixes)} backend network(s), {len(prefixes)} revtrvp service(s))"
    )


if __name__ == "__main__":
    main()
