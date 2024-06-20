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
        psmisc \
        rsync \
        git

RUN apt-get update && apt-get install --no-install-recommends -y \
        iputils-ping \
        traceroute \
        vim

WORKDIR /root
RUN git clone https://github.com/PEERINGTestbed/client.git
COPY entrypoint.sh /root/entrypoint.sh
RUN chmod +x /root/entrypoint.sh
# WORKDIR /root/client
# RUN git checkout import-none

ENTRYPOINT [ "/root/entrypoint.sh" ]
