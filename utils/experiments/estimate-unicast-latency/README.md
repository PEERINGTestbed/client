# Unicast Latency Measurements

This experiment measures end-to-end unicast latency from each PEERING mux to a set of internet targets.  For each mux, we unicast a prefix and probe the targets via ICMP echo using [scamper](https://www.caida.org/tools/measurement/scamper/) while continuously pinging the mux.  During post-processing, one can subtract the latency to the mux from the latency measured to each target.

During probing, two scamper processes run per prefix:
* *Target pings*: pings all targets from the `.1` address of the announced prefix (up to 3 replies per target, up to 6 probes, at 600 pps per prefix).
* *Gateway pings*: continuously pings the OpenVPN gateway for that mux (60 probes at a time, looping for the duration).

The default configuration is in `defs.py`.

## Dataset Structure

```
unicast_latency_measurements/
  round0/
    timestamps.json                          # Unix timestamps for round lifecycle events
    announcements.json                       # Full BGP update details per prefix
    egresses.json                            # Prefix → egress mux mapping
    226-vtrchicago-targets.warts.xz         # Ping results to all targets (prefix 226 via vtrchicago)
    226-vtrchicago-gw.warts.xz              # Continuous gateway ping results
    226-vtrchicago-targets.log              # Scamper stderr/stdout log
    ...
  round1/
    ...
```

### File Details

* `timestamps.json` (JSON) — Epoch timestamps: round start/end, scamper start/end, withdraw start/end
* `announcements.json` (JSON) — Per-prefix BGP update: which muxes were withdrawn, which mux announced, description
* `egresses.json` (JSON) — Simple `{prefix: mux_name}` mapping for the round
* `{pfxid}-{mux}-targets.warts.xz` (Scamper warts, xz-compressed) — Ping measurements to all target IPs from this prefix via this mux
* `{pfxid}-{mux}-gw.warts.xz` (Scamper warts, xz-compressed) — Continuous ICMP echo to the OpenVPN gateway
* `{pfxid}-{mux}-targets.log` (text) — Scamper process log output
* `data/targets.txt` (text, one IP per line) — ~400k target IP addresses used for probing

The naming convention `{pfxid}-{mux}` uses the last octet of the prefix (e.g., `226` for `184.164.226.0/24`) and the mux name (e.g., `vtrchicago`).

## Reading the Data

### Scamper warts files

The `.warts.xz` files are compressed scamper output. Use the scamper tool suite to read them:

```bash
# Decompress and convert to JSON (one JSON object per line)
sc_warts2json 226-vtrchicago-targets.warts.xz 

# Convert to human-readable text
sc_warts2text 226-vtrchicago-targets.warts.xz 

# Get a summary of ping stats (probes sent, replies received)
source peering-common.sh
report_sc_ping_stats round0/
```

<!-- TODO: this above may require update after we refactor, the below too -->

### JSON metadata files

Standard JSON — load with `jq`, Python `json`, or any JSON parser:

```bash
jq '.' round0/egresses.json
jq '.' round0/timestamps.json
```

### Quick analysis with Python

```python
import json, ipaddress, subprocess

# Load round metadata
with open("round0/egresses.json") as f:
    egresses = json.load(f)
# egresses = {"184.164.226.0/24": "vtrchicago", ...}

# Extract RTTs from a warts file
import subprocess
result = subprocess.run(
    ["xzcat", "round0/226-vtrchicago-targets.warts.xz"],
    capture_output=True, text=False,
)
# Pipe into sc_warts2json or parse the binary warts format
```
