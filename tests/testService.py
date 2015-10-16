#!/usr/bin/env python

import sys
import unittest
import urllib2
from unittestTools import WITestRunner
from difflib import Differ


class OwnDCTests(unittest.TestCase):
    """Test the functionality of ownDC.py

    """

    @classmethod
    def setUp(cls):
        "Setting up test"
        cls.host = host

    def testDS_GE(self):
        "Dataselect for GE.APE.*.*"

        qry = 'net=GE&sta=APE&starttime=2008-01-01T00:01:00&end=2008-01-01T00:01:15'
        req = urllib2.Request('%s?%s' % (self.host, qry))
        try:
            u = urllib2.urlopen(req)
            buffer = u.read()
        except:
            raise Exception('Error retrieving data for GE.APE.*.*')

        expLen = 11776

        msg = 'Error in size of response! Expected: %d ; Obtained: %d'
        self.assertEqual(len(buffer), expLen, msg % (expLen, len(buffer)))

    def testDS_RO_POST(self):
        "Dataselect for RO.ARR,VOIR.--.BHZ"

        postReq = """RO ARR -- BHZ 2015-03-07T14:39:36.0000 2015-03-07T15:09:36.0000
RO VOIR -- BHZ 2015-07-07T14:48:47.0000 2015-07-07T15:18:47.0000"""

        req = urllib2.Request(self.host, postReq)
        try:
            u = urllib2.urlopen(req)
            buffer = u.read()
        except:
            raise Exception('Error retrieving data for RO.ARR,VOIR.--.BHZ')

        expLen = 75264

        msg = 'Error in size of response! Expected: %d ; Obtained: %d'
        self.assertEqual(len(buffer), expLen, msg % (expLen, len(buffer)))

# ----------------------------------------------------------------------
def usage():
    print 'testService [-h] [-p]\ntestService [-u http://server/path]'

global host

host = 'http://localhost:7000/fdsnws/dataselect/1/query'

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
