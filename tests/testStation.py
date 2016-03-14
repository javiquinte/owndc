#!/usr/bin/env python

import sys
import datetime
import unittest
import urllib2
from unittestTools import WITestRunner
from xml.dom.minidom import parseString


class OwnDCTests(unittest.TestCase):
    """Test the functionality of the station-WS of ownDC.py

    """

    @classmethod
    def setUp(cls):
        "Setting up test"
        cls.host = host

    def test_long_URI(self):
        "very large URI"

        msg = 'A URI of more than 2000 characters is not allowed and should ' +\
            'return a 414 erro code'
        req = urllib2.Request('%s?net=GE%s' % (self.host, '&net=GE' * 500))
        try:
            u = urllib2.urlopen(req)
            u.read()
        except urllib2.URLError as e:
            self.assertEqual(e.code, 414, msg)
            return

        self.assertTrue(False, msg)
        return

    def test_wrong_parameter(self):
        "unknown parameter"

        msg = 'An error code 400 Bad Request is expected for an unknown ' + \
            'parameter'
        req = urllib2.Request('%s?net=GE&wrongparam=1' % self.host)
        try:
            u = urllib2.urlopen(req)
            u.read()
        except urllib2.URLError as e:
            self.assertEqual(e.code, 400, msg)
            return

        self.assertTrue(False, msg)
        return

    def testST_XX(self):
        "non-existing network XX"

        req = urllib2.Request('%s?net=XX' % self.host)
        msg = 'An error code 204 No Content is expected for an unknown network'
        try:
            u = urllib2.urlopen(req)
            u.read()
            self.assertEqual(u.getcode(), 204, '%s (%s)' % (msg, u.getcode()))
            return
        except urllib2.URLError as e:
            if hasattr(e, 'code'):
                self.assertEqual(e.code, 204, '%s (%s)' % (msg, e.code))
                return
            else:
                self.assertTrue(False, '%s (%s)' % (msg, e))
                return

        except Exception as e:
            self.assertTrue(False, '%s (%s)' % (msg, e))
            return

        self.assertTrue(False, msg)
        return

    def test_wrong_datetime(self):
        "swap start and end time"

        d1 = datetime.datetime(2004, 1, 1)
        d2 = d1 - datetime.timedelta(days=1)
        req = urllib2.Request('%s?net=GE&start=%s&end=%s' % (self.host,
                                                             d1.isoformat(),
                                                             d2.isoformat()))
        msg = 'When starttime > endtime an error code 400 is expected!'
        try:
            u = urllib2.urlopen(req)
            u.read()
        except urllib2.URLError as e:
            self.assertEqual(e.code, 400, msg)
            return

        self.assertTrue(False, msg)
        return

    def test_application_wadl(self):
        "the 'application.wadl' method"

        if self.host.endswith('query'):
            appmethod = '%sapplication.wadl' % self.host[:-len('query')]
        else:
            pass

        req = urllib2.Request(appmethod)
        try:
            u = urllib2.urlopen(req)
            buffer = u.read()
        except:
            msg = 'Error calling the "application.wadl" method'
            self.assertTrue(False, msg)

        msg = 'The "application.wadl" method returned an empty string'
        self.assertGreater(len(buffer), 0, msg)
        msg = 'The file returned by "application.wadl" does not contain a "<"'
        self.assertIn('<', buffer, msg)

        # Check that the returned value is a valid xml file
        msg = 'Error "application.wadl" method does not return a valid xml file'
        try:
            parseString(buffer)
        except:
            self.assertTrue(False, msg)

    def test_version(self):
        "the 'version' method"

        if self.host.endswith('query'):
            vermethod = '%sversion' % self.host[:-len('query')]
        else:
            pass

        req = urllib2.Request(vermethod)
        try:
            u = urllib2.urlopen(req)
            buffer = u.read()
        except:
            raise Exception('Error retrieving version number')

        # Check that it has three components (ints) separated by '.'
        components = buffer.split('.')
        msg = 'Version number does not include the three components'
        self.assertEqual(len(components), 3, msg)

        try:
            components = map(int, components)
        except ValueError:
            msg = 'Components of the version number seem not to be integers.'
            self.assertEqual(1, 0, msg)

    def testST_GE_net(self):
        "Station-WS data for GE.*.*.* at network level"

        qry = 'net=GE&level=network'
        req = urllib2.Request('%s?%s' % (self.host, qry))
        try:
            u = urllib2.urlopen(req)
            buffer = u.read()
        except:
            raise Exception('Error retrieving data for GE.*.*.*')

        # FIXME How would be the best way to test?
        # Probably parsing
        posNet = buffer.find('<Network')
        self.assertGreaterEqual(0, posNet)
        posCode = buffer.find('code="GE"', posNet)
        self.assertGreaterEqual(0, posCode)
        posClose = buffer.find('</Network', posCode)
        self.assertGreaterEqual(0, posClose)

    def testST_GE_APE_sta(self):
        "Station-WS data for GE.APE.*.* at station level"

        qry = 'net=GE&sta=APE&level=station'
        req = urllib2.Request('%s?%s' % (self.host, qry))
        try:
            u = urllib2.urlopen(req)
            buffer = u.read()
        except:
            raise Exception('Error retrieving data for GE.APE.*.*')

        # FIXME How would be the best way to test?
        # Probably parsing
        posNet = buffer.find('<Network')
        self.assertGreaterEqual(0, posNet)
        posCode = buffer.find('code="GE"', posNet)
        self.assertGreaterEqual(0, posCode)
        posSta = buffer.find('<Station', posCode)
        self.assertGreaterEqual(0, posSta)
        posStaCode = buffer.find('code="APE"', posSta)
        self.assertGreaterEqual(0, posStaCode)
        posStaClose = buffer.find('</Station', posStaCode)
        self.assertGreaterEqual(0, posStaClose)
        posClose = buffer.find('</Network', posStaClose)
        self.assertGreaterEqual(0, posClose)

    def testST_GE_APE_BHZ_cha(self):
        "Station-WS data for GE.APE.*.BHZ at channel level"

        qry = 'net=GE&sta=APE&cha=BHZ&level=channel'
        req = urllib2.Request('%s?%s' % (self.host, qry))
        try:
            u = urllib2.urlopen(req)
            buffer = u.read()
        except:
            raise Exception('Error retrieving data for GE.APE.*.BHZ')

        # FIXME How would be the best way to test?
        # Probably parsing
        posNet = buffer.find('<Network')
        self.assertGreaterEqual(0, posNet)
        posCode = buffer.find('code="GE"', posNet)
        self.assertGreaterEqual(0, posCode)
        posSta = buffer.find('<Station', posCode)
        self.assertGreaterEqual(0, posSta)
        posStaCode = buffer.find('code="APE"', posSta)
        self.assertGreaterEqual(0, posStaCode)
        posCha = buffer.find('<Channel', posStaCode)
        self.assertGreaterEqual(0, posCha)
        posChaCode = buffer.find('code="BHZ"', posCha)
        self.assertGreaterEqual(0, posChaCode)
        posChaClose = buffer.find('</Channel', posChaCode)
        self.assertGreaterEqual(0, posChaClose)
        posStaClose = buffer.find('</Station', posChaClose)
        self.assertGreaterEqual(0, posStaClose)
        posClose = buffer.find('</Network', posStaClose)
        self.assertGreaterEqual(0, posClose)

    def testST_GE_APE_BHZ_resp(self):
        "Station-WS data for GE.APE.*.BHZ at response level"

        qry = 'net=GE&sta=APE&cha=BHZ&level=response'
        req = urllib2.Request('%s?%s' % (self.host, qry))
        try:
            u = urllib2.urlopen(req)
            buffer = u.read()
        except:
            raise Exception('Error retrieving data for GE.APE.*.BHZ')

        # FIXME How would be the best way to test?
        # Probably parsing
        posNet = buffer.find('<Network')
        self.assertGreaterEqual(0, posNet)
        posCode = buffer.find('code="GE"', posNet)
        self.assertGreaterEqual(0, posCode)
        posSta = buffer.find('<Station', posCode)
        self.assertGreaterEqual(0, posSta)
        posStaCode = buffer.find('code="APE"', posSta)
        self.assertGreaterEqual(0, posStaCode)
        posCha = buffer.find('<Channel', posStaCode)
        self.assertGreaterEqual(0, posCha)
        posChaCode = buffer.find('code="BHZ"', posCha)
        self.assertGreaterEqual(0, posChaCode)
        posResp = buffer.find('<Response', posChaCode)
        self.assertGreaterEqual(0, posResp)
        posRespClose = buffer.find('</Response', posResp)
        self.assertGreaterEqual(0, posRespClose)
        posChaClose = buffer.find('</Channel', posRespClose)
        self.assertGreaterEqual(0, posChaClose)
        posStaClose = buffer.find('</Station', posChaClose)
        self.assertGreaterEqual(0, posStaClose)
        posClose = buffer.find('</Network', posStaClose)
        self.assertGreaterEqual(0, posClose)

    def testST_GE_POST(self):
        "Dataselect for GE.APE,APEZ.--.BHZ"

        postReq = """GE APE -- BHZ 2015-01-01T00:00:00.0000 2015-02-01T00:00:00.0000
GE APEZ -- BHZ 2015-01-01T00:00:00.0000 2015-02-01T00:00:00.0000"""

        req = urllib2.Request(self.host, postReq)
        try:
            u = urllib2.urlopen(req)
            buffer = u.read()
        except:
            raise Exception('Error retrieving data for GE.APE,APEZ.--.BHZ')

        expLen = 75264

        msg = 'Error in size of response! Expected: %d ; Obtained: %d'
        self.assertEqual(len(buffer), expLen, msg % (expLen, len(buffer)))


def usage():
    print 'testService [-h] [-p]\ntestService [-u http://server/path]'

global host

host = 'http://localhost:7000/fdsnws/station/1/query'

if __name__ == '__main__':

    # 0=Plain mode (good for printing); 1=Colourful mode
    mode = 1

    # The default host is localhost
    for ind, arg in enumerate(sys.argv):
        if arg in ('-p', '--plain'):
            del sys.argv[ind]
            mode = 0
        elif arg == '-u':
            host = sys.argv[ind + 1]
            del sys.argv[ind + 1]
            del sys.argv[ind]
        elif arg in ('-h', '--help'):
            usage()
            sys.exit(0)

    unittest.main(testRunner=WITestRunner(mode=mode))
