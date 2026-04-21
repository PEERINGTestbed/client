# py-peering

PEERING Python Library and Latency Tooling

## Testing

This project uses `pytest` for testing, managed via `uv`.

To run the unit-like tests locally, execute the following from the `py-peering` directory:

```bash
uv run pytest tests/
```

On Linux, the test runner always re-execs itself inside an isolated user+network namespace via `unshare --user --map-root-user --net`, brings up `lo` there, and leaves the host network namespace unchanged.

## measure-latency

Latency-measurement tooling for [PEERING](https://peering.ee.columbia.edu/) that uses [`scamper`](https://www.caida.org/tools/measurement/scamper/) to probe target IP addresses.  We run two `scamper` instances: one probes the target IPs at the specified rates to collect end-to-end latencies, while another instance probes the PEERING OpenVPN gateway to allow us to subtract the tunnel latency from the end-to-end latency.

We can call the code as a standalone program on the CLI.  It also operates as a library: the `round_callback` function can be used with PEERING's `Sequencer` class for integration into multi-round BGP experiments.

### Execution

Run the CLI directly to measure latency for a single prefix through a single mux:

```bash
uv run python latency.py \
  --prefix 184.164.224.0/24 \
  --mux amsterdam01 \
  --hitlist targets.txt \
  --pps 200 \
  --outdir output/
```

### Sequencer integration

The `round_callback` function is designed to be passed to `Sequencer.run()` as a `RoundCallback`. It automatically discovers all eligible prefixes from the current round's BGP updates, distributes the packet-rate budget across them, and launches parallel scamper instances via a `ThreadPoolExecutor`.

### Assumptions

1. PEERING repository layout: this package lives at `<repo-root>/utils/py-peering/`, the latency CLI module lives under `src/peering/`, and the PEERING repository root is four parent directories up from `latency.py`.
2. OpenVPN configurations exist at `<repo-root>/configs/openvpn/<mux>.conf`. Each config file contains a `dev tap<N>` line; the tap number `<N>` serves as the mux ID for computing gateway IP addresses.
3. Sequencer mode prerequisites: when using `round_callback`, the `DataPlane` class (via `pyroute2`) manages Linux policy-routing rules.  It assumes an already-configured PEERING node with running OpenVPN tunnels and BIRD daemons.

### Output

For each prefix/mux pair, two files are produced in the output directory:

- `pfx<pfxid>-<mux>-gw.warts.xz`: warts-format probes to the OpenVPN gateway.
- `pfx<pfxid>-<mux>-targets.warts.xz`: warts-format probes to the target list.

## TO-DO

- [] Drop `pyroute2` and instead just call `ip -j`
- [] Modularize `__init__.py`; plan exists in ./refs/package-migration-plan.md
