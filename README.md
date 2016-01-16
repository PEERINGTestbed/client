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
`openvpn/certs/` and rename them as `client.crt`, `client.csr`, and
`client.key`.  Then `chmod 400` all files in `openvpn/certs/` to
prevent unauthorized access to your keys.

## Controlling OpenVPN

## Controling BIRD

## Controlling prefix announcements

## Limitations and extending the controller

The control scripts allow you to quickly start using PEERING.  They
do not cover all possible uses of PEERING.  If you need to perform
more complex announcements (e.g., make BGP announcements with BGP
communities attached), these scripts provide a useful starting
point.

