#!/usr/bin/env python
#
# FDSN-WS Dataselect prototype
#
# Begun by Javier Quinteros, GEOFON team, February 2014
# <javier@gfz-potsdam.de>
#
# ----------------------------------------------------------------------


"""FDSN-WS Dataselect prototype

(c) 2014 GEOFON, GFZ Potsdam

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2, or (at your option) any later
version. For more information, see http://www.gnu.org/

"""

import cgi
import datetime
import urllib2
import struct

# SC3 stuff
import seiscomp3.System
import seiscomp3.Config
import seiscomp3.Logging

from seiscomp import logs
import seiscomp.mseedlite
from wsgicomm import *
from inventorycache import InventoryCache
from routing import RoutingCache

# Verbosity level a la SeisComP logging.level: 1=ERROR, ... 4=DEBUG
# (global parameters, settable in wsgi file)
verbosity = 3
syslog_facility = 'local0'

# Maximum size of POST data, in bytes? Or roubles?
cgi.maxlen = 1000000

##################################################################

sdsRoot = '/iso_sds'


def getRecords(net, sta, loc, cha, startt, endt):
    """Retrieve records from an SDS archive. The start and end dates must be
    in the same day for this test. This can be later improved."""

    if ((startt.year != endt.year) or (startt.month != endt.month) or
       (startt.day != endt.day)):
        print "Error: Start and end dates should be in the same day."
        return None

    # Take into account the case of empty location
    if loc == '--':
        loc = ''

    # For every file that contains information to be retrieved
    try:
        with open('%s/%d/%s/%s/%s.D/.%s.%s.%s.%s.D.%d.%s.idx' %
                  (sdsRoot, startt.year, net, sta, cha, net, sta, loc, cha,
                   startt.year, startt.strftime('%j')),
                  'rb') as idxFile:
            buffer = idxFile.read(100000)

            with open('%s/%d/%s/%s/%s.D/%s.%s.%s.%s.D.%d.%s' %
                      (sdsRoot, startt.year, net, sta, cha, net, sta, loc, cha,
                       startt.year, startt.strftime('%j')),
                      'rb') as msFile:
                # Read the baseline for time from the first record
                rec = msFile.read(512)
                msrec = seiscomp.mseedlite.Record(rec)
                basetime = msrec.begin_time

                # Float number that we search for in the index
                # THIS IS ONLY TO FIND THE STARTING POINT
                searchFor = (startt - basetime).total_seconds()

                recStart = 0
                recEnd = int(len(buffer) / 4) - 1

                timeStart = struct.unpack('f', buffer[recStart * 4:
                                                      (recStart + 1) * 4])[0]
                timeEnd = struct.unpack('f', buffer[recEnd * 4:
                                                    (recEnd + 1) * 4])[0]

                recHalf = recStart + int((recEnd - recStart) / 2.0)
                timeHalf = struct.unpack('f', buffer[recHalf * 4:
                                                     (recHalf + 1) * 4])[0]

                if searchFor <= timeStart:
                    recEnd = recStart
                if searchFor >= timeEnd:
                    recStart = recEnd

                while (recEnd - recStart) > 1:
                    if searchFor > timeHalf:
                        recStart = recHalf
                    else:
                        recEnd = recHalf
                    recHalf = recStart + int((recEnd - recStart) / 2.0)
                    # Calculate time
                    timeStart = struct.unpack('f',
                                              buffer[recStart * 4:
                                                     (recStart + 1) * 4])[0]
                    timeEnd = struct.unpack('f', buffer[recEnd * 4:
                                                        (recEnd + 1) * 4])[0]
                    timeHalf = struct.unpack('f', buffer[recHalf * 4:
                                                         (recHalf + 1) * 4])[0]
                    # print searchFor, timeStart, timeHalf, timeEnd

                lower = recStart

                # Float number that we search for in the index
                # THIS IS ONLY TO FIND THE END POINT
                searchFor = (endt - basetime).total_seconds()

                recStart = 0
                recEnd = int(len(buffer) / 4) - 1

                timeStart = struct.unpack('f', buffer[recStart * 4:
                                                      (recStart + 1) * 4])[0]
                timeEnd = struct.unpack('f', buffer[recEnd * 4:
                                                    (recEnd + 1) * 4])[0]

                recHalf = recStart + int((recEnd - recStart) / 2.0)
                timeHalf = struct.unpack('f', buffer[recHalf * 4:
                                                     (recHalf + 1) * 4])[0]

                if searchFor <= timeStart:
                    recEnd = recStart
                if searchFor >= timeEnd:
                    recStart = recEnd

                while (recEnd - recStart) > 1:
                    if searchFor > timeHalf:
                        recStart = recHalf
                    else:
                        recEnd = recHalf
                    recHalf = recStart + int((recEnd - recStart) / 2.0)
                    # Calculate time
                    timeStart = struct.unpack('f',
                                              buffer[recStart * 4:
                                                     (recStart + 1) * 4])[0]
                    timeEnd = struct.unpack('f', buffer[recEnd * 4:
                                                        (recEnd + 1) * 4])[0]
                    timeHalf = struct.unpack('f', buffer[recHalf * 4:
                                                         (recHalf + 1) * 4])[0]
                    # print searchFor, timeStart, timeHalf, timeEnd

                upper = recEnd
                # Now I have a pointer to the record I want (recStart)
                # and another one (recEnd) to the record where I should stop
                msFile.seek(lower * 512)
                return msFile.read((upper - lower + 1) * 512)

    except:
        return None

