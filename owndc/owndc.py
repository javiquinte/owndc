#!/usr/bin/env python2
# owndc: An FDSN Virtual Datacentre for SeisComP3
#
# (c) 2015-2017 Javier Quinteros, GEOFON team
# <javier@gfz-potsdam.de>
#
# ----------------------------------------------------------------------


"""owndc: An FDSN-WS Virtual Data Centre for SeisComP3

   :Platform:
       Linux
   :Copyright:
       GEOFON, GFZ Potsdam <geofon@gfz-potsdam.de>
   :License:
       To be decided!

.. moduleauthor:: Javier Quinteros <javier@gfz-potsdam.de>, GEOFON, GFZ Potsdam
"""

import os
import cherrypy
import json
import argparse
import logging
import logging.config
import ConfigParser as configparser
import datetime
import urllib2 as ul

from cherrypy.process import plugins
from routing.routeutils.wsgicomm import WIError
from routing.routeutils.wsgicomm import WIClientError
from routing.routeutils.wsgicomm import WIContentError
from routing.routeutils.utils import Stream
from routing.routeutils.utils import TW
from routing.routeutils.utils import RoutingCache
from routing.routeutils.utils import RoutingException
from routing.routeutils.routing import applyFormat
from routing.routeutils.routing import lsNSLC
from routing.routeutils.utils import str2date

# Version of this software
version = '0.9.1a1'

# Dataselect version of this software
dsversion = '1.1.0'

global dsq

# Logging configuration (hardcoded!)
LOG_CONF = {
    'version': 1,

    'formatters': {
        'void': {
            'format': ''
        },
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level':'DEBUG',
            'class':'logging.StreamHandler',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout'
        },
        'owndclog': {
            'level':'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'standard',
            'filename': os.path.join(os.path.expanduser('~'), '.owndc', 'owndc.log'),
            'maxBytes': 10485760,
            'backupCount': 20,
            'encoding': 'utf8'
        },
        'cherrypy_access': {
            'level':'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'standard',
            'filename': os.path.join(os.path.expanduser('~'), '.owndc', 'access.log'),
            'maxBytes': 10485760,
            'backupCount': 20,
            'encoding': 'utf8'
        },
        'cherrypy_error': {
            'level':'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'standard',
            'filename': os.path.join(os.path.expanduser('~'), '.owndc', 'errors.log'),
            'maxBytes': 10485760,
            'backupCount': 20,
            'encoding': 'utf8'
        },
    },
    'loggers': {
        'main': {
            'handlers': ['owndclog'],
            'level': 'INFO'
        },
        'ResultFile': {
            'handlers': ['owndclog'],
            'level': 'INFO' ,
            'propagate': False
        },
        'DataSelectQuery': {
            'handlers': ['owndclog'],
            'level': 'INFO',
            'propagate': False
        },
        'Application': {
            'handlers': ['owndclog'],
            'level': 'INFO',
            'propagate': False
        },
        'cherrypy.access': {
            'handlers': ['cherrypy_access'],
            'level': 'INFO',
            'propagate': False
        },
        'cherrypy.error': {
            'handlers': ['cherrypy_error'],
            'level': 'INFO',
            'propagate': False
        },
    }
}

