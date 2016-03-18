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

import glob
import os
import datetime
import fcntl
import smtplib
from email.mime.text import MIMEText
import logging
from collections import namedtuple
from wsgicomm import WIClientError
from wsgicomm import WIContentError
from utils import RoutingCache
from utils import RoutingException
from utils import text2Datetime
from routing import applyFormat
from routing import lsNSLC

# This try is needed to be Python3 compliant
try:
    import urllib.request as ul
except ImportError:
    import urllib2 as ul

try:
    import configparser
except ImportError:
    import ConfigParser as configparser


class LogEntry(namedtuple('LogEntry', ['dt', 'code', 'line', 'bytes'])):

    __slots__ = ()

    def __str__(self):
        return '%s %s %s %s' % self


# Wrap parsed values in the GET method with this class to mimic FieldStorage
# syntax and be compatible with underlying classes, which use ".value"
class FakeStorage(dict):
    def __init__(self, s=None):
        self.value = s

    def getvalue(self, k):
        return self[k]

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self.value)


class Accounting(object):
    """Receive information about all the requests and log it in a file disk
    or send it per Mail. This class is still being tested and debugged."""

    def __init__(self, logName):
        self.logName = logName
        self.lFD = open(logName, 'a')

    def log(self, le, user=None):
        fcntl.flock(self.lFD, fcntl.LOCK_EX)
        self.lFD.write('%s\n' % str(le))
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


class ResultStation(object):
    """Define a class that is an iterable. We can start returning data from the
    station web service ASAP."""

    def __init__(self, fileList):
        self.fileList = fileList
        self.content_type = 'text/xml'
        # now = datetime.datetime.now()
        # nowStr = '%04d%02d%02d-%02d%02d%02d' % (now.year, now.month, now.day,
        #                                         now.hour, now.minute,
        #                                         now.second)

        # I think that the returned XML does not need to be an attachment
        # self.filename = 'OwnDC-%s.xml' % nowStr

        self.logs = logging.getLogger('ResultStation')
        self.len = 0
        for fin in self.fileList:
            if fin[0] in (' ', '<'):
                self.len += len(fin)
            else:
                self.logs.debug('Checking size of %s' % fin)
                self.len += os.stat(fin).st_size

        print 'ResultStation created with length: %d' % self.len

    def __iter__(self):
        """
        Reads one file at a time and yield its content.
        """

        for pos, fin in enumerate(self.fileList):
            # Prepare Request
            self.logs.debug('%s/%s - Opening %s' % (pos, len(self.fileList),
                                                    fin))
            print '%s/%s - Opening %s' % (pos, len(self.fileList), fin)

            if fin[0] in ('<', ' '):
                yield fin
                continue

            with open(fin) as fh:

                # Read the data in blocks of predefined size
                try:
                    buffer = fh.read()
                    yield buffer
                except:
                    self.logs.error('Oops!')

        raise StopIteration


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

        # status = ''

        for pos, url in enumerate(self.urlList):
            # Prepare Request
            self.logs.debug('%s/%s - Connecting %s' % (pos, len(self.urlList),
                                                       url))
            req = ul.Request(url)

            totalBytes = 0
            httpErr = 0
            # Connect to the proper FDSN-WS
            try:
                u = ul.urlopen(req)
                self.logs.debug('%s/%s - Connected to %s' % (pos,
                                                             len(self.urlList),
                                                             url))

                # Read the data in blocks of predefined size
                try:
                    buffer = u.read(blockSize)
                except:
                    self.logs.error('Oops!')

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

                httpErr = u.getcode()

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
                le = LogEntry(datetime.datetime.now(), httpErr, url,
                              totalBytes)
                self.callback(le, self.user)

        # if self.callback is not None:
        #     self.callback(status, self.user)

        raise StopIteration