class ResultFile(object):
    """Define a class that is an iterable. We can start returning the file
    before everything was retrieved from the sources."""

    def __init__(self, urlList):
        self.urlList = urlList
        self.content_type = 'application/vnd.fdsn.mseed'
        self.filename = 'eidaws.mseed'

    def __iter__(self):
        blockSize = 100 * 1024

        for pos, url in enumerate(self.urlList):
            # Check if the data should be searched locally at the SDS archive
            if url[:4] != 'http':
                params = url.split()

                try:
                    startParts = params[4].replace('-', ' ').replace('T', ' ')
                    startParts = startParts.replace(':', ' ').replace('.', ' ')
                    startParts = startParts.replace('Z', '').split()
                    params[4] = datetime.datetime(*map(int, startParts))
                except:
                    print 'Error while converting START parameter.'

                try:
                    endParts = params[5].replace('-', ' ').replace('T', ' ')
                    endParts = endParts.replace(':', ' ').replace('.', ' ')
                    endParts = endParts.replace('Z', '').split()
                    params[5] = datetime.datetime(*map(int, endParts))
                except:
                    print 'Error while converting END parameter.'

                buffer = getRecords(*params)
                if buffer is not None:
                    yield buffer
                continue

            # Prepare Request
            req = urllib2.Request(url)

            # Connect to the proper FDSN-WS
            try:
                u = urllib2.urlopen(req)

                # Read the data in blocks of predefined size
                buffer = u.read(blockSize)
                while len(buffer):
                    print '%d / %d - (%s) Buffer: %s bytes' \
                            % (pos, len(self.urlList), url.split('?')[1],
                               len(buffer))
                    # Return one block of data
                    yield buffer
                    buffer = u.read(blockSize)

                # Close the connection to avoid overloading the server
                u.close()

            except urllib2.URLError as e:
                if hasattr(e, 'reason'):
                    print '%s - Reason: %s' % (url, e.reason)
                elif hasattr(e, 'code'):
                    print 'The server couldn\'t fulfill the request.'
                    print 'Error code: ', e.code

        raise StopIteration


