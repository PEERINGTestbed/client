# PEERING client controller

The PEERING client controller is a set of scripts to ease
configuration and operation of a PEERING client, able to connect to
PEERING muxes and announce PEERING prefixes.

## Recent changes

* We have recently merged the `-c` and `-C` parameters used to attach communities to announcements.  The functionality is identical to before, but the interface for specifying communities has changed.

## Installation

After cloning [this repository][1], follow the following
instructions to install software dependencies and set up your
PEERING client.

  [1]: https://github.com/TransitPortal/client

### Software dependencies

The client runs OpenVPN to connect directly to PEERING muxes and
the BIRD software router to establish BGP sessions and perform
announcements.

You must have a pre-2.0 version of Bird to use the PEERING client. You can compile Bird from source after downloading the source from <http://bird.network.cz/?download>.

You can also install these dependencies from your distro
repository; on Debian use `apt-get install openvpn bird`. However, ensure that Bird is a pre-2.0 version.

### PEERING account setup

To establish OpenVPN tunnels with PEERING muxes, you will need
PEERING-issued certificates.  You can get certificates by submitting
a project proposal on our website.  Copy your certificate files into
`certs/` and rename them as `client.crt`, and `client.key`.  Then
`chmod 400` all files in `certs/` to prevent unauthorized access to
your keys.

You will also need to *explicitly* create a `prefixes.txt` file
containing the prefixes you are going to announce.  This is an extra
safety net.  Specify one prefix per line, in the usual format, e.g.,
`184.164.236.0/24`.

## Controlling OpenVPN

`usage ./peering openvpn status|up mux|down mux`

Both OpenVPN and BIRD have to run with superuser rights, you may
want to run the provided scripts as root or `suid` the script.  When
controlling OpenVPN, we support three operations:

* `peering openvpn status`: show the status of OpenVPN tunnels.
  Tunnels can be either up or down.  If a tunnel is up, we will also
  list the device (the interface) it is running on and the local IP
  address.  You can use `ip route` to identify the IP address of the
  remote end as the gateway associated with each tunnel.

* `peering openvpn up|down mux`: bring the tunnel up to `mux` up or
  down.  Muxes are identified by their nicknames, which you can
  check by running `openvpn status` above.

## Controling BIRD

`usage: ./peering bgp cli|start|status|stop|adv mux`

We support five operations to interact with BIRD:

* `peering bgp start|stop`: start or stop the BIRD software router.
  BIRD is preconfigured to establish BGP sessions with all PEERING
  muxes through OpenVPN tunnels.  Use OpenVPN to create tunnels to
  the muxes you want BIRD to establish BGP sessions with.  Starting
  or stopping bird will establish and close all BGP sessions
  automatically.

* `peering bgp status`: show the status of the BIRD software router.
  If BIRD is running, it will show the status of BGP all sessions.
  Sessions in Idle state are waiting for their respective OpenVPN
  tunnels to be established.  Sessions in the Established state are
  exchanging routes.

* `peering bgp adv mux`: show which prefixes are being advertised
  to `mux`.  This is useful when debugging announcements.

* `peering bgp cli`: open the BIRD command line interface.  Type '?'
  in the BIRD interface to see a list of possible commands.  Use at
  your own risk.

## Controlling prefix announcements

```
usage: peering prefix announce|withdraw [-m mux]
                                        [-p poison | [-P prepend] [-o origin]]
                                        [-c id1] ... [-c idN]
                                        prefix
```

We also provide support for announcing and withdrawing PEERING
prefixes.  Be sure to use only prefixes allocated to you, or your
announcements will be filtered at PEERING servers.  When announcing
or withdrawing prefixes, we support the following options:

* `[-m mux]`: control which `mux` to announce or withdraw from.
  Use the mux nickname as shown by `openvpn status`.  The default is
  to announce and withdraw from all muxes (anycast).

* `[-p asn]`: poison a given ASN, i.e., prepend the announcement to
  include `asn` in the AS-path and trigger BGP loop prevention.
  Also known as BGP poisoning.  [default: do not poison]

