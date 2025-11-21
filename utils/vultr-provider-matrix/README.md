# Vultr Provider Matrix

## Vultr BGP Communities

Vultr's documentation of BGP communities is
[here](https://github.com/vultr/vultr-docs/tree/main/faq/as20473-bgp-customer-
guide).

The following table describes Vultr's community tagging:

| Prefix type                            | Community     | Large Community                     |
| :---:                                  | :---:         | :---:                               |
| From Transit                           | 20473:100     | 20473:100:transit-as                |
| From Public Peer via route servers     | 20473:200     | 20473:200:ixp-as                    |
| From Public Peer via bilateral peering | 20473:200     | 20473:200:ixp-as, 20473:200:peer-as |
| From Private Peer                      | 20473:300     | 20473:300:peer-as                   |
| From Customer                          | 20473:4000    |                                     |
| From AS20473                           | 20473:500     |                                     |
| From AS (if <= 65535)                  | 20473:peer-as | 20473:peer-type:peer-as             |

## JSON format

Each route is presented in JSON with the following format:

```json
[
  {
    "net": "49.14.107.0/24",
    "rtype": "unicast",
    "proto": "up518_64515",
    "since": "2025-08-14",
    "from": "from 169.254.169.254",
    "primary": "*",
    "info": "(100/?) [AS45271i]",
    "iface": "henp1s0",
    "via": "95.179.182.1",
    "attributes": {
      "Type": "BGP univ",
      "BGP.origin": "IGP",
      "BGP.as_path": [
        64515,
        65534,
        20473,
        3356,
        55644,
        45271
      ],
      "BGP.next_hop": "100.89.2.6",
      "BGP.local_pref": 100,
      "BGP.atomic_aggr": "",
      "BGP.aggregator": "10.100.230.241 AS65010",
      "BGP.community": "(20473,100) (20473,3356) (64515,44) (47065,10518)",
      "BGP.large_community": "(20473, 100, 3356)"
    }
  }
]
```