class DataSelectQuery(object):
    def __init__(self, appName, dataPath):
        # initialize SC3 environment
        env = seiscomp3.System.Environment_Instance()

        # set up logging
        self.__syslog = seiscomp3.Logging.SyslogOutput()
        self.__syslog.open(appName, syslog_facility)

        for (v, c) in ((1, "error"), (2, "warning"), (2, "notice"),
                       (3, "info"), (4, "debug")):
            if verbosity >= v:
                self.__syslog.subscribe(seiscomp3.Logging.getGlobalChannel(c))

        logs.debug = seiscomp3.Logging.debug
        logs.info = seiscomp3.Logging.info
        logs.notice = seiscomp3.Logging.notice
        logs.warning = seiscomp3.Logging.warning
        logs.error = seiscomp3.Logging.error

        logs.notice("Starting EIDA Dataselect Web Service")

        # load SC3 config files from all standard locations (SEISCOMP_ROOT
        # must be set)
        self.__cfg = seiscomp3.Config.Config()
        env.initConfig(self.__cfg, appName, env.CS_FIRST, env.CS_LAST, True)

        # Add inventory cache here, to be accessible to all modules
        inventory = dataPath + '/Arclink-inventory.xml'
        self.ic = InventoryCache(inventory)

        # Add routing cache here, to be accessible to all modules
        routesFile = dataPath + '/routing.xml'
        self.routes = RoutingCache(routesFile)

        self.ID = str(datetime.datetime.now())

        logs.debug(str(self))

    def makeQueryPOST(self, lines):

        urlList = []
        for line in lines.split('\n'):
            # Skip empty lines
            if not len(line):
                continue

            try:
                net, sta, loc, cha, start, endt = line.split(' ')
            except:
                continue

            # Empty location
            if loc == '--':
                loc = ''

            try:
                startParts = start.replace('-', ' ').replace('T', ' ').replace(':', ' ').replace('.', ' ').replace('Z', '').split()
                start = datetime.datetime(*map(int, startParts))
            except:
                return 'Error while converting starttime parameter.'

            try:
                endParts = endt.replace('-', ' ').replace('T', ' ').replace(':', ' ').replace('.', ' ').replace('Z', '').split()
                endt = datetime.datetime(*map(int, endParts))
            except:
                return 'Error while converting starttime parameter.'

            for reqLine in self.ic.expand(net, sta, loc, cha, start, endt):
                n, s, l, c = reqLine
                auxRoute = self.routes.getRoute(n, s, l, c)[1]

                fdsnws = None
                if auxRoute == 'GFZ':
                    fdsnws = 'http://geofon.gfz-potsdam.de/fdsnws/dataselect/1/query'
                elif auxRoute == 'ODC':
                    fdsnws = 'http://www.orfeus-eu.org/fdsnws/dataselect/1/query'
                elif auxRoute == 'ETH':
                    fdsnws = 'http://eida.ethz.ch/fdsnws/dataselect/1/query'
                elif auxRoute == 'RESIF':
                    fdsnws = 'http://ws.resif.fr/fdsnws/dataselect/1/query'

                url = fdsnws + '?network=' + n
                url += '&station=' + s
                if len(l):
                    url += '&location=' + l
                url += '&channel=' + c
                url += '&starttime=' + start.strftime('%Y-%m-%dT%H:%M:%S')
                url += '&endtime=' + endt.strftime('%Y-%m-%dT%H:%M:%S')

                urlList.append(url)

        iterObj = ResultFile(urlList)
        return iterObj


    def makeQueryGET(self, parameters):
        # List all the accepted parameters
        allowedParams = ['net', 'network',
                         'sta', 'station',
                         'loc', 'location',
                         'cha', 'channel',
                         'start', 'starttime',
                         'end', 'endtime']

        for param in parameters:
            if param not in allowedParams:
                return 'Unknown parameter: %s' % param

        try:
            if 'network' in parameters:
                net = parameters['network'].value
            elif 'net' in parameters:
                net = parameters['net'].value
            else:
                net = '*'
        except:
            net = '*'

        try:
            if 'station' in parameters:
                sta = parameters['station'].value
            elif 'sta' in parameters:
                sta = parameters['sta'].value
            else:
                sta = '*'
        except:
            sta = '*'

        try:
            if 'location' in parameters:
                loc = parameters['location'].value
            elif 'loc' in parameters:
                loc = parameters['loc'].value
            else:
                loc = '*'
        except:
            loc = '*'

        try:
            if 'channel' in parameters:
                cha = parameters['channel'].value
            elif 'cha' in parameters:
                cha = parameters['cha'].value
            else:
                cha = '*'
        except:
            cha = '*'

        try:
            if 'starttime' in parameters:
                start = datetime.datetime.strptime(
                    parameters['starttime'].value,
                    '%Y-%m-%dT%H:%M:%S')
            elif 'start' in parameters:
                start = datetime.datetime.strptime(
                    parameters['start'].value,
                    '%Y-%m-%dT%H:%M:%S')
            else:
                raise Exception
        except:
            return 'Error while converting starttime parameter.'

        try:
            if 'endtime' in parameters:
                endt = datetime.datetime.strptime(
                    parameters['endtime'].value,
                    '%Y-%m-%dT%H:%M:%S')
            elif 'end' in parameters:
                endt = datetime.datetime.strptime(
                    parameters['end'].value,
                    '%Y-%m-%dT%H:%M:%S')
            else:
                raise Exception
        except:
            return 'Error while converting endtime parameter.'

        urlList = []
        for reqLine in self.ic.expand(net, sta, loc, cha, start, endt):
            n, s, l, c = reqLine
            auxRoute = self.routes.getRoute(n, s, l, c)[1]

            if n == 'GE' and start.year == 2014:

                # Empty location case
                if l == '':
                    l = '--'

                urlList.append('%s %s %s %s %s %s' %
                               (n, s, l, c,
                                start.strftime('%Y-%m-%dT%H:%M:%S'),
                                endt.strftime('%Y-%m-%dT%H:%M:%S')))
                continue

            fdsnws = None
            if auxRoute == 'GFZ':
                fdsnws = 'http://geofon.gfz-potsdam.de/fdsnws/dataselect/1/query'
            elif auxRoute == 'ODC':
                fdsnws = 'http://www.orfeus-eu.org/fdsnws/dataselect/1/query'
            elif auxRoute == 'ETH':
                fdsnws = 'http://eida.ethz.ch/fdsnws/dataselect/1/query'
            elif auxRoute == 'RESIF':
                fdsnws = 'http://ws.resif.fr/fdsnws/dataselect/1/query'

            url = fdsnws + '?network=' + n
            url += '&station=' + s
            if len(l):
                url += '&location=' + l
            url += '&channel=' + c
            url += '&starttime=' + start.strftime('%Y-%m-%dT%H:%M:%S')
            url += '&endtime=' + endt.strftime('%Y-%m-%dT%H:%M:%S')

            urlList.append(url)

        iterObj = ResultFile(urlList)
        return iterObj


