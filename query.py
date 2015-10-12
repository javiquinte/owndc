#!/usr/bin/env python
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

import os
import datetime
import fcntl
import smtplib
from email.mime.text import MIMEText

import logging
from wsgicomm import WIClientError
from wsgicomm import WIContentError
from utils import RoutingCache
from utils import RoutingException
from routing import applyFormat
from routing import lsNSLC

# These tries arre needed to be Python3 compliant
try:
    # 3.x name
    import configparser
except ImportError:
    # 2.x name
    import ConfigParser as configparser

try:
    import urllib.request as ul
except ImportError:
    import urllib2 as ul

# "WARNING" is the default value
#verboNum = getattr(logging, verbo.upper(), 30)
logging.basicConfig(level=30)

##################################################################


class Accounting(object):
    """Receive information about all the requests and log it in a file disk
    or send it per Mail. This class is still being tested and debugged."""

    def __init__(self, logName):
        self.logName = logName
        self.lFD = open(logName, 'a')

    def log(self, data, user=None):
        fcntl.flock(self.lFD, fcntl.LOCK_EX)
        self.lFD.write(data)
        self.lFD.flush()
        fcntl.flock(self.lFD, fcntl.LOCK_UN)

        # FIXME The username as well as the mail settings should be configured
        # in the general configuration file
        if user is not None:
            msg = MIMEText(data)
            msg['Subject'] = 'Feedback from OwnDC'
            msg['From'] = 'noreply@localhost'
            msg['To'] = user

            # Send the message via our own SMTP server, but don't include the
            # envelope header.
            s = smtplib.SMTP('localhost')
            s.sendmail('noreply@localhost', [user],
                       msg.as_string())
            s.quit()


class ResultFile(object):
    """Define a class that is an iterable. We can start returning the file
    before everything was retrieved from the sources."""

    def __init__(self, urlList, callback=None, user=None):
        self.urlList = urlList
        self.content_type = 'application/vnd.fdsn.mseed'
        now = datetime.datetime.now()
        nowStr = '%04d%02d%02d-%02d%02d%02d' % (now.year, now.month, now.day,
                                                now.hour, now.minute,
                                                now.second)

        # FIXME The filename prefix should be read from the configuration
        self.filename = 'OwnDC-%s.mseed' % nowStr

        self.logs = logging.getLogger('ResultFile')
        self.callback = callback
        self.user = user

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
            self.logs.debug('%s/%s - Connecting %s' % (pos, len(self.urlList), url))
            req = ul.Request(url)

            totalBytes = 0
            httpErr = 200
            # Connect to the proper FDSN-WS
            try:
                u = ul.urlopen(req)
                self.logs.debug('%s/%s - Connected to %s' % (pos, len(self.urlList), url))

                # Read the data in blocks of predefined size
                try:
                    buffer = u.read(blockSize)
                except:
                    self.logs.error('Oops!')

                if not len(buffer):
                    self.logs.error('Error code: %s' % u.getcode())
                    self.logs.error('Info: %s' % u.info())

                while len(buffer):
                    totalBytes += len(buffer)
                    # Return one block of data
                    yield buffer
                    try:
                        buffer = u.read(blockSize)
                    except:
                        self.logs.error('Oops!')
                    self.logs.debug('%s/%s - %s bytes from %s' % 
                                    (pos, len(self.urlList), totalBytes, url))

                # Close the connection to avoid overloading the server
                self.logs.info('%s/%s - %s bytes from %s' % 
                               (pos, len(self.urlList), totalBytes, url))
                u.close()

            except ul.URLError as e:
                if hasattr(e, 'reason'):
                    self.logs.error('%s - Reason: %s' % (url, e.reason))
                elif hasattr(e, 'code'):
                    self.logs.error('The server couldn\'t fulfill the request')
                    self.logs.error('Error code: %s' % e.code)

                if hasattr(e, 'code'):
                    httpErr = e.code
            except Exception as e:
                self.logs.error('%s' % e)

            if self.callback is not None:
                status += '%s %s %s %s\n' % \
                    (datetime.datetime.now().isoformat(), httpErr, url,
                     totalBytes)

        if self.callback is not None:
            self.callback(status, self.user)

        raise StopIteration


class DataSelectQuery(object):
    def __init__(self, logName=None, routesFile='./data/routing.xml',
                 masterFile='./data/masterTable.xml', configFile='routing.cfg'):
        # Dataselect version
        self.version = '1.1.0'

        # set up logging
        self.logs = logging.getLogger('DataSelectQuery')

        # Add routing cache here, to be accessible to all modules
        self.logs.info('Reading routes from %s' % routesFile)
        self.logs.info('Reading masterTable from %s' % masterFile)
        self.logs.info('Reading configuration from %s' % configFile)

        self.routes = RoutingCache(routesFile, masterFile, configFile)

        self.ID = str(datetime.datetime.now())

        if logName is not None:
            self.acc = Accounting(logName)
        else:
            self.acc = None

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
                startParts = start.replace('-', ' ').replace('T', ' ')
                startParts = startParts.replace(':', ' ').replace('.', ' ')
                startParts = startParts.replace('Z', '').split()
                start = datetime.datetime(*map(int, startParts))
            except:
                logging.error('Cannot convert "starttime" parameter (%s).'
                              % start)
                continue

            try:
                endParts = endt.replace('-', ' ').replace('T', ' ')
                endParts = endParts.replace(':', ' ').replace('.', ' ')
                endParts = endParts.replace('Z', '').split()
                endt = datetime.datetime(*map(int, endParts))
            except:
                logging.error('Cannot convert "endtime" parameter (%s).'
                              % endt)
                continue

            try:
                fdsnws = self.routes.getRoute(net, sta, loc, cha, start, endt,
                                              'dataselect')
                urlList.extend(applyFormat(fdsnws, 'get').splitlines())

            except RoutingException:
                logging.warning('No route could be found for %s' % line)
                continue

        if not len(urlList):
            raise WIContentError('No routes have been found!')

        iterObj = ResultFile(urlList, self.acc.log if self.acc is not None
                             else None)
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
                #return 'Unknown parameter: %s' % param
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
                start = datetime.datetime.strptime(
                    parameters['starttime'].value.upper(),
                    '%Y-%m-%dT%H:%M:%S')
            elif 'start' in parameters:
                start = datetime.datetime.strptime(
                    parameters['start'].value.upper(),
                    '%Y-%m-%dT%H:%M:%S')
            else:
                raise Exception
        except:
            raise WIClientError('Error while converting starttime parameter.')

        try:
            if 'endtime' in parameters:
                endt = datetime.datetime.strptime(
                    parameters['endtime'].value.upper(),
                    '%Y-%m-%dT%H:%M:%S')
            elif 'end' in parameters:
                endt = datetime.datetime.strptime(
                    parameters['end'].value.upper(),
                    '%Y-%m-%dT%H:%M:%S')
            else:
                raise Exception
        except:
            raise WIClientError('Error while converting endtime parameter.')

        try:
            if 'user' in parameters:
                user = parameters['user'].value
            else:
                user = None
        except:
            raise Exception('Error while checking the user parameter')

        urlList = []

        for (n, s, l, c) in lsNSLC(net, sta, loc, cha):
            try:
                fdsnws = self.routes.getRoute(n, s, l, c, start, endt,
                                              'dataselect')
                urlList.extend(applyFormat(fdsnws, 'get').splitlines())

            except RoutingException:
                pass

        if not len(urlList):
            raise WIContentError('No routes have been found!')

        iterObj = ResultFile(urlList, self.acc.log if self.acc is not None
                             else None, user)
        return iterObj
