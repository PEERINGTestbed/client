# PEERING client controller

The PEERING client controller is a set of scripts to ease
configuration and operation of a PEERING client, able to connect to
PEERING muxes and announce PEERING prefixes.

## Installation

After cloning [this repository][1], follow the following
instructions to install software dependencies and set up your
PEERING client.

  [1]: https://github.com/TransitPortal/client

### Software dependencies

The client runs OpenVPN to connect directly to PEERING muxes and
the BIRD software router to establish BGP sessions and perform
announcements.  You can install these dependencies from your distro
repository; on Debian use `apt-get install openvpn bird`.

### PEERING account setup

To establish OpenVPN tunnels with PEERING muxes, you will need
PEERING-issued certificates.  You can get certificates by submitting
a project proposal on our website.  Copy your certificate files into
`openvpn/certs/` and rename them as `client.crt`, and `client.key`. 
Then `chmod 400` all files in `openvpn/certs/` to
prevent unauthorized access to your keys.

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

`usage: peering prefix announce|withdraw [-m mux] [-p poison] prefix`

We also provide support for announcing and withdrawing PEERING
prefixes.  Be sure to use only prefixes allocated to you, or your
announcements will be filtered at PEERING servers.  When announcing
or withdrawing prefixes, we support the following options:

* `[-m mux]`: control which `mux` to announce or withdraw from.
  Use the mux nickname as shown by `openvpn status`.  The default is
  to announce and withdraw from all muxes (anycast).

* `[-p asn]`: poison a given ASN, i.e., prepend the announcement to
  include `asn` in the AS-path and trigger BGP loop prevention.

* `[-o asn]`: change the origin ASN, i.e., the first ASN in the AS-path,
  to `asn`.  Cannot be combined with `-p`.

* `[-c id]`: Add community `(47065,id)` to the announcement, making
  sending the announcement through the peer identified by `id` only.
  Can be used multiple times to send announcements through multiple
  peers.  Click [here][1] for a list of PEERING peers.

  [1]: https://peering.usc.edu/peers/

Please follow these guidelines when using your PEERING client:

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

