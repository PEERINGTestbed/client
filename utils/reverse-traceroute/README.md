# Running Reverse Traceroute towards PEERING

## Create Docker bridges and configure source routing

### Docker bridges

The Docker container for the revtr VP assumes a single interface.  To
allow the container to communicate with multiple PEERING upstreams, we
create a Docker bridge and attach the container to the bridge.  Packets
can then flow through the brigde between the RevTr Docker container and
PEERING mux OpenvVPN devices.

We configure Docker to *not* NAT the addresses of containers.  However,
you may also need to get rid of all `iptables` rules installed by
Docker.  You can do this by adding `"iptables": false` to your
`/etc/docker/daemon.json` file.

You can use the `./peering app -b` command to create a Docker bridge for
the container that bypasses NAT.  We assume one VP per PEERING prefix;
if this matches your deployment, you can configure one bridge for each
prefix.  We configure Docker to hand out addresses in the PEERING prefix
to be used for the VP.

### Configure source routing

We also need to source-route packets from the Reverse Traceroute
container to use PEERING as an upstream.  If no specific upstream mux is
specified using `-u` when creating the bridge (with `./peering app -b`),
then all packets from the RevTr container will be source-routed to table
`20000`, which is automatically populated by BIRD with routes received
from all upstreams.  Packets are routed to a prefix's specific routing
table according to the source IP address of the RevTr VP's Docker
container or its corresponding bridge.  More specifically, this source
routing is configured by creating two `ip rule`s that route all packets
arriving from the bridge or from the VP's address to table `20000`.

You can also pass in a specific upstream mux with `-u`, in which case we
create a specific routing table for that prefix (and thus the VP,
assuming one VP per prefix).  The table number is given by `10000` plus
the `ID` passed as a parameter to the `./peering app -b` command.  The
default route uses the mux's IP address on the OpenVPN tunnel as the
gateway.  For example, `uw01` has `id` 10, so uses `tap10` as the
OpenVPN tunnel and `100.(64+10).128.1` on its end of the OpenVPN tunnel.

## Establish OpenVPN tunnels and BGP sessions

Establish OpenVPN tunnels and BGP sessions to the muxes used in the
experiment.  You can manage OpenVPN tunnels and BGP sessions
independently from Reverse Traceroute VPs and VP Docker containers.
Care should just be taken so that the PEERING prefix in use by a VP is
announced to the upstream mux used by the VP.  (To be more specific, the
RevTr VP may still work if its prefix is not announced to the chosen
egress mux, but [Reverse Path Filtering][reverse-path-filtering] may
reduce reachability.)

[reverse-path-filtering]: https://tldp.org/HOWTO/Adv-Routing-HOWTO/lartc.kernel.rpf.html

Consider changing the import filter on the BGP session configuration
template inside `client/configs/bird/bird.conf` to `none` (search for
`template bgp peering`) if you do not care about BGP routes and your
machine has limited RAM.

Note that if there are stray OpenVPN daemon instances on the server,
they may prevent correct management of the tunnel devices.  Consider
killing all existing OpenVPN instances before creating the tunnels and
attempting to establish BGP sessions with PEERING muxes.

## Test data plane

After you have announced the prefixes that will be used by the vantage
points, test data plane connectivity by issuing pings from within
containers using the Docker bridges.  The functions inside
`networking-setup.sh` sequences these steps and implements basic tests.

Initial ideas in case troubleshooting is needed:

1. Check that the IP address is configured correctly inside the
   container.
2. Check that the container has a default route to the bridge's highest
   address.
3. Check that source-routing rules exist on the host to direct packets
   arriving form the VP onto an upstream routing table (either `20000`
   or `10000+id`).
4. Run `tcpdump` on different interfaces to check how far packets go.
5. Check that the Docker firewall/NAT is disabled.

## Running the Reverse Traceroute VP

The Reverse Traceroute VP is built from the [revtrvp][revtrvp-repo]
repository. Edit `plvp.config` to point to the interface inside the
container, which Docker calls `eth0` by default.  Adjust the maximum
probing rate, if desired.  If running on PEERING keep the maximum
probing rate below the value specified in your proposal. Build the
container:

```bash
cd /path/to/revtrvp/repo
docker build -t revtrvp .
```

Then run the container.  The `revtr-containers` script can be used to
this end.  When the VP connects to the RevTr controller, the controller
will test whether the VP can receive spoofed RR probes and will send an
e-mail with the test results.

## Dependencies

```{bash}
apt install bird openvpn socat ipcalc
systemctl stop openvpn bird bird6
systemctl disable openvpn bird bird6
pip3 install pexpect
```
