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

# SC3 stuff
import seiscomp3.System
import seiscomp3.Config
import seiscomp3.Logging

from seiscomp import logs
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
            # Prepare Request
            req = urllib2.Request(url)

            # Connect to the proper FDSN-WS
            try:
                u = urllib2.urlopen(req)

                # Read the data in blocks of predefined size
                buffer = u.read(blockSize)
                while len(buffer):
                    print '%d / %d - (%s) Buffer: %s bytes' % (pos,
                                                         len(self.urlList),
                                                         url.split('?')[1],
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

        logs.notice("Starting EIDA webinterface")

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

    def makeQuery(self, parameters):
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
            print reqLine
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

            url = fdsnws + '?network=' + n + '&station=' + s + \
                '&location=' + l + '&channel=' + c + '&starttime=' + \
                parameters['starttime'].value + \
                '&endtime=' + parameters['endtime'].value

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
        form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)

    except ValueError, e:
        if str(e) == "Maximum content length exceeded":
            # Add some user-friendliness (this message triggers an alert
            # box on the client)
            return send_plain_response("400 Bad Request",
                                       "maximum request size exceeded",
                                       start_response)

        return send_plain_response("400 Bad Request", str(e), start_response)

    if environ['PATH_INFO'].split('/')[-1] != 'query':
        return send_plain_response("400 Bad Request",
                                   'Only the query function is supported',
                                   start_response)

    iterObj = wi.makeQuery(form)

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
    body = "\n".join(res_string)
    return send_plain_response(status, body, start_response)
