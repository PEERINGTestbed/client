FROM debian:bullseye

RUN apt-get update
RUN apt-get -y --no-install-recommends install iputils-ping iproute2 traceroute tcpdump psmisc

ENTRYPOINT /bin/bash

