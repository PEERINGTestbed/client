import logging
import re


def normalize_desc(string):
    return string.strip()  # .lower().replace(' ', '_')


def set_desc_values(result, match):
    v = match.groupdict()
    result[normalize_desc(v["desc"])] = v
    del v["desc"]


def parse_desc_int_list(reader):
    REGEX = r"^\s+(?P<desc>[^:]+):\s+(?P<data>.+)$"
    line = reader.readline()
    m = re.match(REGEX, line)
    if "{" in m.group("data"):
        # Ignore AS-paths with AS-sets
        return normalize_desc(m.group("desc")), None
    data = [int(x) for x in m.group("data").split()]
    return normalize_desc(m.group("desc")), data


def parse_desc_colon_int(reader):
    REGEX = r"^\s+(?P<desc>[^:]+):\s+(?P<data>\d+)$"
    line = reader.readline()
    m = re.match(REGEX, line)
    return normalize_desc(m.group("desc")), int(m.group("data"))


def parse_desc_colon_str(reader):
    REGEX = r"^\s+(?P<desc>[^:]+):(?P<data>.*)$"
    line = reader.readline().rstrip()
    lines = [line]
    line = reader.readline()
    while line and line.startswith("\t\t"):
        lines.append(line.strip())
        line = reader.readline()
    reader.rewind_line()
    buf = "".join(l for l in lines)
    m = re.match(REGEX, buf)
    data = str(m.group("data")).strip()
    return normalize_desc(m.group("desc")), data


def parse_desc_lines(reader, regex, parsers, ignore_regex=None):
    result = dict()
    line = reader.readline()
    while line:
        if ignore_regex and re.match(ignore_regex, line):
            break
        m = re.match(regex, line)
        if not m:
            logging.debug("skipping details line [%s]", line)
            line = reader.readline()
            continue
        desc = m.group("desc")
        # allow parsers to be an instance of defaultdict:
        reader.rewind_line()
        try:
            k, v = parsers[desc](reader)
            result[k] = v
        except KeyError:
            logging.exception("parse_details: desc [%s] has no parser [%s]", desc, line)
            raise
        line = reader.readline()
    reader.rewind_line()
    return result


def add_line(d: dict, line: str) -> str:
    # TODO: handle import/export routes
    # see protocols.parse_proto_route_stats
    if ":" in line:
        key, value = [v.strip() for v in line.split(":", 1)]
        try:
            d[key] = int(value)
        except ValueError:
            d[key] = value
        return key
    d[line] = None
    return line


def parse_by_indentation(reader):
    lastkey = "details"
    root = { lastkey: {} }
    # stack of (indent, dict)
    stack: list[tuple[int, dict]] = [(0, root)]

    line = reader.readline()
    while line:
        indent = len(line) - len(line.lstrip())
        line = line.strip()
        if not line:
            break

        # pop until we find the correct parent level:
        logging.debug("indent %s", indent)
        logging.debug("line [%s]", line)
        logging.debug("dict %s", root)
        while stack and indent < stack[-1][0]:
            stack.pop()

        if indent == stack[-1][0]:
            lastkey = add_line(stack[-1][1], line)
        elif indent > stack[-1][0]:
            if stack[-1][1][lastkey]:
                nested = { lastkey: stack[-1][1][lastkey] }
            else:
                nested = {}
            stack[-1][1][lastkey] = nested
            lastkey = add_line(nested, line)
            stack.append((indent, nested))
        else:
            raise RuntimeError("unreachable")
        line = reader.readline()

    return root
