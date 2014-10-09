#!/usr/bin/env python
#
# FDSN-WS Dataselect prototype
#
# (c) 2014 Javier Quinteros, GEOFON team
# <javier@gfz-potsdam.de>
#
# ----------------------------------------------------------------------


"""FDSN-WS Dataselect prototype

(c) 2014 Javier Quinteros, GEOFON, GFZ Potsdam

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2, or (at your option) any later
version. For more information, see http://www.gnu.org/

"""

import os
import sys
import cgi
import datetime
import urllib2

# SC3 stuff
import seiscomp3.System
import seiscomp3.Config
import seiscomp3.Logging

from seiscomp import logs
from wsgicomm import *
from inventorycache import InventoryCache
from routing import RoutingCache
from routing import applyFormat
from msIndex import IndexedSDS

# Verbosity level a la SeisComP logging.level: 1=ERROR, ... 4=DEBUG
# (global parameters, settable in wsgi file)
verbosity = 3
syslog_facility = 'local0'

# Maximum size of POST data, in bytes? Or roubles?
cgi.maxlen = 1000000

##################################################################


class ResultFile(object):
    """Define a class that is an iterable. We can start returning the file
    before everything was retrieved from the sources."""

    def __init__(self, urlList, iSDS=None):
        self.urlList = urlList
        self.iSDS = iSDS
        self.content_type = 'application/vnd.fdsn.mseed'
        now = datetime.datetime.now()
        nowStr = '%d%d%d-%d%d%d' % (now.year, now.month, now.day,
                                    now.hour, now.minute, now.second)
        self.filename = 'eidaws-%s.mseed' % nowStr

    def __iter__(self):
        # Read a maximum of 25 blocks of 4k (or 200 of 512b) each time
        # This will allow us to use threads and multiplex records from
        # different sources
        blockSize = 25 * 4096

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

                # Iterator over MS files. Final result is returned in chunks.
                for buffer in self.iSDS.getRawBytes(params[4], params[5],
                                                    params[0], params[1],
                                                    params[2], params[3]):
                    yield buffer
                continue

            # Prepare Request
            req = urllib2.Request(url)

            sys.stdout.write('\n%d / %d - (%s) Buffer: ' % (pos,
                                                            len(self.urlList),
                                                            url))
            # Connect to the proper FDSN-WS
            try:
                u = urllib2.urlopen(req)

                # Read the data in blocks of predefined size
                buffer = u.read(blockSize)
                if not len(buffer):
                    print 'Error code: ', u.getcode()
                    print 'Info: ', u.info()

                while len(buffer):
                    sys.stdout.write(' %d' % len(buffer))
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
            except Exception as e:
                print e

        raise StopIteration


class DataSelectQuery(object):
    def __init__(self, appName, sdsRoot=None, isoRoot=None,
                 idxRoot=None):
        if sdsRoot is not None and idxRoot is not None:
            self.iSDS = IndexedSDS(sdsRoot, isoRoot, idxRoot)

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
        here = os.path.dirname(__file__)
        inventory = os.path.join(here, 'Arclink-inventory.xml')
        self.ic = InventoryCache(inventory)

        # Add routing cache here, to be accessible to all modules
        routesFile = os.path.join(here, 'routing.xml')
        masterFile = os.path.join(here, 'masterTable.xml')
        self.routes = RoutingCache(routesFile, masterFile)

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
                startParts = start.replace('-', ' ').replace('T', ' ')
                startParts = startParts.replace(':', ' ').replace('.', ' ')
                startParts = startParts.replace('Z', '').split()
                start = datetime.datetime(*map(int, startParts))
            except:
                return 'Error while converting starttime parameter.'

            try:
                endParts = endt.replace('-', ' ').replace('T', ' ')
                endParts = endParts.replace(':', ' ').replace('.', ' ')
                endParts = endParts.replace('Z', '').split()
                endt = datetime.datetime(*map(int, endParts))
            except:
                return 'Error while converting starttime parameter.'

            for reqLine in self.ic.expand(net, sta, loc, cha, start, endt):
                n, s, l, c = reqLine
                fdsnws = self.routes.getRoute(n, s, l, c, start, endt,
                                              'dataselect')

                url = fdsnws[0] + '?network=' + n
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
                net = parameters['network'].value.upper()
            elif 'net' in parameters:
                net = parameters['net'].value.upper()
            else:
                net = '*'
        except:
            net = '*'

        try:
            if 'station' in parameters:
                sta = parameters['station'].value.upper()
            elif 'sta' in parameters:
                sta = parameters['sta'].value.upper()
            else:
                sta = '*'
        except:
            sta = '*'

        try:
            if 'location' in parameters:
                loc = parameters['location'].value.upper()
            elif 'loc' in parameters:
                loc = parameters['loc'].value.upper()
            else:
                loc = '*'
        except:
            loc = '*'

        try:
            if 'channel' in parameters:
                cha = parameters['channel'].value.upper()
            elif 'cha' in parameters:
                cha = parameters['cha'].value.upper()
            else:
                cha = '*'
        except:
            cha = '*'

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
            return 'Error while converting starttime parameter.'

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
            return 'Error while converting endtime parameter.'

        urlList = []

        for reqLine in self.ic.expand(net, sta, loc, cha, start, endt):
            n, s, l, c = reqLine
            fdsnws = self.routes.getRoute(n, s, l, c, start, endt,
                                          'dataselect')

            urlList.extend(applyFormat(fdsnws, 'get').splitlines())

        iterObj = ResultFile(urlList)
        return iterObj


##################################################################
#
# Initialization of variables used inside the module
#
##################################################################

wi = DataSelectQuery('EIDA FDSN-WS')


def application(environ, start_response):
    """Main WSGI handler that processes client requests and calls
    the proper functions.

    Begun by Javier Quinteros <javier@gfz-potsdam.de>,
    GEOFON team, February 2014

    """

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
        here = os.path.dirname(__file__)
        with open(os.path.join(here, 'application.wadl'), 'r') \
                as appFile:
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
