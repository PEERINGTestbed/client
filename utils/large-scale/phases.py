import itertools

import defs

from peering import (
    IXP_SPECIAL_PEERS_V4,
    MUX_SETS,
    Announcement,
    MuxName,
    PeeringCommunities,
    Update,
    Vultr,
)

AS_PATH_PREPEND_LIST = [47065, 47065, 47065]


def phase1a() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for mux in MuxName:
        description = f"anycast+withdraw:{mux}"
        withdraw = [mux]
        muxes = set(MuxName)
        muxes.discard(mux)
        announce = [Announcement(list(muxes))]
        updates.append(Update(withdraw, announce, description))
    return updates


def phase1b() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for mux, asn2peerids in IXP_SPECIAL_PEERS_V4.items():
        for peerids in asn2peerids.values():
            description = (
                f"anycast+withdraw:{mux}+announce:{','.join(str(p) for p in peerids)}"
            )
            withdraw = []
            muxes = set(MuxName)
            muxes.discard(mux)
            communities = [PeeringCommunities.announce_to(pid) for pid in peerids]
            announce1 = Announcement([mux], communities=communities)
            announce2 = Announcement(list(muxes))
            announce = [announce1, announce2]
            updates.append(Update(withdraw, announce, description))
    return updates


def phase1_muxsets() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for desc, withdrawn_muxes in MUX_SETS.items():
        description = f"anycast+withdraw:{desc}"
        normal_muxes = set(MuxName)
        normal_muxes.difference_update(withdrawn_muxes)
        announce = [Announcement(list(normal_muxes))]
        updates.append(Update(withdrawn_muxes, announce, description))
    return updates


def phase2a() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for mux in MuxName:
        description = f"anycast+prepend:{mux}"
        withdraw = []
        muxes = set(MuxName)
        muxes.discard(mux)
        announce1 = Announcement([mux], prepend=AS_PATH_PREPEND_LIST)
        announce2 = Announcement(list(muxes))
        announce = [announce1, announce2]
        updates.append(Update(withdraw, announce, description))
    return updates


def phase2b() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for mux, asn2peerids in IXP_SPECIAL_PEERS_V4.items():
        for peerids in asn2peerids.values():
            description = (
                f"anycast+withdraw:{mux}+prepend:{','.join(str(p) for p in peerids)}"
            )
            withdraw = []
            muxes = set(MuxName)
            muxes.discard(mux)
            communities = [PeeringCommunities.announce_to(pid) for pid in peerids]
            announce1 = Announcement(
                [mux], prepend=AS_PATH_PREPEND_LIST, communities=communities
            )
            announce2 = Announcement(list(muxes))
            announce = [announce1, announce2]
            updates.append(Update(withdraw, announce, description))
    return updates


def phase2_muxsets() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for desc, prepended_muxes in MUX_SETS.items():
        description = f"anycast+prepend:{desc}"
        normal_muxes = set(MuxName)
        normal_muxes.difference_update(prepended_muxes)
        announce1 = Announcement(list(normal_muxes))
        announce2 = Announcement(list(prepended_muxes), prepend=AS_PATH_PREPEND_LIST)
        announce = [announce1, announce2]
        updates.append(Update([], announce, description))
    return updates


def phase3() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for provider in defs.VULTR_PROVIDERS:
        description = f"anycast+withdraw:vtr{provider}"
        muxes = set(MuxName)
        announce1 = Announcement([m for m in muxes if not m.startswith("vtr")])
        vtrmuxes = [m for m in muxes if m.startswith("vtr")]
        vtrcomm = Vultr.communities_do_not_announce([provider])
        announce2 = Announcement(vtrmuxes, communities=vtrcomm)
        announce = [announce1, announce2]
        updates.append(Update([], announce, description))
    return updates


def phase4() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for provider in defs.VULTR_PROVIDERS:
        description = f"anycast+prepend:vtr{provider}"
        muxes = set(MuxName)
        announce1 = Announcement([m for m in muxes if not m.startswith("vtr")])
        vtrmuxes = [m for m in muxes if m.startswith("vtr")]
        vtrcomm = Vultr.communities_prepend_thrice([provider])
        announce2 = Announcement(vtrmuxes, communities=vtrcomm)
        announce = [announce1, announce2]
        updates.append(Update([], announce, description))
    return updates


def phase5a() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for (mux1, mux2) in itertools.combinations(MuxName, 2):
        description = f"anycast+withdraw:{mux1},{mux2}"
        withdraw = [mux1, mux2]
        muxes = set(MuxName)
        muxes.discard(mux1)
        muxes.discard(mux2)
        announce = [Announcement(list(muxes))]
        updates.append(Update(withdraw, announce, description))
    return updates


def phase5b() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for mux1 in MuxName:
        for mux2, asn2peerids in IXP_SPECIAL_PEERS_V4.items():
            for peerids in asn2peerids.values():
                pidsstr = ','.join(str(p) for p in peerids)
                description = f"anycast+withdraw:{mux1},{mux2}+announce:{pidsstr}"
                withdraw = [mux1]
                muxes = set(MuxName)
                muxes.discard(mux1)
                communities = [PeeringCommunities.announce_to(pid) for pid in peerids]
                announce1 = Announcement([mux2], communities=communities)
                announce2 = Announcement(list(muxes))
                announce = [announce1, announce2]
                updates.append(Update(withdraw, announce, description))
    return updates


def phase5_muxsets() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for mux1 in MuxName:
        for desc, muxes in MUX_SETS.items():
            if mux1 in muxes:
                continue
            description = f"anycast+withdraw:{mux1},{desc}"
            withdraw = [mux1, *muxes]
            normal_muxes = set(MuxName)
            normal_muxes.difference_update(withdraw)
            announce = [Announcement(list(normal_muxes))]
            updates.append(Update(withdraw, announce, description))
    return updates


