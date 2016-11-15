import re
import parsers.util as util

SUPPORTED = set(['BGP'])
HEADER_LINE_FIELDS = list(['name', 'proto', 'table', 'state', 'since', 'info'])
SUMMARY_RE = r'^(?P<name>\w+)\s+(?P<proto>\w+)\s+(?P<table>\w+)\s+(?P<state>\w+)\s+(?P<since>[0-9:-]+)\s*(?P<info>.*)$'
DETAILS_RE = r'^\s\s(?P<desc>[^:]+):(?P<data>.+)$'
BGP_DETAILS_RE = r'^\s\s\s\s(?P<desc>[^:]+):(?P<data>.+)$'


def parse_proto_routes(reader):  # {{{
    REGEX = r'^\s\s(?P<desc>\w+):\s+(?P<imported>\d+) imported, (?P<exported>\d+) exported(?:, (?P<preferred>\d+) preferred)?$'
    line = reader.readline()
    m = re.match(REGEX, line)
    values = m.groupdict()
    del values['desc']
    values = dict((k, int(v)) for k, v in values.items())
    return util.normalize_desc(m.group('desc')), values
# }}}


def parse_proto_route_stats(reader):  # {{{
    REGEX = r'^\s\sRoute change stats:\s+received\s+rejected\s+filtered\s+ignored\s+accepted$'
    REGEX_UPDATE = r'^\s\s\s\s(?P<desc>[\w ]+):\s+(?P<received>[\d-]+)\s+(?P<rejected>[\d-]+)\s+(?P<filtered>[\d-]+)\s+(?P<ignored>[\d-]+)\s+(?P<accepted>[\d-]+)$'
    REGEX_WITHDRAW = r'^\s\s\s\s(?P<desc>[\w ]+):\s+(?P<received>[\d-]+)\s+(?P<rejected>[\d-]+)\s+(?P<filtered>[\d-]+)\s+(?P<ignored>[\d-]+)\s+(?P<accepted>[\d-]+)$'
    route_change_stats = dict()

    line = reader.readline()
    m = re.match(REGEX, line)
    assert m

    line = reader.readline()
    m = re.match(REGEX_UPDATE, line)
    util.set_desc_values(route_change_stats, m)

    line = reader.readline()
    m = re.match(REGEX_WITHDRAW, line)
    util.set_desc_values(route_change_stats, m)

    line = reader.readline()
    m = re.match(REGEX_UPDATE, line)
    util.set_desc_values(route_change_stats, m)

    line = reader.readline()
    m = re.match(REGEX_WITHDRAW, line)
    util.set_desc_values(route_change_stats, m)

    return 'route_change_stats', route_change_stats
# }}}


def parse_bgp_state(reader):  # {{{
    result = dict()
    k, v = util.parse_desc_colon_str(reader)
    result[k] = v
    v = util.parse_desc_lines(reader, BGP_DETAILS_RE, BGP_DETAILS_PARSERS)
    result['details'] = v
    return 'bgp', result
# }}}


DETAILS_PARSERS = {
        'Description': util.parse_desc_colon_str,
        'Preference': util.parse_desc_colon_int,
        'Input filter': util.parse_desc_colon_str,
        'Output filter': util.parse_desc_colon_str,
        'Routes': parse_proto_routes,
        'Route change stats': parse_proto_route_stats,
        'BGP state': parse_bgp_state
}

BGP_DETAILS_PARSERS = {
        'BGP state': util.parse_desc_colon_str,
        'Neighbor address': util.parse_desc_colon_str,
        'Neighbor AS': util.parse_desc_colon_int,
        'Neighbor ID': util.parse_desc_colon_str,
        'Neighbor caps': util.parse_desc_colon_str,
        'Session': util.parse_desc_colon_str,
        'Source address': util.parse_desc_colon_str,
        'Hold timer': util.parse_desc_colon_str,
        'Keepalive timer': util.parse_desc_colon_str
}