* `[-P N]`: prepend the origin ASN `N` times.  Cannot be combined
  with `-p`, can be combined with `-o`.  [default: 0]

* `[-o asn]`: change the origin ASN, i.e., the first ASN in the AS-path,
  to `asn`.  Cannot be combined with `-p`, sets -P to 1 if not specified.
  [default: unchanged (47065)]

* `[-c id]`: add community `(47065,id)` to the announcement, making
  sending the announcement through the peer identified by `id` only.
  Can be used multiple times to send announcements through multiple
  peers.  Click [here][2] for a list of PEERING peers.

  [2]: https://peering.usc.edu/peers/

## Controlling TinyProxy

`usage ./peering proxy start|stop|status`

Both OpenVPN and TinyProxy have to run with superuser rights.  The proxy
for a given mux's container needs to start after the OpenVPN tunnel is
established, or TinyProxy will be unable to bind to the right IP
address.

This script reads your container's *allocated prefix ID* from a file
named `container.txt`.  This information is necessary to compute
prefixes and install routes, you can find it on the PEERING website
dashboard.

* `peering proxy start mux`: start the proxy for communicating with
  the container on the given mux.

* `peering proxy stop mux`: stop the proxy for the mux passed as
  parameter.  Use `all` to stop all proxies.

* `peering proxy status`: show the status of running proxies.

Bringing up a proxy prints relevant information to access and interact
with that mux's container.

```
TinyProxy addresses for isi01 (tap2, 2)
  local address: 100.66.128.6:8802
  subnet: 100.125.16.8/30
  pidfile: /home/cunha/git/peering/client/var/tinyproxy.isi01.pid
  logfile: /home/cunha/git/peering/client/var/tinyproxy.isi01.log
updating (add) 100.125.16.8/30 via 100.66.128.1 dev tap2
updating (add) 2804:269c:ff03:2:2::/80 via 2804:269c:ff00:2:1::1 dev tap2
```

After the proxy is configured, you can start using it *on the
container* by setting the `http_proxy` environment variable to match
TinyProxy's local address (above).

```
export http_proxy=http://100.68.128.8:8805/
```

You can SSH into your container by using the *second host* in the `/30`
subnet.  You should login as `root` using your private key:

```
ssh -i ~/.ssh/peering_id_rsa root@100.125.16.10
```

## Guidelines

Follow these guidelines when using your PEERING client:

* Do not announce prefixes that are not allocated to your
  experiment.  Do not announce prefixes outside of PEERING address
  space.  (The PEERING prefix control script will print a list of
  valid PEERING prefixes if you input an incorrect one.)

* Similarly, do not spoof packets with source IP addresses outside
  the PEERING address space allocated to your experiment.

* Do not change announcements more than once every 90 minutes.  This
  ensures your experiment is not affected by route-flap dampening
  and avoids attracting complaints operators.

* Be conservative.  Routers are often running close to their limits
  and we do not want any breakage.  In particular, do not announce
  AS-paths with more than 5 AS-hops, do not announce paths
  containing AS-sets with more than 5 ASes, and do not announce
  paths with more than 5 attached communities.

## Limitations and extending the controller

The control scripts allow you to quickly start using PEERING.  They
do not cover all possible uses of PEERING.  If you need to perform
more complex announcements (e.g., make BGP announcements with BGP
communities attached), these scripts provide a useful starting
point.

## More informations

More informations about PEERING configuration:

* [Client data plane.][3]
* [Mux data plane.][4]
* Additional information can be found [here][5].

[3]: https://github.com/PEERINGTestbed/client/wiki/Client-data-plane/
[4]: https://github.com/PEERINGTestbed/client/wiki/Mux-data-plane/
[5]: https://github.com/PEERINGTestbed/client/wiki/

## Python library

The `peering.py` module can be imported into Python programs to
programmatically control announcements.  It is tested in `python3`
and depends on `jsonschema` and `jinja2`.  Announcements are
specified in JSON; the JSON schema is described in
`configs/announcement_schema.json`.  You should edit the
`allocatedPrefixes` entry in the JSON schema to the prefixes
allocated to your experiment.
