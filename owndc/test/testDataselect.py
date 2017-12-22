#!/usr/bin/env python

import sys
import os

# here = os.path.dirname(__file__)
# sys.path.append(os.path.join(here, '..'))

import unittest
from owndc.routing.routeutils.unittestTools import WITestRunner
from owndc.owndc import FakeStorage
from owndc.owndc import DataSelectQuery
from owndc.routing.routeutils.wsgicomm import WIClientError
from owndc.routing.routeutils.wsgicomm import WIContentError

class DataselectTests(unittest.TestCase):
    """Test the functionality of owndc.py

    """

    numTestsRun = 0

    @classmethod
    def setUp(cls):
        "Setting up test"
        cls.host = host
        cls.numTestsRun += 1
        if hasattr(cls, 'ds'):
            return

        cls.ds = DataSelectQuery('./test-owndc-routes.xml',
                                 './test-masterTable.xml',
                                 configFile='./test-owndc.cfg')

    @classmethod
    def tearDown(cls):
        "Removing cache and log files"
        if cls.numTestsRun == 4:
            # os.remove('./owndc-test.log')
            os.remove('./test-owndc-routes.xml.bin')

    def testDS_GE(self):
        "Dataselect GE.APE.*.*"

        params = dict()
        params['net'] = FakeStorage('GE')
        params['sta'] = FakeStorage('APE')
        params['start'] = FakeStorage('2008-01-01T00:01:00')
        params['end'] = FakeStorage('2008-01-01T00:01:15')

        iterObj = self.ds.makeQueryGET(params)
        lenData = 0
        for chunk in iterObj:
            lenData += len(chunk)

        numRecords = (18, 25)

        msg = 'Error in size of response! Expected a multiple of 512, but obtained: %d'
        self.assertEqual(lenData/512.0, int(lenData/512.0), msg % lenData)

        msg = 'Error in number of records! Expected records within the range: %s, but obtained %s'
        self.assertIn(int(lenData / 512.0), range(*numRecords), msg % (numRecords, int(lenData/512)))

    def testDS_RO_POST(self):
        "Dataselect via POST method with RO.ARR,VOIR.--.BHZ"

        postReq = """RO ARR -- BHZ 2015-03-07T14:39:36.0000 2015-03-07T15:09:36.0000
RO VOIR -- BHZ 2015-07-07T14:48:47.0000 2015-07-07T15:18:47.0000"""

        iterObj = self.ds.makeQueryPOST(postReq)
        lenData = 0
        for chunk in iterObj:
            lenData += len(chunk)

        numRecords = (140, 155)

        msg = 'Error in size of response! Expected a multiple of 512, but obtained: %d'
        self.assertEqual(lenData/512.0, int(lenData/512.0), msg % lenData)

        msg = 'Error in number of records! Expected records within the range: %s, but obtained %s'
        self.assertIn(int(lenData / 512.0), range(*numRecords), msg % (numRecords, int(lenData/512)))

    def testDS_XX(self):
        "Unknown network XX"

        params = dict()
        params['net'] = FakeStorage('XX')
        params['start'] = FakeStorage('2008-01-01T00:01:00')
        params['end'] = FakeStorage('2008-01-01T00:01:15')

        self.assertRaises(WIContentError, self.ds.makeQueryGET, params)

    def testDS_wrongStart(self):
        "wrong starttime"

        params = dict()
        params['net'] = FakeStorage('XX')
        params['start'] = FakeStorage('9999-99-99T99:99:99')
        params['end'] = FakeStorage('2008-01-01T00:01:15')

        self.assertRaises(WIClientError, self.ds.makeQueryGET, params)

    def testDS_wrongEnd(self):
        "wrong endtime"

        params = dict()
        params['net'] = FakeStorage('XX')
        params['start'] = FakeStorage('2008-01-01T00:01:15')
        params['end'] = FakeStorage('9999-99-99T99:99:99')

        self.assertRaises(WIClientError, self.ds.makeQueryGET, params)

    def testDS_unknownparam(self):
        "Unknown parameter"

        params = dict()
        params['unknown'] = FakeStorage('unknown')
        params['start'] = FakeStorage('2008-01-01T00:01:00')
        params['end'] = FakeStorage('2008-01-01T00:01:15')

        self.assertRaises(WIClientError, self.ds.makeQueryGET, params)

# ----------------------------------------------------------------------
def usage():
    print 'testDataselect [-h] [-p]'

global host

host = 'http://localhost:7000/fdsnws/dataselect/1/query'


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(DataselectTests)


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
