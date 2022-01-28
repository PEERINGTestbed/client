# Running Reverse Traceroute towards PEERING

## Create Docker bridges

The Docker container for the revtr VP assumes a single interface. To do
this, we configure Docker to *not* NAT the addresses of containers.
Create a network for the container that bypasses NAT. We configure
Docker to hand out addresses in the PEERING prefix to be used for the
VP. This task is performed by `create_docker_bridges` function.

## Establish OpenVPN tunnels and BGP sessions

Establish OpenVPN tunnels and BGP sessions to the muxes used in the
experiment. Function `establish_bgp_sessions` helps with this. Consider
changing the import filter inside `client/configs/bird/bird.conf` to
`none` if you do not care about BGP routes and your machine has limited
RAM. This needs to run before source routing configuration below as we
want the OpenVPN tunnels established.

Note that if there are stray OpenVPN daemon instances on the server,
they may prevent correct management of the tunnel devices. Considering
killing all existing OpenVPN instances before establishing the BGP
sessions.

## Configure source routing

We also need to source-route packets from the Reverse Traceroute
container to use PEERING as an upstream. We create a specific routing
table for each mux, and add a default route pointing to the mux's IP
address on the OpenVPN tunnel.  For example, `uw01` has `id` 10, so uses
`tap10` as the OpenVPN tunnel and `100.(64+10).128.1` on its end of the
OpenVPN tunnel. Packets are routed to this specific routing table
according to the source IP assress of Docker container. We configure
this in the `setup_source_routing` function.

## Make announcements

Announce a test prefix from PEERING and wait some time for route
convergence to finish. The `announce_prefixes` calls PEERING scripts to
achieve this.

## Test data plane

Test data plane connectivity by issuing pings from within containers
using the Docker bridges. Function `run_data_plane_test` implements
basic tests. Check that the IP address is configured correctly inside
the container, that there is a default route, and that 8.8.8.8 is
reachable. It is also a good idea to run `tcpdump` to check if packets
are going in and out of tap interfaces.

## Running the Reverse Traceroute VP

The Reverse Traceroute VP is built from the [revtrvp][revtrvp-repo]
repository. Edit `plvp.config` to point to the interface inside the
container, which Docker calls `eth0` by default. Adjust the maximum
probing rate, if desired. If running on PEERING keep the maximum probing
rate below the value specified in your proposal. Build the container:

```bash
cd /path/to/revtrvp/repo
docker build -t revtrvp .
```

Then run the container. When it connects to the RevTr controller, the
controller will test whether the VP can receive spoofed RR probes and
will send an e-mail with the test results. The function `run_revtr_vps`
performs this step.

## Dependencies

```{bash}
apt install bird openvpn socat
pip3 install pexpect
```

## Configuration

We keep two configurations file around, one for testing (`-test`) and
another for executing experiments (`-prod`). Link to these files from
`client.sh` and `client.py` as needed.

## Results

Our tests on Sep. 7th, 2021 indicated the following muxes can receive RR
packets: grnet01, uw01, clemson01, neu01, gatech01, wisc01, ufmg01,
utah01, amsterdam01, seattle01.  (At the moment of writing, PNWGP is not
forwarding packets from Internet2 to the wide area Internet. We can
bypass this problem poisonin AS101.)

* Update on 2022-01-24: It seems ufmg01 cannot receive RR packets.
* Update on 2022-01-28: False alarm, it can receive RRs just fine, the
  false alarm is caused by something else, possibly delayed BGP
  convergence. utah01 is experiencing similar problems.

grnet01 gatech01 wisc01 neu01 ufmg01

## PEERING prefix allocations to restore after SIGCOMM deadline

Experiment: Comparison between Bdrmapit and classic IP-to-AS strategies
Prefix: 184.164.248.0/24

Experiment: Locating DDoS Attackers
Prefix: 184.164.250.0/24
Prefix: 184.164.251.0/24
Prefix: 184.164.252.0/24
Prefix: 184.164.253.0/24
