#!/usr/bin/env python3
#
# OwnDC - An FDSN-WS compliant Virtual Datacentre prototype
#
# (c) 2015 Javier Quinteros, GEOFON team
# <javier@gfz-potsdam.de>
#
# ----------------------------------------------------------------------


"""OwnDC - An FDSN-WS compliant Virtual Datacentre prototype

   :Platform:
       Linux
   :Copyright:
       GEOFON, GFZ Potsdam <geofon@gfz-potsdam.de>
   :License:
       To be decided!

.. moduleauthor:: Javier Quinteros <javier@gfz-potsdam.de>, GEOFON, GFZ Potsdam
"""

import sys
import datetime
import logging
import urllib.request as ul
import configparser
sys.path.add('./routing')
from routeutils.wsgicomm import WIClientError
from routeutils.wsgicomm import WIContentError
from routeutils.utils import Stream
from routeutils.utils import TW
from routeutils.utils import RoutingCache
from routeutils.utils import RoutingException
from routeutils.routing import applyFormat
from routeutils.routing import lsNSLC
from routeutils.utils import str2date


class ResultFile(object):
    """Define a class that is an iterable. We can start returning the file
    before everything was retrieved from the sources."""

    def __init__(self, urlList, log=None):
        self.urlList = urlList
        self.content_type = 'application/vnd.fdsn.mseed'
        now = datetime.datetime.now()
        nowStr = '%04d%02d%02d-%02d%02d%02d' % (now.year, now.month, now.day,
                                                now.hour, now.minute,
                                                now.second)

        # FIXME The filename prefix should be read from the configuration
        self.filename = 'OwnDC-%s.mseed' % nowStr

        # Set the logging properties
        if log is not None:
            self.log = log
        else:
            self.log = logging

    def __iter__(self):
        """
        Read a maximum of 25 blocks of 4k (or 200 of 512b) each time.
        This will allow us to use threads and multiplex records from
        different sources.
        """

        blockSize = 25 * 4096

        status = ''

        for pos, url in enumerate(self.urlList):
            # Prepare Request
            self.log.debug('%s/%s - Connecting %s' % (pos, len(self.urlList), url))
            req = ul.Request(url)

            totalBytes = 0
            httpErr = 0
            # Connect to the proper FDSN-WS
            try:
                u = ul.urlopen(req)
                self.log.debug('%s/%s - Connected to %s' % (pos, len(self.urlList), url))

                # Read the data in blocks of predefined size
                try:
                    buffer = u.read(blockSize)
                except:
                    self.log.error('Oops!')

                while len(buffer):
                    totalBytes += len(buffer)
                    # Return one block of data
                    yield buffer
                    try:
                        buffer = u.read(blockSize)
                    except:
                        self.log.error('Oops!')
                    self.log.debug('%s/%s - %s bytes from %s' %
                                   (pos, len(self.urlList), totalBytes, url))

                httpErr = u.getcode()

                # Close the connection to avoid overloading the server
                self.log.info('%s/%s - %s bytes from %s' %
                              (pos, len(self.urlList), totalBytes, url))
                u.close()

            except ul.URLError as e:
                if hasattr(e, 'reason'):
                    self.log.error('%s - Reason: %s' % (url, e.reason))
                elif hasattr(e, 'code'):
                    self.log.error('The server couldn\'t fulfill the request')
                    self.log.error('Error code: %s' % e.code)

                if hasattr(e, 'code'):
                    httpErr = e.code
            except Exception as e:
                self.log.error('%s' % e)

        raise StopIteration


class DataSelectQuery(object):
    def __init__(self, routesFile='./data/routing.xml',
                 masterFile='./data/masterTable.xml', configFile='routing.cfg',
                 log=None):
        # Dataselect version
        self.version = '1.1.0'

        # Read the verbosity setting
        configP = configparser.RawConfigParser()
        configP.read(configFile)

        self.routes = RoutingCache(routesFile, masterFile, configFile)

        self.ID = str(datetime.datetime.now())

        # Set the logging properties
        if log is not None:
            self.log = log
        else:
            self.log = logging

    def makeQueryPOST(self, lines):

        urlList = []
        for line in lines.split('\n'):
            # Skip empty lines
            if not len(line):
                continue

            try:
                net, sta, loc, cha, start, endt = line.split(' ')
            except:
                logging.error('Cannot parse line: %s' % line)
                continue

            # Empty location
            if loc == '--':
                loc = ''

            try:
                start = str2date(start)
            except:
                self.log.error('Cannot convert "starttime" parameter (%s).'
                               % start)
                continue

            try:
                endt = str2date(endt)
            except:
                self.log.error('Cannot convert "endtime" parameter (%s).'
                               % endt)
                continue

            try:
                st = Stream(net, sta, loc, cha)
                tw = TW(start, endt)
                fdsnws = self.routes.getRoute(st, tw, 'dataselect')
                urlList.extend(applyFormat(fdsnws, 'get').splitlines())

            except RoutingException:
                self.log.warning('No route could be found for %s' % line)
                continue

        if not len(urlList):
            raise WIContentError('No routes have been found!')

        iterObj = ResultFile(urlList)
        return iterObj

    def makeQueryGET(self, parameters):
        # List all the accepted parameters
        allowedParams = ['net', 'network',
                         'sta', 'station',
                         'loc', 'location',
                         'cha', 'channel',
                         'start', 'starttime',
                         'end', 'endtime',
                         'user']

        for param in parameters:
            if param not in allowedParams:
                # return 'Unknown parameter: %s' % param
                raise WIClientError('Unknown parameter: %s' % param)

        try:
            if 'network' in parameters:
                net = parameters['network'].value.upper()
            elif 'net' in parameters:
                net = parameters['net'].value.upper()
            else:
                net = '*'
            net = net.split(',')
        except:
            net = ['*']

        try:
            if 'station' in parameters:
                sta = parameters['station'].value.upper()
            elif 'sta' in parameters:
                sta = parameters['sta'].value.upper()
            else:
                sta = '*'
            sta = sta.split(',')
        except:
            sta = ['*']

        try:
            if 'location' in parameters:
                loc = parameters['location'].value.upper()
            elif 'loc' in parameters:
                loc = parameters['loc'].value.upper()
            else:
                loc = '*'
            loc = loc.split(',')
        except:
            loc = ['*']

        try:
            if 'channel' in parameters:
                cha = parameters['channel'].value.upper()
            elif 'cha' in parameters:
                cha = parameters['cha'].value.upper()
            else:
                cha = '*'
            cha = cha.split(',')
        except:
            cha = ['*']

        try:
            if 'starttime' in parameters:
                start = str2date(parameters['starttime'].value.upper())
            elif 'start' in parameters:
                start = str2date(parameters['start'].value.upper())
            else:
                raise Exception
        except:
            raise WIClientError('Error while converting starttime parameter.')

        try:
            if 'endtime' in parameters:
                endt = str2date(parameters['endtime'].value.upper())
            elif 'end' in parameters:
                endt = str2date(parameters['end'].value.upper())
            else:
                raise Exception
        except:
            raise WIClientError('Error while converting endtime parameter.')

        urlList = []

        for (n, s, l, c) in lsNSLC(net, sta, loc, cha):
            try:
                st = Stream(n, s, l, c)
                tw = TW(start, endt)
                fdsnws = self.routes.getRoute(st, tw, 'dataselect')
                urlList.extend(applyFormat(fdsnws, 'get').splitlines())

            except RoutingException:
                pass

        if not len(urlList):
            raise WIContentError('No routes have been found!')

        iterObj = ResultFile(urlList)
        return iterObj
