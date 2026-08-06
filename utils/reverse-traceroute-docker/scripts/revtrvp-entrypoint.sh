#!/usr/bin/env bash
# =============================================================================
# revtrvp wrapper entrypoint
# -----------------------------------------------------------------------------
# Points the container's default route at the PEERING gateway container so all
# probe and control traffic egresses via the PEERING prefix, then hands off to
# the revtrvp binary.  Requires `iproute2` in the image (added in Task 3) and
# NET_ADMIN (granted in compose).
# =============================================================================
set -eu

# The PEERING gateway container's bbackend IP (overridable via compose env).
GATEWAY="${REVTR_GATEWAY:-184.164.231.254}"

# Replace Docker's default route (via the unused .253 bridge gateway) with the
# route through the peering container, which forwards/source-routes our traffic.
ip route replace default via "$GATEWAY"

# Hand off to revtrvp with the args supplied by compose `command:`.
exec /revtrvp "$@"
