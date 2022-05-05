# Running Reverse Traceroute towards PEERING

## Create Docker bridges

The Docker container for the revtr VP assumes a single interface. To do
this, we configure Docker to *not* NAT the addresses of containers.
Create a network for the container that bypasses NAT. We configure
Docker to hand out addresses in the PEERING prefix to be used for the
VP. This task is performed by the `create_docker_bridges` function.

## Establish OpenVPN tunnels and BGP sessions

Establish OpenVPN tunnels and BGP sessions to the muxes used in the
experiment. Function `establish_bgp_sessions` helps with this. Consider
changing the import filter inside `client/configs/bird/bird.conf` to
`none` if you do not care about BGP routes and your machine has limited
RAM. This needs to run before source routing configuration below as we
want the OpenVPN tunnels established.

Note that if there are stray OpenVPN daemon instances on the server,
they may prevent correct management of the tunnel devices. Consider
killing all existing OpenVPN instances before establishing the BGP
sessions.

## Configure source routing

We also need to source-route packets from the Reverse Traceroute
container to use PEERING as an upstream. We create a specific routing
table for each prefix. The table number is given by `-200` plus the
third octet of the prefix; this assumes that we are using a prefix in
the 184.164.224.0/19 range. We add a default route pointing the prefix
to a specific mux. The default route uses the mux's IP address on the
OpenVPN tunnel as the gateway.  For example, `uw01` has `id` 10, so uses
`tap10` as the OpenVPN tunnel, `100.(64+10).128.1` on its end of the
OpenVPN tunnel, and table `60`.  Packets are routed to a prefix's
specific routing table according to the source IP address of the Docker
container. We configure this using the `scripts/source-routing` script.

## Make announcements

Announce a test prefix from PEERING and wait some time for route
convergence to finish. We call PEERING scripts to achieve this.

Note that announcements should match source routing: we recommend the
egress mux used for a given prefix is also announcing the prefix to the
Internet to avoid reverse path filtering.

## Test data plane

Test data plane connectivity by issuing pings from within containers
using the Docker bridges. The `test_data_plane` function implements
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

We keep two configuration files around, one for testing (`-test`) and
another for executing experiments (`-prod`). Link to these files from
`client.sh` and `client.py` as needed.

## Results

Our tests on Sep. 7th, 2021 indicated the following muxes can receive RR
packets: grnet01, uw01, clemson01, neu01, gatech01, wisc01, ufmg01,
utah01, amsterdam01, seattle01.  (At the moment of writing, PNWGP is not
forwarding packets from Internet2 to the wide area Internet. We can
bypass this problem poisoning AS101.)

* Update on 2022-01-24: It seems ufmg01 cannot receive RR packets.
* Update on 2022-01-28: False alarm, it can receive RRs just fine, the
  false alarm is caused by something else, possibly delayed BGP
  convergence. utah01 is experiencing similar problems.