class ResultFile(object):
    """Define a class that is an iterable. We can start returning the file
    before everything was retrieved from the sources."""

    def __init__(self, urlList):
        self.log = logging.getLogger('ResultFile')
        self.urlList = urlList
        self.content_type = 'application/vnd.fdsn.mseed'
        now = datetime.datetime.now()
        nowStr = '%04d%02d%02d-%02d%02d%02d' % (now.year, now.month, now.day,
                                                now.hour, now.minute,
                                                now.second)

        self.filename = 'owndc-%s.mseed' % nowStr

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
                    self.log.error('Error reading data from %s!' % url)

                while len(buffer):
                    totalBytes += len(buffer)
                    # Return one block of data
                    yield buffer
                    try:
                        buffer = u.read(blockSize)
                    except:
                        self.log.error('Error reading data from %s!' % url)
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
    def __init__(self, routesFile=None, masterFile=None,
                 configFile=None):
        self.log = logging.getLogger('DataSelectQuery')
        if routesFile is None:
            routesFile = os.path.join(os.path.expanduser('~'), '.owndc', 'data', 'owndc-routes.xml')

        if masterFile is None:
            masterFile = os.path.join(os.path.expanduser('~'), '.owndc', 'data', 'masterTable.xml')

        if configFile is None:
            configFile = os.path.join(os.path.expanduser('~'), '.owndc', 'owndc.cfg')

        # Dataselect version
        self.version = '1.1.0'

        self.log.debug('Creating Routing Cache.')
        self.routes = RoutingCache(routesFile, masterFile, configFile)

        self.ID = str(datetime.datetime.now())

    def makeQueryPOST(self, lines):
        self.log.debug('Query with POST method and body:\n%s' % lines)
        urlList = []
        for line in lines.split('\n'):
            # Skip empty lines
            if not len(line):
                continue

            try:
                net, sta, loc, cha, start, endt = line.split(' ')
            except:
                self.log.error('Cannot parse line: %s' % line)
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
                self.log.debug('Retrieve routes for %s %s' % (st, tw))
                fdsnws = self.routes.getRoute(st, tw, 'dataselect')
                urlList.extend(applyFormat(fdsnws, 'get').splitlines())

            except RoutingException:
                self.log.warning('No route could be found for %s' % line)
                continue

        if not len(urlList):
            self.log.debug('No routes found!')
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

        self.log.debug('Query with GET method and parameters:\n%s' % parameters)
        for param in parameters:
            if param not in allowedParams:
                # return 'Unknown parameter: %s' % param
                self.log.error('Unknown parameter: %s' % param)
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
            self.log.error('Network could not be parsed!')
            raise WIClientError('Network could not be parsed!')

        try:
            if 'station' in parameters:
                sta = parameters['station'].value.upper()
            elif 'sta' in parameters:
                sta = parameters['sta'].value.upper()
            else:
                sta = '*'
            sta = sta.split(',')
        except:
            self.log.error('Station could not be parsed!')
            raise WIClientError('Station could not be parsed!')

        try:
            if 'location' in parameters:
                loc = parameters['location'].value.upper()
            elif 'loc' in parameters:
                loc = parameters['loc'].value.upper()
            else:
                loc = '*'
            loc = loc.split(',')
        except:
            self.log.error('Location could not be parsed!')
            raise WIClientError('Location could not be parsed!')

        try:
            if 'channel' in parameters:
                cha = parameters['channel'].value.upper()
            elif 'cha' in parameters:
                cha = parameters['cha'].value.upper()
            else:
                cha = '*'
            cha = cha.split(',')
        except:
            self.log.error('Channel could not be parsed!')
            raise WIClientError('Channel could not be parsed!')

        try:
            if 'starttime' in parameters:
                start = str2date(parameters['starttime'].value.upper())
            elif 'start' in parameters:
                start = str2date(parameters['start'].value.upper())
            else:
                start = None
        except:
            self.log.error('Error while converting starttime parameter.')
            raise WIClientError('Error while converting starttime parameter.')

        try:
            if 'endtime' in parameters:
                endt = str2date(parameters['endtime'].value.upper())
            elif 'end' in parameters:
                endt = str2date(parameters['end'].value.upper())
            else:
                endt = None
        except:
            self.log.error('Error while converting endtime parameter.')
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
            self.log.debug('No routes found!')
            raise WIContentError('No routes have been found!')

        iterObj = ResultFile(urlList)
        return iterObj


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


