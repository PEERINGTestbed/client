# PEERING client utilities

This directory contains a set of short scripts that might be useful
when using the PEERING testbed.  Here is a short explanation of what
the scripts do:

## dump-peer-routes

This scripts dumps all routes your client has received to a JSON
file.  The script connects to your client's BIRD instance at the
socket pointed to by the `BIRD_SOCKET` variable inside the scripts
(defaults to `../var/bird.ctl`).  The name of the output file is set
by variable `OUTPUT_FILE` in the script.  If the output file name
ends in `.gz`, then the file will be compressed using Python's zlib.

Note this script can take several minutes to complete if your client
receives many routes (e.g., when you connect to AMS-IX).

## get-peer-csv

This script simply downloads an up-to-date list of PEERING peers
from the website.  Here is how this information can be combined with
the route dump above.

PEERING sets the next hop of routes your client receives to an IP
address that depends on the peer the route was received from.  In
particular, the next hop follows a `100.X.Y.Z` format, where:

* X is the mux identifier (8 bits).  It equals 64 plus the mux's
  number.  The mux number is also used to establish the OpenVPN
  tunnels.  For example, `amsterdam01` is mux number 5, its tunnel
  is tap5 and its mux identifier is 69.

* X.Y is the peer identifier (16 bits).  The peer identifier is
  given in the last column of the peer CSV downloaded by this
  script.  For example, AMS-IX's route server is peer 29, so the
  next hop used by routes received from AMS-IX route server is
  `100.69.0.29`.



