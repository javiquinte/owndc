#!/usr/bin/env python

import sys
import datetime
import unittest
import urllib2
from xml.dom.minidom import parseString

# here = os.path.dirname(__file__)
# sys.path.append(os.path.join(here, '..'))

from owndc.routing.routeutils.unittestTools import WITestRunner


class OwnDCTests(unittest.TestCase):
    """Test the functionality of owndc.py

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

    def testDS_XX(self):
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
        "wrong datetime"

        d1 = datetime.datetime(2004, 1, 1)
        d2 = datetime.datetime(2004, 1, 2)
        req = urllib2.Request('%s?net=GE&start=%s&end=%s' % (self.host,
                                                             d1.isoformat() + 'A',
                                                             'A' + d2.isoformat()))
        msg = 'If a datetime format error occurs an HTTP 400 code is expected!'
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

    def testDS_GE(self):
        "Dataselect for GE.APE.*.*"

        qry = 'net=GE&sta=APE&starttime=2008-01-01T00:01:00&end=2008-01-01T00:01:15'
        req = urllib2.Request('%s?%s' % (self.host, qry))
        try:
            u = urllib2.urlopen(req)
            buffer = u.read()
            lenData = len(buffer)
        except:
            raise Exception('Error retrieving data for GE.APE.*.*')

        numRecords = (18, 25)

        msg = 'Error in size of response! Expected a multiple of 512, but obtained: %d'
        self.assertEqual(lenData/512.0, int(lenData/512.0), msg % lenData)

        msg = 'Error in number of records! Expected records within the range: %s, but obtained %s'
        self.assertIn(int(lenData / 512.0), range(*numRecords), msg % (numRecords, int(lenData/512)))

    def testDS_RO_POST(self):
        "Dataselect for RO.ARR,VOIR.--.BHZ"

        postReq = """RO ARR -- BHZ 2015-03-07T14:39:36.0000Z 2015-03-07T15:09:36.0000Z
RO VOIR -- BHZ 2015-07-07T14:48:47.0000Z 2015-07-07T15:18:47.0000Z"""

        req = urllib2.Request(self.host, postReq)
        req.add_header('Content-type', 'text/plain')
        try:
            u = urllib2.urlopen(req)
            buffer = u.read()
            lenData = len(buffer)
        except Exception as e:
            print(e)
            raise Exception('Error retrieving data for RO.ARR,VOIR.--.BHZ')

        numRecords = (140, 155)

        msg = 'Error in size of response! Expected a multiple of 512, but obtained: %d'
        self.assertEqual(lenData/512.0, int(lenData/512.0), msg % lenData)

        msg = 'Error in number of records! Expected records within the range: %s, but obtained %s'
        self.assertIn(int(lenData / 512.0), range(*numRecords), msg % (numRecords, int(lenData/512)))

# ----------------------------------------------------------------------
def usage():
    print 'testService [-h] [-p]\ntestService [-u http://server/path]'

global host

host = 'http://localhost:7000/fdsnws/dataselect/1/query'


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(OwnDCTests)


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
