# Reverse Traceroute VP behind PEERING (Docker Compose)

This repo runs a [Reverse Traceroute](https://github.com/NEU-SNS/revtrvp) (RevTr)
vantage point (`revtrvp`) behind the [PEERING](https://peering.ee.columbia.edu/)
testbed using Docker Compose. A `peering` container acts as the gateway/router:
Makefile targets establish OpenVPN tunnels and BGP, and source-route each VP's
traffic out the hardcoded data-plane egress mux, so RevTr probes and control
connections originate from our allocated PEERING prefix(es).

- **Prefixes:** listed in `config/prefixes.txt` (one backend network + `revtrvp-*`
  per prefix)
- **Data-plane egress mux:** `ufmg01` (tunnel device `tap7`, policy table `10007`)
- **Probing rate:** 100 pps

## Topology

```
                         host internet (NAT)
                                 │
                    afrontend (NAT bridge, 172.16.50.0/24)
                                 │  (peering's control plane:
                                 │   OpenVPN->muxes, DNS, git)
                          ┌──────┴───────┐
                          │   peering    │  afrontend: 172.16.50.x (default route)
                          │  container   │  tap7: OpenVPN tunnel to ufmg01 (egress)
                          │  (BIRD+OVPN) │  backend-*: .254 (gateway per prefix)
                          └──────┬───────┘
                    backend-* (one no-NAT bridge per prefix)
                          ┌──────┴───────┐
                          │  revtrvp-*   │  eth0: .1, default route -> peering .254
                          │  (per prefix)│
                          └──────────────┘
```

Networks:

- **`afrontend`** (NAT enabled): carries the `peering` container's *own* control
  traffic (OpenVPN to muxes, DNS, git). Masqueraded out the host normally.
- **`backend-*`** (NAT disabled, one per prefix): carries that prefix between
  `peering` (`.254`) and the matching `revtrvp-*` (`.1`). Masquerade is off so
  the VP's source IP is preserved. IPAM/host-side gateway is parked at `.253`;
  the real gateway each VP routes through is `peering` at `.254`.

All `revtrvp-*` forwarded traffic egresses via **`ufmg01`** (policy routing:
`iif <backend> → table 10007 → tap7`). Other mux tunnels (e.g. `vtrtoronto`) are
optional and used for BGP reachability/announcements, not data-plane egress.

## Prerequisites

- Docker + Docker Compose.
- PEERING client certificates in `certs/` (`ca.crt`, `client.crt`, `client.key`).
- Prefixes allocated to you listed in `config/prefixes.txt`.
- Passwordless (or interactive) `sudo` for `sysctl`: `make up` disables
  `net.bridge.bridge-nf-call-iptables` on the host as a prerequisite step (see
  Troubleshooting for why) and will prompt for a password if needed.

## Files of interest

- `templates/docker-compose.template.yml` / `templates/backend.template.yml` /
  `templates/peering-backend-attach.template.yml` /
  `templates/revtrvp.template.yml` — sources for the generated compose file;
  one `backend-*` network, peering attachment, and `revtrvp-*` service is
  expanded per prefix in `config/prefixes.txt`.
- `scripts/setup_docker.py` — renders `docker-compose.yml` from those templates
  (`make setup-docker`).
- `docker-compose.yml` — generated stack (frontend + one backend network and
  revtrvp per prefix).
- `scripts/peering-gateway-entrypoint.sh` — pins the default route to
  `afrontend`, enables forwarding, stays alive (no OpenVPN/BGP).
- `scripts/peering-openvpn-up.sh` — brings up a mux tunnel; for `ufmg01`, also
  installs backend→egress policy routes (`make openvpn` / `make up`).
- `scripts/revtrvp-entrypoint.sh` — points each VP's default route at the
  gateway, then starts the VP.
- `config/prefixes.txt` / `config/prefixes6.txt` — PEERING prefix databases
  (mounted into the client; also drive backend networks via `setup-docker`).
- `config/plvp.config` — RevTr VP config (interface `eth0`, scamper rate 100).
- `client/` and `revtrvp/` — git submodules for the PEERING client and the
  RevTr VP.

## Usage

Regenerate `docker-compose.yml` after changing prefixes or templates:

```bash
make setup-docker
```

Build the images (first time; note `revtrvp` compiles scamper and can take a
few minutes):

```bash
make build
```

Start the stack. `make up` disables `net.bridge.bridge-nf-call-iptables`, starts
Compose detached, brings up the **`ufmg01`** egress tunnel and backend policy
routes, then follows logs. Ctrl-C stops log follow only; use `make down` to
tear down. BGP and prefix announcement are separate manual steps.

```bash
make up
# optional extra BGP muxes (tunnel only; egress stays ufmg01):
# make openvpn mux=vtrtoronto
make bgp-start
```

Announce a prefix over BGP (live action) and wait for convergence (~180s):

```bash
make announce
```

Check status and the data plane:

```bash
make bgp-status      # sessions for connected muxes; Established after converge
make dataplane-test  # ping 1.1.1.1 from inside a revtrvp container
make logs            # revtrvp should connect to plcontroller.revtr.ccs.neu.edu
```

Tear down:

```bash
make withdraw   # stop announcing the prefix
make down       # stop and remove containers/networks
```

> Each `revtrvp-*` uses `restart: unless-stopped`. Before the prefix is
> announced it cannot resolve/reach the controller and will restart-loop; this
> is expected and it will connect once `make announce` has converged.

## Verification / troubleshooting

Inspect the egress tunnel and routing:

```bash
docker compose -f docker-compose.yml exec peering ip -4 addr show tap7
docker compose -f docker-compose.yml exec peering ip rule show
docker compose -f docker-compose.yml exec peering ip route show table 10007
```

Expected: `tap7` has an address in `100.71.128.0/24`; an `iif <backend-iface>`
rule points at table `10007` for each backend; table `10007` has
`default via 100.71.128.1 dev tap7`.

Inspect a VP (service name is prefix-derived, e.g. `revtrvp-184-164-231-0-24`):

```bash
docker compose -f docker-compose.yml exec revtrvp-184-164-231-0-24 ip route
# default via 184.164.231.254
```

Confirm probes carry the prefix source IP (after announce):

```bash
docker compose -f docker-compose.yml exec peering tcpdump -ni tap7
```

Common issues:

1. Prefix not announced yet → `revtrvp-*` restart-loops on DNS failure. Run
   `make announce` and wait for convergence.
2. `announce` rejects the prefix → ensure it is present in `config/prefixes.txt`.
3. No egress after announce → check `rp_filter` is relaxed and source-routing is
   installed (commands above); check `make bgp-status` shows `Established`.
   Ensure `make up` (or `make openvpn mux=ufmg01`) ran successfully.
4. **Traceroute/ping from `revtrvp` reaches the `peering` gateway (`.254`) but
   never progresses further, even though the prefix is announced, BGP shows
   `Established`, and #3 above looks fine.** This is caused by
   `net.bridge.bridge-nf-call-iptables=1` on the host (commonly enabled by
   `libvirt` for its own bridges): it silently drops reply traffic that
   `peering` *relays* back to `revtrvp` across a backend Docker bridge,
   even though direct `peering`<->`revtrvp` traffic on that same bridge works
   fine. Confirmed via packet capture in a real debugging session on this
   exact stack: replies correctly arrived back through the tunnel and were
   re-transmitted by `peering` onto the bridge with correct source/destination
   MACs, yet never arrived at `revtrvp`'s interface. Scoped mitigations (a
   `DOCKER-USER` iptables accept rule, `rp_filter=0`, `send_redirects=0`) did
   **not** fix it in isolation — only disabling
   `net.bridge.bridge-nf-call-iptables` globally did. `make up` now runs
   `sudo sysctl -w net.bridge.bridge-nf-call-iptables=0` before starting
   compose specifically to avoid this. If you bypassed `make up` (e.g. ran
   `docker compose up` directly) and hit this, run that command manually, or
   restart the stack via `make up`.
   - This is a **host-wide** setting (affects all Docker bridges and any
     `libvirt` VM networks on the machine, not just this project) and does
     **not** persist across reboots — `make up` re-asserts it every time
     rather than assuming it's already set.

## Configuration knobs

- **Egress mux** is hardcoded as `EGRESS_MUX=ufmg01` in the Makefile /
  `scripts/peering-openvpn-up.sh` (tap/table derived from the mux OpenVPN
  config: `tap7` → `100.71.128.1` / table `10007`).
- **Extra muxes** for BGP: `make openvpn mux=<name>` (does not change
  data-plane egress).
- **Prefixes / addressing:** edit `config/prefixes.txt` and re-run
  `make setup-docker`. Each prefix gets a `backend-*` network, peering at
  `.254`, and a `revtrvp-*` at `.1` with `REVTR_GATEWAY=.254`.
