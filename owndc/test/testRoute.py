#!/usr/bin/env python

import sys
import os
import unittest

# here = os.path.dirname(__file__)
# sys.path.append(os.path.join(here, '..'))

from owndc.routing.routeutils.unittestTools import WITestRunner
from owndc.routing.routeutils.utils import RoutingCache
from owndc.routing.routeutils.utils import RequestMerge
from owndc.routing.routeutils.utils import Stream
from owndc.routing.routeutils.utils import TW


class RouteCacheTests(unittest.TestCase):
    """Test the functionality of routing.py

    """

    numTestsRun = 0

    @classmethod
    def setUp(cls):
        "Setting up test"
        cls.numTestsRun += 1
        if hasattr(cls, 'rc'):
            return
        cls.rc = RoutingCache('./test-owndc-routes.xml',
                              './test-masterTable.xml',
                              './test-owndc.cfg')

    @classmethod
    def tearDown(cls):
        "Removing cache and log files"
        if cls.numTestsRun == 7:
            os.remove('./test-owndc-routes.xml.bin')


    def testDS_GE(self):
        "route for GE.*.*.*"

        expURL = 'http://geofon.gfz-potsdam.de/fdsnws/dataselect/1/query'
        result = self.rc.getRoute(Stream('GE', '*', '*', '*'), TW(None, None))
        self.assertIsInstance(result, RequestMerge,
                              'A RequestMerge object was expected!')
        self.assertEqual(len(result), 1,
                         'Wrong number of data centers for GE.*.*.*!')
        self.assertEqual(result[0]['url'], expURL,
                         'Wrong URL for GE.*.*.*')
        self.assertEqual(result[0]['name'], 'dataselect',
                         'Wrong service name!')

    def testDS_GE_RO(self):
        "route for GE.RO.*.*.*"

        expURL_GE = 'http://geofon.gfz-potsdam.de/fdsnws/dataselect/1/query'
        expURL_RO = 'http://eida-sc3.infp.ro/fdsnws/dataselect/1/query'

        result = self.rc.getRoute(Stream('GE', '*', '*', '*'), TW(None, None))
        result.extend(self.rc.getRoute(Stream('RO', '*', '*', '*'), TW(None, None)))
        self.assertIsInstance(result, RequestMerge,
                              'A RequestMerge object was expected!')
        self.assertEqual(len(result), 2,
                         'Wrong number of data centers for GE,RO.*.*.*!')
        self.assertEqual(result[0]['url'], expURL_GE,
                         'Wrong URL for GE.*.*.*')
        self.assertEqual(result[0]['name'], 'dataselect',
                         'Wrong service name!')
        self.assertEqual(result[1]['url'], expURL_RO,
                         'Wrong URL for RO.*.*.*')
        self.assertEqual(result[1]['name'], 'dataselect',
                         'Wrong service name!')

    def testDS_GE_APE(self):
        "route for GE.APE.*.*"

        expURL = 'http://geofon.gfz-potsdam.de/fdsnws/dataselect/1/query'
        result = self.rc.getRoute(Stream('GE', 'APE', '*', '*'), TW(None, None))
        self.assertIsInstance(result, RequestMerge,
                              'A RequestMerge object was expected!')
        self.assertEqual(len(result), 1,
                         'Wrong number of data centers for GE.APE.*.*!')
        self.assertEqual(result[0]['url'], expURL,
                         'Wrong URL for GE.APE.*.*!')
        self.assertEqual(result[0]['name'], 'dataselect',
                         'Wrong service name!')

    def testDS_CH_LIENZ_HHZ(self):
        "route for CH.LIENZ.*.HHZ"

        expURL = 'http://eida.ethz.ch/fdsnws/dataselect/1/query'
        result = self.rc.getRoute(Stream('CH', 'LIENZ', '*', 'HHZ'), TW(None, None))
        self.assertIsInstance(result, RequestMerge,
                              'A RequestMerge object was expected!')
        self.assertEqual(len(result), 1,
                         'Wrong number of data centers for CH.LIENZ.*.HHZ!')
        self.assertEqual(result[0]['url'], expURL,
                         'Wrong URL for CH.LIENZ.*.HHZ!')
        self.assertEqual(result[0]['name'], 'dataselect',
                         'Wrong service name!')

    def testDS_CH_LIENZ_BHZ(self):
        "route for CH.LIENZ.*.BHZ"

        expURL = 'http://eida.ethz.ch/fdsnws/dataselect/1/query'
        result = self.rc.getRoute(Stream('CH', 'LIENZ', '*', 'BHZ'), TW(None, None))
        self.assertIsInstance(result, RequestMerge,
                              'A RequestMerge object was expected!')
        self.assertEqual(len(result), 1,
                         'Wrong number of data centers for CH.LIENZ.*.BHZ!')
        self.assertEqual(result[0]['url'], expURL,
                         'Wrong URL for CH.LIENZ.*.BHZ!')
        self.assertEqual(result[0]['name'], 'dataselect',
                         'Wrong service name!')

    def testDS_CH_LIENZ_qHZ(self):
        "route for CH.LIENZ.*.?HZ"

        ethURL = 'http://eida.ethz.ch/fdsnws/dataselect/1/query'
        result = self.rc.getRoute(Stream('CH', 'LIENZ', '*', '?HZ'), TW(None, None))
        self.assertIsInstance(result, RequestMerge,
                              'A RequestMerge object was expected!')
        self.assertEqual(len(result), 1,
                         'Wrong number of data centers for CH.LIENZ.*.?HZ!')

        for res in result:
            if 'eth' in res['url']:
                self.assertEqual(res['url'], ethURL,
                                 'Wrong URL for CH.LIENZ.*.?HZ!')
                self.assertEqual(res['name'], 'dataselect',
                                 'Wrong service name!')

            else:
                self.assertEqual(1, 0,
                                 'None of the URLs belong to ETH!')

    def testDS_RO_BZS_BHZ(self):
        "route for RO.BZS.*.BHZ"

        expURL = 'http://eida-sc3.infp.ro/fdsnws/dataselect/1/query'
        result = self.rc.getRoute(Stream('RO', 'BZS', '*', 'BHZ'), TW(None, None))
        self.assertIsInstance(result, RequestMerge,
                              'A RequestMerge object was expected!')
        self.assertEqual(len(result), 1,
                         'Wrong number of data centers for RO.BZS.*.BHZ!')
        self.assertEqual(result[0]['url'], expURL,
                         'Wrong URL for RO.BZS.*.BHZ!')
        self.assertEqual(result[0]['name'], 'dataselect',
                         'Wrong service name!')


# ----------------------------------------------------------------------
def usage():
    print 'testRoute [-h] [-p]'


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(RouteCacheTests)


if __name__ == '__main__':

    # 0=Plain mode (good for printing); 1=Colourful mode
    mode = 1

    for ind, arg in enumerate(sys.argv):
        if arg in ('-p', '--plain'):
            del sys.argv[ind]
            mode = 0
        elif arg in ('-h', '--help'):
            usage()
            sys.exit(0)

    unittest.main(testRunner=WITestRunner(mode=mode))
