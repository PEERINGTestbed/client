import logging
import re


def normalize_desc(string):
    return string.strip()  # .lower().replace(' ', '_')


def set_desc_values(result, match):  # {{{
    v = match.groupdict()
    result[normalize_desc(v['desc'])] = v
    del v['desc']
# }}}


def parse_desc_colon_int(reader):  # {{{
    REGEX = r'^\s+(?P<desc>[^:]+):\s+(?P<data>\d+)$'
    line = reader.readline()
    m = re.match(REGEX, line)
    return normalize_desc(m.group('desc')), int(m.group('data'))
# }}}


def parse_desc_colon_str(reader):  # {{{
    REGEX = r'^\s+(?P<desc>[^:]+):(?P<data>.*)$'
    line = reader.readline().rstrip()
    lines = [line]
    line = reader.readline()
    while line and line.startswith('\t\t'):
        lines.append(line.strip())
        line = reader.readline()
    reader.rewind_line()
    buf = ''.join(l for l in lines)
    m = re.match(REGEX, buf)
    data = str(m.group('data')).strip()
    return normalize_desc(m.group('desc')), data
# }}}


def parse_desc_lines(reader, regex, parsers, ignore_regex=None):  # {{{
    result = dict()
    line = reader.readline()
    while line:
        if ignore_regex and re.match(ignore_regex, line):
            break
        m = re.match(regex, line)
        if not m:
            break
        desc = m.group('desc')
        # allow parsers to be an instance of defaultdict:
        reader.rewind_line()
        try:
            k, v = parsers[desc](reader)
            result[k] = v
        except KeyError:
            logging.exception('parse_details: desc [%s] has no parser [%s]',
                              desc, line)
            raise
        line = reader.readline()
    reader.rewind_line()
    return result
# }}}