# Application class
class Application(object):
    def __init__(self):
        self.log = logging.getLogger('Application')

    @cherrypy.expose
    def index(self):
        self.log.debug('Showing owndc help page.')
        cherrypy.response.headers['Server'] = 'owndc/%s' % version
        cherrypy.response.headers['Content-Type'] = 'text/html'
        helptext = '<body><h1>Help of the Dataselect implementation by owndc</h1></body>.'
        return helptext.encode('utf-8')

    @cherrypy.expose
    def version(self):
        """Return the version of this implementation.

        :returns: System version in plain text format
        :rtype: utf-8 encoded string
        """
        self.log.debug('Return owndc version number.')
        cherrypy.response.headers['Server'] = 'owndc/%s' % version
        cherrypy.response.headers['Content-Type'] = 'text/plain'
        cherrypy.response.headers['Content-Length'] = str(len(dsversion.encode('utf-8')))
        return dsversion.encode('utf-8')

    @cherrypy.expose(alias='application.wadl')
    def applicationwadl(self):
        self.log.debug('Return application.wadl.')
        here = os.path.dirname(__file__)
        with open(os.path.join(here, 'application.wadl'), 'r') \
                as appFile:
            cherrypy.response.headers['Server'] = 'owndc/%s' % version
            cherrypy.response.headers['Content-Type'] = 'text/xml'
            iterObj = appFile.read()
            cherrypy.response.headers['Content-Length'] = str(len(iterObj.encode('utf-8')))
        return iterObj.encode('utf-8')

    @cherrypy.expose
    def query(self, **kwargs):
        # Check that the query string is not longer than 2000 chars
        if len(cherrypy.request.query_string) > 2000:
            cherrypy.response.headers['Server'] = 'owndc/%s' % version
            cherrypy.response.status = 414
            return

        if cherrypy.request.method.upper() == 'GET':
            return self.queryGET(**kwargs)
        elif cherrypy.request.method.upper() == 'POST':
            return self.queryPOST()
        self.log.error('Request method is neither GET nor POST.')

    def queryGET(self, **kwargs):
        self.log.debug('Query with GET method')
        cherrypy.response.headers['Server'] = 'owndc/%s' % version

        for k, v in kwargs.items():
            kwargs[k] = FakeStorage(v)

        try:
            iterObj = dsq.makeQueryGET(kwargs)
            # WARNING I need to check if data length == 0?
            # Cycle through the iterator in order to retrieve one chunk at a time
            loop = 0
            for data in iterObj:
                if loop == 0:
                    # The first thing to do is to send the headers.
                    # This needs to be done here so that we are sure that there is
                    # ACTUALLY data to send

                    # Content-length cannot be set because the file size is unknown
                    self.log.debug('Setting headers.')
                    cherrypy.response.headers['Content-Type'] = iterObj.content_type
                    cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=%s' % (iterObj.filename)

                # Increment the loop count
                loop += 1
                # and send data
                self.log.debug('Send chunk')
                yield data

            if loop == 0:
                self.log.debug('Send 204 HTTP error code')
                cherrypy.response.status = 204
                return

        except WIContentError as w:
            self.log.debug('Send 204 HTTP error code')
            cherrypy.response.status = 204
            return

        except WIError as w:
            messDict = {'code': 0,
                        'message': str(w)}
            message = json.dumps(messDict)
            cherrypy.response.headers['Content-Type'] = 'application/json'
            self.log.debug('Send 400 HTTP error code')
            raise cherrypy.HTTPError(400, message)

    queryGET._cp_config = {'response.stream': True}

    def queryPOST(self):
        self.log.debug('Query with POST method')
        cherrypy.response.headers['Server'] = 'owndc/%s' % version

        length = int(cherrypy.request.headers.get('content-length', 0))
        self.log.debug('Length: %s' % length)
        lines = cherrypy.request.body.fp.read(length)

        # Show request
        self.log.debug('Request body:\n%s' % lines)

        try:
            iterObj = dsq.makeQueryPOST(lines)
            # WARNING I need to check if data length == 0?
            # Cycle through the iterator in order to retrieve one chunk at a time
            loop = 0
            for data in iterObj:
                if loop == 0:
                    # The first thing to do is to send the headers.
                    # This needs to be done here so that we are sure that there is
                    # ACTUALLY data to send

                    self.log.debug('Setting headers.')
                    # Content-length cannot be set because the file size is unknown
                    cherrypy.response.headers['Content-Type'] = iterObj.content_type
                    cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=%s' % (iterObj.filename)

                # Increment the loop count
                loop += 1
                # and send data
                self.log.debug('Send chunk')
                yield data

            if loop == 0:
                self.log.debug('Send 204 HTTP error code')
                cherrypy.response.status = 204
                return

        except WIError as w:
            messDict = {'code': 0,
                        'message': str(w)}
            message = json.dumps(messDict)
            self.log.debug('Send 400 HTTP error code')
            cherrypy.response.headers['Content-Type'] = 'application/json'
            raise cherrypy.HTTPError(400, message)

    queryPOST._cp_config = {'response.stream': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', '--host',
                        help='Address where this server listens.',
                        default='localhost')
    parser.add_argument('-P', '--port',
                        help='Port where this server listens.',
                        default='7000')
    parser.add_argument('-c', '--config',
                        help='Config file.',
                        default=os.path.join(os.path.expanduser('~'), '.owndc', 'owndc.cfg'))
    parser.add_argument('--version', action='version',
                        version='owndc-%s' % version)
    args = parser.parse_args()

    # Check arguments (IP, port)
    host = args.host

    configP = configparser.RawConfigParser()
    configP.read(args.config)

    # Logging configuration
    verbo = configP.get('Logging', 'main') if configP.has_option('Logging', 'main') else 'INFO'
    verboNum = getattr(logging, verbo.upper(), 30)
    LOG_CONF['loggers']['main']['level'] = verboNum

    verbo = configP.get('Logging', 'ResultFile') if configP.has_option('Logging', 'ResultFile') else 'INFO'
    verboNum = getattr(logging, verbo.upper(), 30)
    LOG_CONF['loggers']['ResultFile']['level'] = verboNum

    verbo = configP.get('Logging', 'DataSelectQuery') if configP.has_option('Logging', 'DataSelectQuery') else 'INFO'
    verboNum = getattr(logging, verbo.upper(), 30)
    LOG_CONF['loggers']['DataSelectQuery']['level'] = verboNum

    verbo = configP.get('Logging', 'Application') if configP.has_option('Logging', 'Application') else 'INFO'
    verboNum = getattr(logging, verbo.upper(), 30)
    LOG_CONF['loggers']['Application']['level'] = verboNum

    verbo = configP.get('Logging', 'cherrypy.access') if configP.has_option('Logging', 'cherrypy.access') else 'INFO'
    verboNum = getattr(logging, verbo.upper(), 30)
    LOG_CONF['loggers']['cherrypy.access']['level'] = verboNum

    verbo = configP.get('Logging', 'cherrypy.error') if configP.has_option('Logging', 'cherrypy.error') else 'INFO'
    verboNum = getattr(logging, verbo.upper(), 30)
    LOG_CONF['loggers']['cherrypy.error']['level'] = verboNum

    logging.config.dictConfig(LOG_CONF)

    loclog = logging.getLogger('main')

    try:
        port = int(args.port)
    except:
        loclog.error('Error while interpreting port %s' % args.port)
        raise Exception('Error while interpreting port %s' % args.port)

    # Create the object that will resolve and execute all the queries
    loclog.info('Creating a DataSelectQuery object. Wait...')
    global dsq
    dsq = DataSelectQuery(os.path.join(os.path.expanduser('~'), '.owndc', 'data', 'owndc-routes.xml'),
                          os.path.join(os.path.expanduser('~'), '.owndc', 'data', 'masterTable.xml'),
                          args.config)
    loclog.info("Virtual Datacentre at: http://%s:%s/fdsnws/dataselect/1/" %
                (host, port))

    server_config = {
        'global': {
            'tools.proxy.on': True,
            'tools.trailing_slash.on': False,
            'server.socket_host': host,
            'server.socket_port': port,
            'engine.autoreload_on': False,
            'log.screen': False
        }
    }
    # Update the global CherryPy configuration
    cherrypy.config.update(server_config)
    # TODO Pass all parameters to Application!
    cherrypy.tree.mount(Application(), '/fdsnws/dataselect/1')

    plugins.Daemonizer(cherrypy.engine).subscribe()
    if hasattr(cherrypy.engine, 'signal_handler'):
        cherrypy.engine.signal_handler.subscribe()
    if hasattr(cherrypy.engine, 'console_control_handler'):
        cherrypy.engine.console_control_handler.subscribe()

    # Always start the engine; this will start all other services
    try:
        cherrypy.engine.start()
    except Exception:
        # Assume the error has been logged already via bus.log.
        raise
    else:
        cherrypy.engine.block()


if __name__ == '__main__':
    main()
    # config = {'/': {'tools.trailing_slash.on': False}}
    # cherrypy.quickstart(Application(), script_name='/', config=config)