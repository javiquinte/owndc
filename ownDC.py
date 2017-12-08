#!/usr/bin/env python2
# ownDC: An FDSN Virtual Datacentre for SeisComP3
#
# (c) 2015-2017 Javier Quinteros, GEOFON team
# <javier@gfz-potsdam.de>
#
# ----------------------------------------------------------------------


"""ownDC: An FDSN-WS Virtual Data Centre for SeisComP3

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
import ConfigParser as configparser
import datetime
import urllib2 as ul

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
        self.filename = 'ownDC-%s.mseed' % nowStr

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
    def __init__(self, routesFile=None, masterFile=None,
                 configFile=None, log=None):

        if routesFile is None:
            routesFile = os.path.join(os.path.expanduser('~'), '.ownDC', 'data', 'routing.xml')

        if masterFile is None:
            masterFile = os.path.join(os.path.expanduser('~'), '.ownDC', 'data', 'masterTable.xml')

        if configFile is None:
            configFile = os.path.join(os.path.expanduser('~'), '.ownDC', 'routing.cfg')

        # Dataselect version
        self.version = '1.1.0'

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
        pass

    @cherrypy.expose
    def index(self):
        cherrypy.response.headers['Server'] = 'ownDC/%s' % version
        cherrypy.response.headers['Content-Type'] = 'text/html'
        helptext = '<body><h1>Help of the Dataselect implementation by ownDC</h1></body>.'
        return helptext.encode('utf-8')

    @cherrypy.expose
    def version(self):
        """Return the version of this implementation.

        :returns: System version in plain text format
        :rtype: utf-8 encoded string
        """
        cherrypy.response.headers['Server'] = 'ownDC/%s' % version
        cherrypy.response.headers['Content-Type'] = 'text/plain'
        cherrypy.response.headers['Content-Length'] = str(len(dsversion.encode('utf-8')))
        return dsversion.encode('utf-8')

    @cherrypy.expose(alias='application.wadl')
    def applicationwadl(self):
        here = os.path.dirname(__file__)
        with open(os.path.join(here, 'application.wadl'), 'r') \
                as appFile:
            cherrypy.response.headers['Server'] = 'ownDC/%s' % version
            cherrypy.response.headers['Content-Type'] = 'text/xml'
            iterObj = appFile.read()
            cherrypy.response.headers['Content-Length'] = str(len(iterObj.encode('utf-8')))
        return iterObj.encode('utf-8')

    @cherrypy.expose
    def query(self, **kwargs):
        if cherrypy.request.method.upper() == 'GET':
            return self.queryGET(**kwargs)
        elif cherrypy.request.method.upper() == 'POST':
            return self.queryPOST()

    def queryGET(self, **kwargs):
        cherrypy.response.headers['Server'] = 'ownDC/%s' % version

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
                    cherrypy.response.headers['Content-Type'] = iterObj.content_type
                    cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=%s' % (iterObj.filename)

                # Increment the loop count
                loop += 1
                # and send data
                yield data

            if loop == 0:
                cherrypy.response.status = 204
                return

        except WIError as w:
            messDict = {'code': 0,
                        'message': str(w)}
            message = json.dumps(messDict)
            cherrypy.response.headers['Content-Type'] = 'application/json'
            raise cherrypy.HTTPError(400, message)

    queryGET._cp_config = {'response.stream': True}

    def queryPOST(self):
        cherrypy.response.headers['Server'] = 'ownDC/%s' % version

        length = int(cherrypy.request.headers.get('content-length', 0))
        logging.debug('Length: %s' % length)
        lines = cherrypy.request.body.fp.read(length)

        # Show request
        logging.info('POST request with %s lines' % len(lines.split('\n')))

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

                    # Content-length cannot be set because the file size is unknown
                    cherrypy.response.headers['Content-Type'] = iterObj.content_type
                    cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=%s' % (iterObj.filename)

                # Increment the loop count
                loop += 1
                # and send data
                yield data

            if loop == 0:
                cherrypy.response.status = 204
                return

        except WIError as w:
            messDict = {'code': 0,
                        'message': str(w)}
            message = json.dumps(messDict)
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
                        default='ownDC.cfg')
    parser.add_argument('--version', action='version',
                        version='ownDC-%s' % dsversion)
    args = parser.parse_args()

    # Check arguments (IP, port)
    host = args.host

    configP = configparser.RawConfigParser()
    configP.read(args.config)

    verbo = configP.get('Service', 'verbosity')
    verboNum = getattr(logging, verbo.upper(), 30)

    logging.basicConfig(logLevel=verboNum)
    loclog = logging.getLogger('main')
    loclog.setLevel(verboNum)

    try:
        port = int(args.port)
    except:
        loclog.error('Error while interpreting port %s' % args.port)
        raise Exception('Error while interpreting port %s' % args.port)

    # Create the object that will resolve and execute all the queries
    loclog.info('Creating a DataSelectQuery object. Wait...')
    global dsq
    dsq = DataSelectQuery('./data/ownDC-routes.xml', './data/masterTable.xml', args.config)
    loclog.info('Ready to answer queries!')
    loclog.info("Virtual Datacentre at: http://%s:%s/fdsnws/dataselect/1/" %
                (host, port))

    server_config = {
        'global': {
            'tools.proxy.on': True,
            'tools.trailing_slash.on': False,
            'server.socket_host': '127.0.0.1',
            'server.socket_port': 7000,
            'engine.autoreload_on': False
        }
    }
    # Update the global CherryPy configuration
    cherrypy.config.update(server_config)
    # TODO Pass all parameters to Application!
    cherrypy.tree.mount(Application(), '/fdsnws/dataselect/1')
    cherrypy.engine.signals.subscribe()
    cherrypy.engine.start()
    cherrypy.engine.block()


if __name__ == '__main__':
    main()
    # config = {'/': {'tools.trailing_slash.on': False}}
    # cherrypy.quickstart(Application(), script_name='/', config=config)