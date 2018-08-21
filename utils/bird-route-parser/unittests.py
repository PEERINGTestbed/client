#!/usr/bin/env python

import cStringIO
import logging
import logging.handlers
import os
import sys
import time
import unittest

import cblr
import parse


class TestShowProtocolsParser(unittest.TestCase):
    def setUp(self):
        self.devnull = open(os.devnull, 'w')
        pass

    def test_ParseSimpleProtocols1(self):  # {{{
        string = '''name     proto    table    state  since       info
device1  Device   master   up     20:06:57
dtap     Direct   igplocal up     20:06:57
bt_mux_c_test1 Pipe     mux      up     20:06:57    => bt_c_test1
bt_mux_c_test2 Pipe     mux      up     20:06:57    => bt_c_test2
up_2_65002 BGP      bt_up2   up     20:07:01    Established
bt_mux_up2 Pipe     mux      up     20:06:57    => bt_up2
up_1_65001 BGP      bt_up1   down   00:19:22
bt_mux_up1 Pipe     mux      up     20:06:57    => bt_up1
'''
        sio = cStringIO.StringIO(string)
        reader = cblr.CachingBufferedLineReader(sio)
        data = parse.show_protocols(reader, self.devnull)
        self.assertEquals(2, len(data))
        for bgp in data:
            self.assertFalse(bgp['details'])
    # }}}

    def test_ParseSimpleProtocols2(self):  # {{{
        string = '''name     proto    table    state  since       info
device1  Device   master   up     20:06:57
dtap     Direct   igplocal up     20:06:57

bt_mux_c_test2 Pipe     mux      up     20:06:57    => bt_c_test2
up_2_65002 BGP      bt_up2   up     20:07:01    Established

up_1_65001 BGP      bt_up1   down   00:19:22
'''
        sio = cStringIO.StringIO(string)
        reader = cblr.CachingBufferedLineReader(sio)
        data = parse.show_protocols(reader, self.devnull)
        self.assertEquals(2, len(data))
        for bgp in data:
            self.assertFalse(bgp['details'])
    # }}}

    def test_ParseSimpleProtocols3(self):  # {{{
        string = '''name     proto    table    state  since       info
device1  Device   master   up     20:06:57
dtap     Direct   igplocal up     20:06:57
bt_mux_c_test1 Pipe     mux      up     20:06:57    => bt_c_test1
bt_mux_c_test2 Pipe     mux      up     20:06:57    => bt_c_test2
bt_mux_up2 Pipe     mux      up     20:06:57    => bt_up2
bt_mux_up1 Pipe     mux      up     20:06:57    => bt_up1
'''
        sio = cStringIO.StringIO(string)
        reader = cblr.CachingBufferedLineReader(sio)
        data = parse.show_protocols(reader, self.devnull)
        self.assertEquals(0, len(data))
        for bgp in data:
            self.assertFalse(bgp['details'])
    # }}}

    def test_ParseComplexProtocols1(self):  # {{{
        string = '''name     proto    table    state  since       info
device1  Device   master   up     20:06:57
  Preference:     240
  Input filter:   ACCEPT
  Output filter:  REJECT
  Routes:         0 imported, 0 exported, 0 preferred
  Route change stats:     received   rejected   filtered    ignored   accepted
    Import updates:              0          0          0          0          0
    Import withdraws:            0          0        ---          0          0
    Export updates:              0          0          0        ---          0
    Export withdraws:            0        ---        ---        ---          0

dtap     Direct   igplocal up     20:06:57
  Preference:     240
  Input filter:   ACCEPT
  Output filter:  REJECT
  Routes:         1 imported, 0 exported, 1 preferred
  Route change stats:     received   rejected   filtered    ignored   accepted
    Import updates:              1          0          0          0          1
    Import withdraws:            0          0        ---          0          0
    Export updates:              0          0          0        ---          0
    Export withdraws:            0        ---        ---        ---          0

bt_mux_c_test1 Pipe     mux      up     20:06:57    => bt_c_test1
  Preference:     70
  Input filter:   ACCEPT
  Output filter:  ACCEPT
  Routes:         0 imported, 5 exported
  Route change stats:     received   rejected   filtered    ignored   accepted
    Import updates:             10         10          0          0          0
    Import withdraws:            5          0        ---          0          0
    Export updates:             10          0          0          0         10
    Export withdraws:            5          0        ---          0          5

bt_mux_c_test2 Pipe     mux      up     20:06:57    => bt_c_test2
  Preference:     70
  Input filter:   ACCEPT
  Output filter:  ACCEPT
  Routes:         0 imported, 5 exported
  Route change stats:     received   rejected   filtered    ignored   accepted
    Import updates:             10         10          0          0          0
    Import withdraws:            5          0        ---          0          0
    Export updates:             10          0          0          0         10
    Export withdraws:            5          0        ---          0          5

up_2_65002 BGP      bt_up2   up     20:07:01    Established
  Description:    upstream2
  Preference:     100
  Input filter:   ACCEPT
  Output filter:  (unnamed)
  Routes:         5 imported, 0 exported, 20 preferred
  Route change stats:     received   rejected   filtered    ignored   accepted
    Import updates:              5          0          0          0          5
    Import withdraws:            0          0        ---          0          0
    Export updates:              5          5          0        ---          0
    Export withdraws:            0        ---        ---        ---          0
  BGP state:          Established
    Neighbor address: 10.100.0.122
    Neighbor AS:      65002
    Neighbor ID:      10.100.0.122
    Neighbor caps:    refresh enhanced-refresh restart-aware AS4 add-path-rx
    Session:          external AS4
    Source address:   10.100.0.100
    Hold timer:       148/240
    Keepalive timer:  62/80

bt_mux_up2 Pipe     mux      up     20:06:57    => bt_up2
  Preference:     70
  Input filter:   (unnamed)
  Output filter:  (unnamed)
  Routes:         5 imported, 0 exported
  Route change stats:     received   rejected   filtered    ignored   accepted
    Import updates:              5          0          0          0          5
    Import withdraws:            0          0        ---          0          0
    Export updates:             10          5          5          0          0
    Export withdraws:            5          0        ---          5          0

up_1_65001 BGP      bt_up1   down   00:19:22
  Description:    upstream1
  Preference:     100
  Input filter:   ACCEPT
  Output filter:  (unnamed)
  BGP state:          Down
    Neighbor address: 10.100.0.121
    Neighbor AS:      65001

bt_mux_up1 Pipe     mux      up     20:06:57    => bt_up1
  Preference:     70
  Input filter:   (unnamed)
  Output filter:  (unnamed)
  Routes:         0 imported, 0 exported
  Route change stats:     received   rejected   filtered    ignored   accepted
    Import updates:              5          0          0          0          5
    Import withdraws:            5          0        ---          0          5
    Export updates:             10          5          5          0          0
    Export withdraws:            5          0        ---          0          0

'''
        sio = cStringIO.StringIO(string)
        reader = cblr.CachingBufferedLineReader(sio)
        data = parse.show_protocols(reader, self.devnull)
        self.assertEquals(2, len(data))
        for bgp in data:
            self.assertTrue(bgp['details'])
            if bgp['name'] == 'up_1_65001':
                self.assertEquals(bgp['details']['bgp']['BGP state'], 'Down')
            if bgp['name'] == 'up_2_65002':
                self.assertEquals(bgp['details']['route_change_stats']['Import updates']['received'], '5')
        # sys.stdout.write(json.dumps(data, indent=2))
    # }}}

    def test_ParseSimpleRoutes1(self):  # {{{
        string = '''184.164.240.0/24   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
184.164.241.0/24   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
184.164.242.0/24   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
184.164.243.0/24   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
184.164.246.0/24   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
'''
        sio = cStringIO.StringIO(string)
        reader = cblr.CachingBufferedLineReader(sio)
        data = parse.show_route(reader, self.devnull, True)
        self.assertEquals(5, len(data))
        for rt in data:
            self.assertEquals(rt['via'], 'via 10.100.0.122 on eth1')
            self.assertEquals(rt['proto'], 'up_2_65002')
            self.assertEquals(rt['since'], '20:07:01')
            self.assertEquals(rt['primary'], '*')
            self.assertEquals(rt['info'], '(100) [AS65002i]')
        # sys.stdout.write(json.dumps(data, indent=2))
    # }}}

    def test_ParseComplexRoutes1(self):  # {{{
        string = '''184.164.240.0/24   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
        Type: BGP unicast univ
        BGP.origin: IGP
        BGP.as_path: 65002
        BGP.next_hop: 10.100.0.122
        BGP.local_pref: 100
184.164.241.0/24   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
        Type: BGP unicast univ
        BGP.origin: IGP
        BGP.as_path: 65002
        BGP.next_hop: 10.100.0.122
        BGP.local_pref: 100
184.164.242.0/24   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
        Type: BGP unicast univ
        BGP.origin: IGP
        BGP.as_path: 65002
        BGP.next_hop: 10.100.0.122
        BGP.local_pref: 100
184.164.243.0/24   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
        Type: BGP unicast univ
        BGP.origin: IGP
        BGP.as_path: 65002
        BGP.next_hop: 10.100.0.122
        BGP.local_pref: 100
184.164.246.0/24   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
        Type: BGP unicast univ
        BGP.origin: IGP
        BGP.as_path: 65002
        BGP.next_hop: 10.100.0.122
        BGP.local_pref: 100
'''
        sio = cStringIO.StringIO(string)
        reader = cblr.CachingBufferedLineReader(sio)
        data = parse.show_route(reader, self.devnull, True)
        self.assertEquals(5, len(data))
        for rt in data:
            self.assertEquals(rt['via'], 'via 10.100.0.122 on eth1')
            self.assertEquals(rt['proto'], 'up_2_65002')
            self.assertEquals(rt['since'], '20:07:01')
            self.assertEquals(rt['primary'], '*')
            self.assertEquals(rt['info'], '(100) [AS65002i]')
            self.assertEquals(len(rt['attributes']), 5)
        # sys.stdout.write(json.dumps(data, indent=2))
    # }}}

    def test_ParseComplexRoutes2(self):  # {{{
        string = '''184.164.240.0/24   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
        Type: BGP unicast univ
        BGP.origin: IGP
        BGP.as_path: 65002
        BGP.next_hop: 10.100.0.122
        BGP.local_pref: 100
                   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
        Type: BGP unicast univ
        BGP.origin: IGP
        BGP.as_path: 65002
        BGP.next_hop: 10.100.0.122
        BGP.local_pref: 100
184.164.242.0/24   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
        Type: BGP unicast univ
        BGP.origin: IGP
        BGP.as_path: 65002
        BGP.next_hop: 10.100.0.122
        BGP.local_pref: 100
184.164.243.0/24   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
        Type: BGP unicast univ
        BGP.origin: IGP
        BGP.as_path: 65002
        BGP.next_hop: 10.100.0.122
        BGP.local_pref: 100
184.164.246.0/24   via 10.100.0.122 on eth1 [up_2_65002 20:07:01] * (100) [AS65002i]
        Type: BGP unicast univ
        BGP.origin: IGP
        BGP.as_path: 65002
        BGP.next_hop: 10.100.0.122
        BGP.local_pref: 100
'''
        sio = cStringIO.StringIO(string)
        reader = cblr.CachingBufferedLineReader(sio)
        data = parse.show_route(reader, self.devnull, True)
        self.assertEquals(5, len(data))
        for rt in data:
            sys.stdout.write('%s' % rt)
            self.assertEquals(rt['via'], 'via 10.100.0.122 on eth1')
            self.assertEquals(rt['proto'], 'up_2_65002')
            self.assertEquals(rt['since'], '20:07:01')
            self.assertEquals(rt['primary'], '*')
            self.assertEquals(rt['info'], '(100) [AS65002i]')
            self.assertEquals(len(rt['attributes']), 5)
        # sys.stdout.write(json.dumps(data, indent=2))
    # }}}



if __name__ == '__main__':
    def initlog(basename, loglevel):  # {{{
        handler = logging.handlers.RotatingFileHandler(basename,
                                                       maxBytes=128*1024*1024,
                                                       backupCount=4)
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger = logging.getLogger()
        logger.setLevel(loglevel)
        logger.addHandler(handler)
    # }}}

    initlog('tests.log', logging.WARN)
    logging.info('starting run %f (%s)', time.time(), time.ctime())

    unittest.main()
