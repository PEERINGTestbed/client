FROM python:3.9-bullseye
LABEL maintainer="PEERING Staff <team@peering.ee.columbia.edu>"

RUN apt-get update && apt-get install --no-install-recommends -y \
        wget \
        ca-certificates \
        apt-transport-https \
        bird \
        openvpn \
        socat \
        iproute2 \
        procps \
        rsync \
        git

RUN apt-get update && apt-get install --no-install-recommends -y \
        iputils-ping \
        traceroute

WORKDIR /root
RUN git clone https://github.com/PEERINGTestbed/client.git
# WORKDIR /root/client
# RUN git checkout import-none

ENTRYPOINT [ "/bin/bash" ]
