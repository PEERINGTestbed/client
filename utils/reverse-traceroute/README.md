# Running Reverse Traceroute towards PEERING

## Create Docker bridges and configure source routing

### Docker bridges

The Docker container for the Reverse Traceroute (RevTr) VP ([code](https://github.com/NEU-SNS/revtrvp.git)) assumes a single interface.  To allow the container to communicate with multiple PEERING upstreams, we create a Docker bridge and attach the container to the bridge.  Packets can then flow through the brigde between the RevTr Docker container and PEERING OpenvVPN devices.

We need Docker to *not* NAT the addresses of containers (as they will use public addresses from PEERING).  You can do this by adding `"iptables": false` to your `/etc/docker/daemon.json` file.  However, you may also need to get rid of all `iptables` rules installed by Docker, enabling IP forwarding, and allowing packets on the forwarding chain:

```bash
# Flushing iptables rules may break networking to your machine, be careful.
iptables -t nat -F
iptables -F
iptables -P FORWARD ACCEPT
sysctl -w net.ipv4.ip_forward=1
```

You can use the `./peering app -b` command to create a Docker bridge for the container that bypasses NAT.  We assume one VP per PEERING prefix; if this matches your deployment, you can configure one bridge for each prefix.  We configure Docker to hand out addresses in the PEERING prefix to be used for the VP.

> `./peering app` is somewhat fragile.  For example, it may break if bridges already exist.  Resetting the network namespace to a "clean" state is recommended.

### Configure source routing

We also need to configure the egress route that packets from the Reverse Traceroute container will use to reach the Internet.  By default all egress packets from the RevTr container will be routed according to table `20000`, which is automatically populated by the PEERING client with routes received from all upstreams.  The egress routes are configured by creating two Linux `ip rule` entries to source-route packets arriving from the VP's prefix or the VPs bridge to table `20000`.

You can override the default behavior by specifying a specific router to be used as egress using the `-u` parameter when creating the bridge (with `./peering app -b`).  In this case we create a specific routing table for the VP's prefix.  The table number is given by `10000` plus the `ID` passed as a parameter to the `./peering app -b` command.  The default route uses the egress router's IP address on the OpenVPN tunnel as the gateway.

> For example, `uw01` has `id` 10, so uses `tap10` as the OpenVPN tunnel and `100.(64+10).128.1` as the default gateway.  More information on the PEERING data plane configuration can be found in the [Wiki](https://github.com/PEERINGTestbed/client/wiki/Client-data-plane).

> In the `networking-setup.sh` script, the `prefix2mux` dictionary (or "associative array" in Bash) contains the mapping of prefix to their egress router.  The `setup_docker_bridges` function creates one bridges for each configured prefix.  One RevTr VP can then be started on each bridge.  The `teardown_docker_bridges` can be used to remove the network configuration.

## Establish OpenVPN tunnels and BGP sessions

Establish OpenVPN tunnels and BGP sessions to the routers used in the experiment.  You can manage OpenVPN tunnels and BGP sessions independently of Reverse Traceroute VPs and VP Docker containers.  Care should just be taken so that the PEERING prefix in use by a VP is announced to the egress router if `-u` was used when creating the application (`./peering app -b`).  (To be more specific, the RevTr VP may still work if its prefix is not announced to the chosen egress router, but [Reverse Path Filtering][reverse-path-filtering] may reduce reachability.)

[reverse-path-filtering]: https://tldp.org/HOWTO/Adv-Routing-HOWTO/lartc.kernel.rpf.html

*Important:* Consider changing the import filter on the BGP session configuration template inside `client/configs/bird/bird.conf` to `none` (search for `template bgp peering`) if you do not care about BGP routes and your machine has limited RAM.

If there are stray OpenVPN daemon instances on the machine, they may prevent correct management of the tunnel devices.  Consider killing all existing OpenVPN instances before creating the tunnels and attempting to establish BGP sessions with PEERING routers.

> In the `networking-setup.sh` script, the `mux2id` The `establish_bgp_sessions` and `teardown_bgp_sessions` in can be used to open and close OpenVPN tunnels and BGP sessions.

## Testing the data plane

After you have announced the prefixes that will be used by the vantage points, test data plane connectivity by issuing pings from within containers using the Docker bridges.  This can be accomplished by running a `busybox` (or some other small container) attached to the Docker bridge.

> The `test_data_plane` function inside `networking-setup.sh` implements basic tests.  We strongly recommend you check they succeed before running the RevTr VP.

Initial ideas in case troubleshooting is needed:

1. Check that the IP address is configured correctly inside the container.
2. Check that the container has a default route to the bridge's highest address.
3. Check that source-routing rules exist on the host to direct packets arriving from the VP into the egress routing table (either `20000` or `10000+id`).
4. Run `tcpdump` on different interfaces to check how far packets go.
5. Check that the Docker firewall/NAT is disabled.

## Running the Reverse Traceroute VP

The Reverse Traceroute VP is built from the public [revtrvp](https://github.com/NEU-SNS/revtrvp.git) repository.  Edit `plvp.config` to point to the interface inside the container, which Docker calls `eth0` by default.  Adjust the maximum probing rate, if desired.  If running on PEERING keep the maximum probing rate below the value specified in your proposal.  Build the container:

```bash
cd /path/to/revtrvp/repo
docker build -t revtrvp .
```

Then run the container.  The `revtr-containers` script can be used to start and terminate containers.  When the VP connects to the RevTr controller, the controller will test whether the VP can receive spoofed RR probes and will send an e-mail with the test results.

## Dependencies

```bash
apt install bird openvpn socat ipcalc psmisc
systemctl stop openvpn bird bird6
systemctl disable openvpn bird bird6
pip3 install pexpect
```
