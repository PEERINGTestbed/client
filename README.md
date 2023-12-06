# PEERING client controller

The PEERING client controller is a set of scripts to ease configuration and operation of a PEERING client, able to connect to PEERING routers and announce PEERING prefixes.

## Installation

After cloning [this repository][1], follow the instructions below to
install software dependencies and set up your PEERING client.

[1]: https://github.com/PEERINGTestbed/client

### Software dependencies

The client runs OpenVPN to connect your machine directly to PEERING routers.  We then run the BIRD software router to establish BGP sessions over the OpenVPN tunnels.  BIRD is used to control prefix announcements.  You will also need the `socat` tool that scripts use to interact with the OpenVPN socket.  On Debian, you'll need `apt install bird openvpn socat psmisc ipcalc`.

After installing OpenVPN and BIRD, you may want to disable these services on your machine, which some distributions may enable by default.  On Debian, run `systemctl disable bird bird6 openvpn` to accomplish this.

The provided BIRD configurations are compatible with BIRD 1.6 (but not 2+).  BIRD is available for most distributions, but you can compile Bird from [source][bird-src].

[bird-src]: http://bird.network.cz/?download

### PEERING account setup

To establish OpenVPN tunnels with PEERING routers, you will need PEERING-issued certificates.  You can get certificates by submitting a project proposal on our website.  Copy your certificate files into `certs/` and rename them as `client.crt`, and `client.key`.  Then `chmod 400` all files in `certs/` to prevent unauthorized access to your keys.

You will also need to *explicitly* create a `prefixes.txt` file containing the prefixes you are going to announce.  This is an extra safety net.  Specify one prefix per line, in the usual format, e.g., `184.164.236.0/24`.

## Controlling OpenVPN

Run `./peering openvpn` to get a description of command-line parameters for interacting with OpenVPN.  The `status` command shows the status of OpenVPN tunnels.  Tunnels can be either up or down.  If a tunnel is up, we will also list the device (the interface) it is running on and the local IP address.  You can use `ip route` to identify the IP address of the remote end as the gateway associated with each tunnel.

You can pass the special value `all` to operate on all PEERING routers simultaneously.

> Creating BGP sessions with many routers simultaneously will significantly increase the amount of memory needed by BIRD.

## Controling BIRD

Run `./peering bgp` or `./peering bgp6` to get a description of command-line parameters for interacting with BIRD.  You need to start the v4 and v6 versions separately.  When you start BIRD, it will continuously attempt to establish BGP sessions with all PEERING routers (and will succeed to establish a session if the OpenVPN tunnel is up).  Starting or stopping BIRD will establish and close all BGP sessions automatically.

When checking the `status` of BGP connections, note that sessions in the "Idle" state are waiting for their respective OpenVPN tunnels to come up.  This is not an issue.  Sessions in the Established state are up and exchanging routes.

> Warning: The PEERING client imports all routes by default, so if you connect to many muxes, the routing tables will take up a lot of RAM. Suggestions include (1) establishing OpenVPN tunnels only with the muxes you plan to use or (2) changing the import filter in the BIRD configuration (change `import all` to `import none` in `configs/bird[6]/bird[6].conf`).

## Controlling prefix announcements

Run `./peering prefix` to get a description of command-line parameters available to control prefix announcements.  The scripts supports prepending, changing the origin AS, poisoning an AS, and attaching communities.  Note that BGP poisoning and communities require special capabilities that must be assigned to your account by PEERING staff before you can use them.

## Running an application behind PEERING

The `app` module configures a network namespace with a single
interface, and routes the network namespace through PEERING OpenVPN
tunnels.  Run `./peering app` for a list of available parameters.

Each application operates on a PEERING prefix (either v4 or v6).  We support
isolating applications in their own network namespace or with a Linux virtual bridge.  The virtual bridge approach is useful to run Docker containers attached to the bridge.

By default, the namespace or bridge is called `pappX`, where X is an ID to identify the namespace.  Users that need multiple applications will need to set a different ID to each application.  By default, the application's egress traffic will be routed using table 20000, which is populated by BIRD.  An option allows the user to choose a specific upstream to route egress traffic out of (`-u`).  When deleting an application (`-d`), pass all the other parameters identically to when the application was created.

## Start using your PEERING client

Once your client is configured you should be able to run experiments.  Here are some steps to get you started:

- `cd` into the client directory

- Use the `./peering` script to establish an OpenVPN connection to a PEERING router, e.g., `./peering openvpn up <mux>`.

- Use the `./peering` script to establish a BGP session for exchanging routes with the router, e.g., `./peering bgp start`.

    > Warning: When using IPv6, you need to edit the `client/bird6/bird6.conf` file and set a valid router ID (search for the line starting with `router id`) and use a unique IP address (e.g., one allocated to your experiment)

Read the output of `./peering prefix` to find out how to make and control announcements.  For example, to announce your prefix out of all PEERING routers you are connected to, use `./peering prefix announce <prefix>`.

You can check that your prefix is propagating by using Looking Glass servers from multiple providers:

- [Spring](https://www.sprint.net/tools/looking-glass)
- [NTT](https://www.gin.ntt.net/looking-glass-landing/)
- [Level3/Lumen](https://lookingglass.centurylink.com/)

> Troubleshooting: If the  prefix does not seem to be propagating, check that the OpenVPN tunnel is up, that the BGP session is established, and that your client is exporting the prefix to the desired router:
>
> ```bash
> ./peering openvpn status
> ./peering bgp status
> ./peering bgp adv <router>
> ```

To shut everything up, stop the BGP server and OpenVPN tunnels:

```bash
./peering bgp stop
./peering openvpn down all
```

## Guidelines

Follow these guidelines when using your PEERING client:

* Do not announce prefixes that are not allocated to your experiment.  Do not announce prefixes outside PEERING address space.  (The PEERING prefix control script will print a list of valid PEERING prefixes if you input an incorrect one.)

* Similarly, do not spoof packets with source IP addresses outside the PEERING address space allocated to your experiment.

* Do not change announcements more than once every 10 minutes.  For best results, prefer to leave announcements up for 90 minutes to avoid route-flap dampening.

* Be conservative.  Routers are often running close to their limits and our first priority is to not disrupt Internet operation.  In particular, do not announce AS-paths with more than 5 AS-hops, do not announce paths containing AS-sets with more than 5 ASes, and do not announce paths with more than 5 attached communities.

## Running announcements via Web

PEERING offers a way to make announcements via REST API, without the need for a VPN connection and prior approval of an experiment on the platform.  These announcements are scheduled and made according to the availability of prefixes.  Each sequence of announcements is considered an experiment.  Each  announcement lasts 90 minutes (to allow for BGP convergence and avoid route-flap dampening).

To deploy an experiment we can use the `peering.py` script in this directory.  Just pass the experiment as parameter and the URL of the page.  An example of an experiment can be seen at `utils/experiment-examples/experiment-1.json`.  An experiment can be generated by using the following python code `utils/experiment-generator.py`.

Access to the API is controlled by a permission token that becomes available to you in the user dashboard on the PEERING site.  Note that the API is very limited; if you need fine-grained control over the announcements, consider submitting a proposal on the Website to receive full access and use the functionality above.  The token must be in the certificate directory `certs/token.json` like shown below.  The refresh token is currently not required.  More information on the wiki [page][5]

```json
{
  "access": "<token>",
  "refresh": ""
}
```

## Accessing Containers on Muxes

We use TinyProxy to provide a proxy for HTTP access from inside your container on PEERING routers.  If your experiment does not run containers on PEERING routers, then you have no need to use TinyProxy.

Run `./peering proxy` to get a description of command-line parameters available to interact with TinyProxy.  The proxy for a given router's container needs to start after the OpenVPN tunnel is established, or TinyProxy will be unable to bind to the right IP address.

This script reads your container's *allocated prefix ID* from a file named `container.txt`.  This information is necessary to compute prefixes and install routes, you can find your container's ID on the PEERING website dashboard.  Generate the file with `echo ID > container.txt`.

Bringing up a proxy prints relevant information to access and interact
with that router's container.

```{text}
TinyProxy addresses for isi01 (tap2, 2)
  local address: 100.66.128.6:8802
  subnet: 100.125.16.8/30
  pidfile: /home/cunha/git/peering/client/var/tinyproxy.isi01.pid
  logfile: /home/cunha/git/peering/client/var/tinyproxy.isi01.log
updating (add) 100.125.16.8/30 via 100.66.128.1 dev tap2
updating (add) 2804:269c:ff03:2:2::/80 via 2804:269c:ff00:2:1::1 dev tap2
```

You can SSH into your container by using the *second host* in the `/30`
subnet. In other words, SSH to the third address in the /30.  You should log in as `root` using your private key:

```{bash}
ssh -i ~/.ssh/peering_id_rsa root@100.125.16.10
```

You can use the proxy *on the container* by setting the `http_proxy`
environment variable to match TinyProxy's local address (above).

```{bash}
export http_proxy=http://100.66.128.6:8802/
apt update
apt install lighttpd
```

Containers have limited RAM and disk space. The amount of RAM available on containers is *insufficient* to run a PEERING client on IXP sites (e.g., `amsterdam01` and `seattle01`). We recommend users run the PEERING client remotely (e.g., on the cloud or at a server in their institution), and route traffic into the container by rewriting the BGP next-hop field (see the `-M` parameter to `./peering prefix`).

## Limitations and extending the controller

The control scripts allow you to quickly start using PEERING.  They do not cover all possible uses of PEERING.  If you need to perform more complex announcements (e.g., make BGP announcements with BGP communities attached), these scripts provide a useful starting point.

## Further information

More information about PEERING configuration:

* [Client data plane.][3]
* [Mux data plane.][4]
* Additional information can be found in the [Wiki][5].

[3]: https://github.com/PEERINGTestbed/client/wiki/Client-data-plane/
[4]: https://github.com/PEERINGTestbed/client/wiki/Mux-data-plane/
[5]: https://github.com/PEERINGTestbed/client/wiki/

## Python library

The `peering.py` module can also be imported into Python programs to programmatically control announcements.  Announcements are specified in JSON, following the JSON schema in `configs/announcement_schema.json`.  You should edit the `allocatedPrefixes` entry in the JSON schema to the prefixes allocated to your experiment.