##################################################################
#
# Initialization of variables used inside the module
#
##################################################################

wi = DataSelectQuery('EIDA FDSN-WS', '/var/www/fdsnws/dataselect/')


def application(environ, start_response):
    """Main WSGI handler that processes client requests and calls
    the proper functions.

    Begun by Javier Quinteros <javier@gfz-potsdam.de>,
    GEOFON team, February 2014

    """

    # Read the URI and save the first word in fname
    #fname = environ['PATH_INFO'].split("/")[-1]
    #fname = environ['PATH_INFO'].lstrip('/').split("/")[0]
    #print "environ['PATH_INFO'].lstrip('/')", environ['PATH_INFO'].lstrip('/')

    fname = environ['PATH_INFO']

    logs.debug('fname: %s' % (fname))

    # Among others, this will filter wrong function names,
    # but also the favicon.ico request, for instance.
    if fname is None:
        return send_html_response(status, 'Error! ' + status, start_response)

    try:
        if environ['REQUEST_METHOD'] == 'GET':
            form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)
        elif environ['REQUEST_METHOD'] == 'POST':
            form = ''
            try:
                length = int(environ.get('CONTENT_LENGTH', '0'))
            except ValueError:
                length = 0
            # If there is a body to read
            if length != 0:
                form = environ['wsgi.input'].read(length)
            else:
                form = environ['wsgi.input'].read()

        else:
            raise Exception

    except ValueError, e:
        if str(e) == "Maximum content length exceeded":
            # Add some user-friendliness (this message triggers an alert
            # box on the client)
            return send_plain_response("400 Bad Request",
                                       "maximum request size exceeded",
                                       start_response)

        return send_plain_response("400 Bad Request", str(e), start_response)

    # Check whether the function called is implemented
    implementedFunctions = ['query', 'application.wadl']

    fname = environ['PATH_INFO'].split('/')[-1]
    if fname not in implementedFunctions:
        return send_plain_response("400 Bad Request",
                                   'Function "%s" not implemented.' % fname,
                                   start_response)

    if fname == 'application.wadl':
        iterObj = ''
        with open('/var/www/fdsnws/dataselect/application.wadl', 'r') as appFile:
            iterObj = appFile.read()
            status = '200 OK'
            return send_xml_response(status, iterObj, start_response)

    elif fname == 'query':
        makeQuery = getattr(wi, 'makeQuery%s' % environ['REQUEST_METHOD'])
        iterObj = makeQuery(form)

    if isinstance(iterObj, basestring):
        status = '200 OK'
        return send_plain_response(status, iterObj, start_response)

    elif isinstance(iterObj, ResultFile):
        status = '200 OK'
        return send_dynamicfile_response(status, iterObj, start_response)

    elif hasattr(iterObj, 'filename'):
        status = '200 OK'
        return send_file_response(status, iterObj, start_response)

    status = '200 OK'
    body = "\n".join(iterObj)
    return send_plain_response(status, body, start_response)
