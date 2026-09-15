# Docker Compose file for the Reverse Traceroute + PEERING stack.
COMPOSE_FILE := docker-compose.yml
TEMPLATES = templates/
CONFIGS = config/
# Hardcoded data-plane egress mux (see docs/superpowers/specs/2026-08-06-...).
EGRESS_MUX := ufmg01

.PHONY: clean up down build logs peering-shell announce withdraw \
	bgp-status bgp-start dataplane-test setup-docker openvpn

clean:
	rm -f $(COMPOSE_FILE)

# Start the stack detached, establish ufmg01 egress for all backends, then
# follow logs. Ctrl-C stops log follow only; use `make down` to tear down.
#
# Host-level prerequisite: disable bridge-nf-call-iptables first. On hosts
# where it's enabled (e.g. because libvirt turned it on for its own bridges),
# reply traffic that `peering` relays back to `revtrvp` across a backend
# Docker bridge gets silently dropped one-way -- confirmed via packet capture
# (revtrvp<->peering direct traffic works, but forwarded/relayed traffic
# doesn't) -- even though BGP/the tunnel/everything else is healthy. This is a
# host-wide sysctl (not scoped to this project's containers/networks) and
# does NOT persist across reboots, so we re-assert it every `make up` rather
# than relying on it being set already. See README Troubleshooting.
up:
	sudo sysctl -w net.bridge.bridge-nf-call-iptables=0
	docker compose -f $(COMPOSE_FILE) up -d
	@echo "waiting for peering container..."
	@for i in $$(seq 1 60); do \
		if docker compose -f $(COMPOSE_FILE) exec -T peering true 2>/dev/null; then \
			break; \
		fi; \
		if [ $$i -eq 60 ]; then \
			echo "peering container not ready after 60s"; \
			exit 1; \
		fi; \
		sleep 1; \
	done
	$(MAKE) openvpn mux=$(EGRESS_MUX)
	docker compose -f $(COMPOSE_FILE) logs -f

# Bring up OpenVPN to mux=<name>. When mux is ufmg01, also install backend
# policy routes so all revtrvp traffic egresses via that mux.
openvpn:
	@test -n "$(mux)" || (echo 'usage: make openvpn mux=<name>'; exit 1)
	docker compose -f $(COMPOSE_FILE) exec peering \
		/peering-openvpn-up.sh "$(mux)"

# Start BIRD/BGP toward whatever mux tunnels are already up.
bgp-start:
	docker compose -f $(COMPOSE_FILE) exec peering ./peering bgp start

# Stop and remove containers, networks, and volumes created by compose.
down:
	docker compose -f $(COMPOSE_FILE) down

# Build or rebuild service images before starting.
build:
	docker compose -f $(COMPOSE_FILE) build

logs:
	docker compose -f $(COMPOSE_FILE) logs revtrvp

peering-shell:
	docker compose -f $(COMPOSE_FILE) exec peering bash

revtrvp-shell:
	docker compose -f $(COMPOSE_FILE) exec revtrvp bash

# Announce the PEERING prefix to the egress mux (manual data-plane step).
# -R skips the client's built-in data-plane config; our Makefile/openvpn
# helper owns tunnel + policy routing.
announce:
	docker compose -f $(COMPOSE_FILE) exec peering \
		./peering prefix announce -R -m vtrtoronto 184.164.231.0/24

# Withdraw the PEERING prefix from all muxes.
withdraw:
	docker compose -f $(COMPOSE_FILE) exec peering \
		./peering prefix withdraw 184.164.231.0/24

# Show BGP session status (Idle before announce is normal).
bgp-status:
	docker compose -f $(COMPOSE_FILE) exec peering ./peering bgp status

# Basic data-plane check: ping from inside the revtrvp container.
dataplane-test:
	docker compose -f $(COMPOSE_FILE) exec revtrvp ping -c 4 1.1.1.1

# Generate docker-compose.yml from templates via scripts/setup_docker.py.
# Expands one backend-* network, peering .254 attachment, and revtrvp (.1)
# service per prefix in config/prefixes.txt.
setup-docker: clean
	python3 scripts/setup_docker.py \
		--compose-template $(TEMPLATES)/docker-compose.template.yml \
		--backend-template $(TEMPLATES)/backend.template.yml \
		--peering-attach-template $(TEMPLATES)/peering-backend-attach.template.yml \
		--revtrvp-template $(TEMPLATES)/revtrvp.template.yml \
		--prefixes $(CONFIGS)/prefixes.txt \
		--output $(COMPOSE_FILE)
