from collections import defaultdict
import parsers.util as util

# from BIRD's nest/rt-table.c:
# cli_printf(c, -1007, "%-18s %s [%s %s%s]%s%s", ia, via, a->src->proto->name,
#            tm, from, primary ? (sync_error ? " !" : " *") : "", info);
SUMMARY_RE = r'^(?P<net>\S+)?\s+(?P<via>[^[]+)\[(?P<proto>\w+) (?P<since>[0-9:-]+)(?P<from> from \S+)?\](?P<primary> .)?(?P<info> .*)$'
SUMMARY_NETWORK_KEY = 'net'

DETAILS_RE = r'^\s+(?P<desc>[^:]+):(?P<data>.+)$'

__DETAILS_PARSERS = {
    'BGP.med': util.parse_desc_colon_int,
    'BGP.local_pref': util.parse_desc_colon_int
}

DETAILS_PARSERS = defaultdict(lambda: util.parse_desc_colon_str,
                              __DETAILS_PARSERS)