def phase6a() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    muxes = set(MuxName)
    nonvtr_muxes = [m for m in muxes if not m.startswith("vtr")]
    vtr_muxes = [m for m in muxes if m.startswith("vtr")]
    for provider in defs.VULTR_PROVIDERS:
        vtr_comms = Vultr.communities_do_not_announce([provider])
        vtr_ann = Announcement(vtr_muxes, communities=vtr_comms)
        for mux in nonvtr_muxes:
            description = f"anycast+withdraw:{mux},vtr{provider}"
            nonvtr_active = set(nonvtr_muxes)
            nonvtr_active.discard(mux)
            nonvtr_ann = Announcement(list(nonvtr_active))
            announce = [nonvtr_ann, vtr_ann]
            updates.append(Update([mux], announce, description))
    return updates


def phase6b() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    muxes = set(MuxName)
    nonvtr_muxes = [m for m in muxes if not m.startswith("vtr")]
    vtr_muxes = [m for m in muxes if m.startswith("vtr")]
    for provider in defs.VULTR_PROVIDERS:
        vtr_comms = Vultr.communities_do_not_announce([provider])
        vtr_ann = Announcement(vtr_muxes, communities=vtr_comms)
        for mux, asn2peerids in IXP_SPECIAL_PEERS_V4.items():
            nonvtr_active = set(nonvtr_muxes)
            nonvtr_active.discard(mux)
            nonvtr_active_ann = Announcement(list(nonvtr_active))
            for peerids in asn2peerids.values():
                pidsstr = ','.join(str(p) for p in peerids)
                nonvtr_sub_comms = [PeeringCommunities.announce_to(p) for p in peerids]
                nonvtr_sub_ann = Announcement([mux], communities=nonvtr_sub_comms)
                announce = [vtr_ann, nonvtr_active_ann, nonvtr_sub_ann]
                description = f"anycast+withdraw:{mux},vtr{provider}+announce:{pidsstr}"
                updates.append(Update([], announce, description))
    return updates


def phase7a() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for (mux1, mux2) in itertools.combinations(MuxName, 2):
        description = f"unicast:{mux1},{mux2}"
        announce = [Announcement([mux1, mux2])]
        updates.append(Update([], announce, description))
    return updates


def phase7b() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for mux1 in MuxName:
        for mux2, asn2peerids in IXP_SPECIAL_PEERS_V4.items():
            for peerids in asn2peerids.values():
                description = (
                    f"unicast:{mux1},{mux2}+{','.join(str(p) for p in peerids)}"
                )
                communities = [PeeringCommunities.announce_to(pid) for pid in peerids]
                announce2 = Announcement([mux1])
                announce1 = Announcement([mux2], communities=communities)
                announce = [announce1, announce2]
                updates.append(Update([], announce, description))
    return updates


def phase7_muxsets() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for desc, muxes in MUX_SETS.items():
        description = f"unicast:{desc}"
        updates.append(Update([], [Announcement(muxes)], description))
    return updates


def phase7_muxsets_unicast() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for mux1 in MuxName:
        for desc, muxes in MUX_SETS.items():
            if mux1 in muxes:
                continue
            description = f"unicast:{mux1},{desc}"
            announce1 = Announcement([mux1])
            announce2 = Announcement(muxes)
            announce = [announce1, announce2]
            updates.append(Update([], announce, description))
    return updates


def phase8a() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    muxes = set(MuxName)
    nonvtr_muxes = [m for m in muxes if not m.startswith("vtr")]
    vtr_muxes = [m for m in muxes if m.startswith("vtr")]
    for provider in defs.VULTR_PROVIDERS:
        vtr_comms = Vultr.communities_announce_to_upstreams([provider])
        vtr_ann = Announcement(vtr_muxes, communities=vtr_comms)
        for mux in nonvtr_muxes:
            description = f"unicast:{mux}+vtr{provider}"
            nonvtr_ann = Announcement([mux])
            announce = [nonvtr_ann, vtr_ann]
            updates.append(Update([], announce, description))
    return updates


def phase8b() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    muxes = set(MuxName)
    vtr_muxes = [m for m in muxes if m.startswith("vtr")]
    for provider in defs.VULTR_PROVIDERS:
        vtr_comms = Vultr.communities_announce_to_upstreams([provider])
        vtr_ann = Announcement(vtr_muxes, communities=vtr_comms)
        for mux, asn2peerids in IXP_SPECIAL_PEERS_V4.items():
            for peerids in asn2peerids.values():
                peerids_str = ','.join(str(p) for p in peerids)
                nonvtr_sub_comms = [PeeringCommunities.announce_to(p) for p in peerids]
                nonvtr_sub_ann = Announcement([mux], communities=nonvtr_sub_comms)
                announce = [vtr_ann, nonvtr_sub_ann]
                description = f"unicast:{mux}+announce:{peerids_str}"
                updates.append(Update([], announce, description))
    return updates


def phase9() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for mux in MuxName:
        description = f"unicast:{mux}"
        announce = [Announcement([mux])]
        updates.append(Update([], announce, description))
    return updates


def phase10() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    vtr_muxes = [m for m in MuxName if m.startswith("vtr")]
    for provider in defs.VULTR_PROVIDERS:
        vtr_comms = Vultr.communities_announce_to_upstreams([provider])
        vtr_ann = Announcement(vtr_muxes, communities=vtr_comms)
        description = f"unicast:vtr{provider}"
        updates.append(Update([], [vtr_ann], description))
    return updates
