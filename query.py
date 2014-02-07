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

# JSON (since Python 2.6)
import json

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

        logs.debug(str(self))

    def makeQuery(self, parameters):
        try:
            net = parameters['network'].value
        except:
            net = '*'

        try:
            sta = parameters['station'].value
        except:
            sta = '*'

        try:
            loc = parameters['location'].value
        except:
            loc = '*'

        try:
            cha = parameters['channel'].value
        except:
            cha = '*'

        try:
            start = datetime.datetime.strptime(
                parameters['starttime'].value,
                '%Y-%m-%dT%H:%M:%S')
        except:
            return 'Error while converting starttime parameter.'

        try:
            endt = datetime.datetime.strptime(
                parameters['endtime'].value,
                '%Y-%m-%dT%H:%M:%S')
        except:
            return 'Error while converting endtime parameter.'

        res_string = []
        for reqLine in self.ic.expand(net, sta, loc, cha, start, endt):
            n, s, l, c = reqLine
            auxRoute = self.routes.getRoute(n, s, l, c)[1]

            fdsnws = None
            if auxRoute == 'GFZ':
                fdsnws = 'http://geofon.gfz-potsdam.de/fdsnws/dataselect/1/query'

            url = fdsnws + '?net=' + n + '&sta=' + s + \
                    '&loc=' + l + '&cha=' + c + '&start=' + \
                    parameters['starttime'].value + \
                    '&end=' + parameters['endtime'].value
            u = urllib2.urlopen(url)
            f = open('/tmp/nada.ms', 'wb')
            block_sz = 1024 * 1024
            buffer = u.read(block_sz)
            if buffer:
                f.write(buffer)
                break
            f.close()

            res_string.append(url)

        return res_string

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

    res_string = wi.makeQuery(form)

    body = []

    # body.extend(["%s: %s" % (key, value)
    #     for key, value in environ.iteritems()])

    # status = '200 OK'
    # return send_plain_response(status, body, start_response)

    if isinstance(res_string, basestring):
        status = '200 OK'
        body = res_string
        return send_plain_response(status, body, start_response)

    elif hasattr(res_string, 'filename'):
        status = '200 OK'
        body = res_string
        return send_file_response(status, body, start_response)

    status = '200 OK'
    body = "\n".join(res_string)
    return send_plain_response(status, body, start_response)
