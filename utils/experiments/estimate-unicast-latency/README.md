# Results

The measurements happen in rounds. Each round uses 14 prefixes. The configured announcements for each round are stored into `phaseX/roundN/announcements.json`. They are JSON dumps of the data an `UpdateSet`, as defined in the [PEERING client library](https://github.com/PEERINGTestbed/client/blob/cdfdda2c0baebe21519bafb613362365a4f42918/peering.py#L128-L129).

We store a list of timestamps for the actions performed in each round inside `phaseX/roundN/timestamps.json`, this is mostly useful to identify which RIPE Atlas traceroutes were performed during each round.

We have one directory for the catchment measurements of each prefix used in the experiment. The number in the directory name is the third octet of the PEERING prefix used.  For example, `catchment_224` contains the catchment measurements for prefix `184.164.224.0/24`.  Each directory contains `tcpdump` `pcap` files, one file per PEERING mux.  This let's us know which mux a response was received from (and thus the respective catchment of each mux).  We can read the `pcap` files using `tcpdump -r`.

## Experiment Description

Pulled from the [authoritative GDoc](https://docs.google.com/document/d/1WZcPjFNIQlWm-qzfJ9Lj79dnbyBf11PU9r9lSNkOVMA/edit?usp=sharing).

We will perform a sequence of BGP announcements to discover alternate routes. We will start with an anycast announcement, to discover the most preferred routes toward PEERING locations. We will then perform two sequences of announcements to discover alternate, less preferred routes, described below.

For these experiments, we will consider PEERING’s IXP providers (RGNet, Coloclue, and BIT), IXP route-servers, and the set of all peers at each IXP as a PEERING “sub-site” that can be withdrawn independently. For reference, PEERING has 32 Vultr sites, 11 non-Vultr sites, and 9 sub-sites (3 at the SIX, 4 at AMSIX, and 2 at [IX.br/SP](http://IX.br/SP)).

Planned sequences of announcements based off of the anycast announcement. Batch 1 has 4 phases and aims at identifying the second most preferred route for every network in the Internet, and whether the choice is based on route length or LocalPref:

1. Withdraw from one PEERING sub-site at a time, for a total of 52 announcements. Will identify the second most preferred route.
2. Prepend from one PEERING sub-site at a time, for a total of 52 announcements. May identify the second most preferred route if the choice was based on path length. At Vultr sites, will identify the second most preferred Vultr site each provider (for each monitored remote endpoint). Remote networks are unlikely to change which Vultr provider they route to as prepended announcements will not be exported by Vultr providers.
3. Withdraw from one Vultr provider at a time (at all sites), for a total of V announcements. Will discover the second most preferred routes of remote networks routing to a Vultr provider.
4. Prepend to one Vultr provider at a time (at all sites), for a total of V announcements, where V (V \= 9\) is the number of distinct Vultr providers. May discover the second most preferred route of remote networks routing to a Vultr provider if the choice was based on route length.

Batch 2 has 2 phases and aims at at identifying the third most preferred route for every network on the Internet:

5. Withdraw from two PEERING sub-sites at a time, for a total of 52\*51 announcements (minus the overlapping cases of withdrawing from an IXP site and any of its sub-sites). Will identify the third most preferred route.
6. Withdraw from one Vultr provider and one non-Vultr PEERING sub-site at a time, for a total of 20\*V announcements.

Batch 3 has 2 phases and aims at identifying the pairwise preferences among PEERING sub-sites and Vultr providers for every network on the Internet:

7. Announce to every possible pair of PEERING sub-sites at a time, for a total of 52\*51 announcements.
8. Announce to every possible pair of one Vultr provider and one non-Vultr PEERING sub-site at a time, for a total of 20\*V announcements.

This gives us a an estimated total of 2\*52 and 2\*V announcements for phase 1 (about 200 announcements), and 52\*51 \+ 20\*V announcements in phases 2 and 3 (about 3000 announcements each).

We will keep announcements up for 90 minutes to avoid route flap dampening, and to collect multiple traceroute measurements from RIPE Atlas towards these prefixes. Considering each prefix will be able to make 16 announcements per day, we will make use of 14 IPv4 prefixes to reduce the total experiment run-time. Considering we will run with P \= 14 prefixes, this will take around 40 days (the first phase finishes in 1 day, and will be used to double-check the deployment is working as expected).

We will issue traceroutes toward these prefixes from RIPE Atlas probes, using Reverse Traceroute’s RIPE allowance (of 100M credits/day). The planned configuration is to use 6400 Probes per prefix, issuing traceroutes (configured to send a single probe per hop, costing 10 credits each) every 20 minutes (72 traceroutes per day). This will give P\*6400\*72\*10 total credit cost. For P \= 14, we would use 64M credits/day. This will incur an additional probing rate of 30\*14/(20\*60) \= 0.35 pps on each RIPE Atlas Probe (in the worst case, considering 30 probes per traceroute). The PEERING client will receive P\*6400\*20/(20\*60) \= 1493 pps (in the worst case, considering RIPE will send packets for 30 hops and the last 20 will get to the client).

We will also issue ping measurements towards a hitlist of 500K responsive IP addresses based on ISI’s hitlist. These measurements will allow us to compute catchments and estimate performance. Pings will start 20 minutes after making an announcement to allow for route convergence, and will execute in the period of 60 minutes before the next announcement change (10 minutes of slack). We will issue 3 probes per target to check for catchment oscillations and to allow some confidence over RTT estimation. Considering P \= 14 prefixes, 3 probes per IP, 405K destinations, and 1h run time, measurements will require a 14\*3\*405000/60/60 \= 4725 pps probing rate (across all prefixes).

## Broader impact

Discovering alternate less-preferred routes is a key mechanism in discovering AS routing preferences, and indirectly probing their routing policies. This is useful for

* Jiangchen’s work on modeling routing preferences
* Osvaldo’s work on locating the sources of spoofed packets
* Kevin’s work on identifying the impact of site outages

Possible analyses:

* Check if the pairwise preferences can estimate the first, second, and third most preferred paths accurately
* Quantify fraction of preferred paths that are chosen based on path length
* Compare Vultr site preference across providers

We could make this dataset public to the networking research community at large.

## Deployment notes

Controlling announcements to Vultr providers (in V) is done by setting [Vultr traffic-engineering BGP communities](https://github.com/vultr/vultr-docs/tree/main/faq/as20473-bgp-customer-guide#action-communities). At IXPs, we use [PEERING traffic-engineering BGP communities](https://github.com/PEERINGTestbed/client) to control announcements to sub-sites.