class DataSelectQuery(object):
    def __init__(self, logName=None, routesFile='./data/routing.xml',
                 masterFile='./data/masterTable.xml', configFile='routing.cfg'):
        # Dataselect version
        self.version = '1.1.0'

        # set up logging
        self.logs = logging.getLogger('DataSelectQuery')
        logging.basicConfig()

        # Read the verbosity setting
        configP = configparser.RawConfigParser()
        configP.read(configFile)

        verbo = configP.get('Service', 'verbosity')
        verboNum = getattr(logging, verbo.upper(), 30)
        self.logs.setLevel(verboNum)

        # Add routing cache here, to be accessible to all modules
        self.logs.info('Reading routes from %s' % routesFile)
        self.logs.info('Reading masterTable from %s' % masterFile)
        self.logs.info('Reading configuration from %s' % configFile)

        self.routes = RoutingCache(routesFile, masterFile, configFile)

        self.ID = str(datetime.datetime.now())

        if isinstance(logName, basestring):
            self.acc = Accounting(logName)
        elif logName is not None:
            self.acc = logName
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

    def makeQueryStationGET(self, parameters):
        # List all the accepted parameters
        allowedParams = ['net', 'network',
                         'sta', 'station',
                         'loc', 'location',
                         'cha', 'channel',
                         'start', 'starttime',
                         'end', 'endtime',
                         'level']

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

        logging.debug('Parameters %s' % parameters)

        try:
            if 'starttime' in parameters:
                start = text2Datetime(parameters['starttime'].value.upper())
            elif 'start' in parameters:
                start = text2Datetime(parameters['start'].value.upper())
            else:
                start = None
        except:
            raise WIClientError('Error while converting starttime parameter.')

        try:
            if 'endtime' in parameters:
                endt = text2Datetime(parameters['endtime'].value.upper())
            elif 'end' in parameters:
                endt = text2Datetime(parameters['end'].value.upper())
            else:
                endt = None
        except:
            raise WIClientError('Error while converting endtime parameter.')

        try:
            if 'level' in parameters:
                level = parameters['level'].value.lower()
            else:
                level = 'station'

            if level not in ('network', 'station', 'channel', 'response'):
                raise Exception
        except:
            raise WIClientError('Error while converting the "level" parameter.')

        if ((start is not None) and (endt is not None) and (start > endt)):
                raise WIClientError('Error! Start time greater than end time')

        fileList = []

        for (n, s, l, c) in lsNSLC(net, sta, loc, cha):
            logging.debug('%s.%s.%s.%s' % (n, s, l, c))

            for fXML in glob.glob('cache/%s.*.*.xml' % n):
                # Skip files that don't contain exclusively a network
                if fXML.count('.') != 3:
                    continue

                # First time filter based on the filename
                netStart = int(fXML.split('.')[1])
                netEnd = int(fXML.split('.')[2]) if fXML.split('.')[2] != \
                    'None' else datetime.datetime.now().year + 1
                queryStart = getattr(start, "year", 1900)
                queryEnd = getattr(endt, "year", 2100)
                if set(range(queryStart, queryEnd + 1)).isdisjoint(
                        set(range(netStart,
                                  getattr(netEnd, "year", 2099) + 1))):
                    continue

                # Process
                curNet = fXML[len('cache/'):fXML.find('.')]
                # curNet = curNet[:curNet.find('.')]
                fileList.append(fXML)

                if level == 'network':
                    fileList.append('</Network>')
                    continue

                # Searching for stations
                for fXML2 in glob.glob('cache/%s.%s.*.*.xml' % (curNet, s)):
                    if fXML2.count('.') != 4:
                        continue

                    logging.debug('Parsing station %s' % fXML2.split('.')[-4])
                    staStart = int(fXML2.split('.')[2])
                    staEnd = int(fXML2.split('.')[3]) if fXML2.split('.')[3] \
                        != 'None' else datetime.datetime.now().year + 1
                    if set(range(queryStart, queryEnd)).isdisjoint(
                            set(range(staStart, staEnd))):
                        continue

                    # print 'for station %s' % fXML
                    strStaCode = fXML2.find('.') + 1
                    curSta = fXML2[strStaCode:fXML2.find('.', strStaCode + 1)]
                    # curSta = curSta[:curSta.find('.')]
                    # Process
                    fileList.append(fXML2)

                    if level == 'station':
                        fileList.append('</Station>')
                        continue

                    # Searching for channels
                    for fXML3 in sorted(glob.glob('cache/%s.%s.%s.*.*.xml' %
                                                  (curNet, curSta, c))):
                        # Skip response files
                        if fXML3.count('.') != 5:
                            continue

                        chaStart = int(fXML3.split('.')[3])
                        chaEnd = int(fXML3.split('.')[4]) if \
                            fXML3.split('.')[4] != 'None' \
                            else datetime.datetime.now().year + 1
                        if set(range(queryStart, queryEnd + 1)).isdisjoint(
                                set(range(chaStart, chaEnd + 1))):
                            continue

                        curCha = fXML3.split('.')[-4]
                        # Include channel file
                        fileList.append(fXML3)

                        # If level == response include the response file
                        # Response is the only one that is already closed
                        # because is the lowest level
                        if level == 'response':
                            fXMLResp = 'cache/%s.%s.%s.resp.%s.%s.xml' % \
                                (curNet, curSta, curCha, chaStart,
                                 fXML3.split('.')[4])
                            fileList.append(fXMLResp)

                        fileList.append('</Channel>')

                    fileList.append('</Station>')

            if (len(fileList) and (level != "network")):
                fileList.append('</Network>')

        if not len(fileList):
            logging.debug('No data from Station-WS has been found!')
            raise WIContentError('No data from Station-WS has been found!')

        header = '<?xml version="1.0" encoding="UTF-8"?>' + \
            '<FDSNStationXML xmlns="http://www.fdsn.org/xml/station/1" ' + \
            'schemaVersion="1.0"><Source>OwnDC</Source>' + \
            '<Created>%s</Created>' % datetime.datetime.now().isoformat()
        fileList.insert(0, header)
        fileList.append('</FDSNStationXML>')

        # print fileList

        iterObj = ResultStation(fileList)
        return iterObj

    def makeQueryStationPOST(self, lines):

        # Default value for level
        level = 'station'
        urlList = []
        for line in lines.split('\n'):
            # Skip empty lines
            if not len(line):
                continue

            try:
                net, sta, loc, cha, start, endt = line.split(' ')
            except:
                try:
                    key, value = line.split('=')
                    if key.trim() != 'level':
                        raise Exception('')
                    if value.trim() not in ('network', 'station', 'channel',
                                            'response'):
                        raise Exception('')
                    level = value
                except:
                    logging.error('Cannot parse line: %s' % line)
                    continue

            # Empty location
            if loc == '--':
                loc = ''

            logging.debug('Calling makeQueryStationGET %s %s %s %s %s %s %s' %
                          (net, sta, loc, cha, start, endt, level))
            params = dict()
            params['net'] = FakeStorage(net)
            params['sta'] = FakeStorage(sta)
            params['loc'] = FakeStorage(loc)
            params['cha'] = FakeStorage(cha)
            params['start'] = FakeStorage(start)
            params['end'] = FakeStorage(endt)
            params['level'] = FakeStorage(level)
            iterObj = self.makeQueryStationGET(params)

        # if not len(urlList):
        #     raise WIContentError('No routes have been found!')

        # iterObj = ResultFile(urlList, self.acc.log if self.acc is not None
        #                      else None)
        return iterObj
