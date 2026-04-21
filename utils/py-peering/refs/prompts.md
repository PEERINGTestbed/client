Please make sure prefixes and IP addresses are passed as instances of these objects from the ipaddress module (IPvXNetwork/Address).

Please allow an optional parameter `egress_priority: list[MuxName]` to deploy()

Please revert the signature of unset_egress to have it receive a priority value (the `ip rule` priority).  Compute the priority value from the prefix's third octet before calling the function

-----

set_egress should not receive the priority as input; it should compute it by adding the base priority to the third octet of the IP address.

please refactor UpdateSet to store a mapping with keys of type IPvXNetwork.  please remove _str suffix when using the keys from UpdateSet.

-----

manually fix deploy()

-----

for v6 prefixes, compute the priority for set/unset egress by adding the base priority to the value of the bits 40-48 in the v6 prefix

-----

peering.py:38-38
```
def load_mux2id(cfgs_dir: pathlib.Path) -> dict[str, int]:
```

please refactor to return dict[MuxName, int]

-----

please update set/unset egress and the prio-related functions to operate on whole prefixes instead of individual IP addresses (e.g., create an IP rule for all IPs in the prefix)

-----

peering.py:481-487
```
        prio = self.config.base_ip_rule_prio + get_ip_rule_prio_offset(prefix)
        logging.info("Unsetting egress for prefix %s (prio %d)", prefix, prio)
        with IPRoute() as ip:
            ip.flush_routes(table=prio)
            for rule in ip.get_rules(priority=prio):
                try:
                    ip.rule("del", **rule)
```
can we modify such that we pass only the rule priority to ip.rule("del"); please check pyroute2 semantics

## Moving PEERING Python Library into a Package

OK, i want to move the peering.py and test_peering.py files from the root directory. i also want to make sure it can be included as a package. i want to manage it using uv. i need it to be used as a dependency of the script in utils/experiments/estimate-unicast-latency/measure-anycast-latency.py. it will also be used as a dependency of the script and library in utils/measure-latency. how can i achieve this? can i move peering.py and measure-latency into a single directory inside utils, like utils/py-peering and then use that as a dependency inside estimate-unicast-latency? what changes would be needed?

## PEERING DataPlane egress tests

create functions to test DataPlane.update_egresses and unset_egresses. use the following strategy: check that no rules exist; check rules by using the get_egress_table method and a helper function to get the IP rules with that that priority. then configure egresses. then check again that the rules exist. also check that the tables with the same number have a default route. finally, clean up the egress by calling unset_egresses and making sure the rules and default tables are gone

## Sequencer and measure-latency test

Please create an end-to-end test using the peering.Sequencer class, using the latency.py::round_callback function.  The idea is to replicate the test in tests/integration/run-latency-test.sh, but instead of a single MUX and PREFIX pair, we should use 4 muxes and 2 prefixes (such that the Sequencer takes two rounds).  Use the following configuration:

        description: str
        basedir: pathlib.Path
        outdir: pathlib.Path
        prefixes: list[IPNetwork] = 184.164.224.0 and .225.0
        round_duration: int = 120
        withdraw_every_round: bool = True
        withdraw_duration: int = 15
        egress_priority: list[Mux] = []
        updates: list[Update] = // use first 4 vtrmuxes in peering.Mux

For the pings, use the same target list and configuration as in run-latency-test.sh.

Consider that the OpenVPN tunnels and BIRD sessions will already be established.
