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
        :rtype: string
        """
        cherrypy.response.headers['Server'] = 'ownDC/%s' % version
        cherrypy.response.headers['Content-Type'] = 'text/plain'
        return dsversion.encode('utf-8')

    @cherrypy.expose(alias='application.wadl')
    def applicationwadl(self):
        here = os.path.dirname(__file__)
        with open(os.path.join(here, 'application.wadl'), 'r') \
                as appFile:
            cherrypy.response.headers['Server'] = 'ownDC/%s' % version
            cherrypy.response.headers['Content-Type'] = 'text/xml'
            iterObj = appFile.read()
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


# # Implement the web server
# class ServerHandler(htserv.SimpleHTTPRequestHandler):
#     """
# :synopsis: Implements the methods to handle the Dataselect requests via
#            GET and POST.
# :platform: Linux
#     """
#
#     def log_message(self, format, *args):
#         # This is important to "mute" the logging messages alla Apache
#         pass
#
#     def __send_plain(self, code, error, msg):
#         """
#         :synopsis: Sends a plain response in HTTP style
#         :platform: Linux
#
#         """
#         self.send_response(code, error)
#         self.send_header('Server', 'OwnDC/%s' % version)
#         self.send_header('Content-Type', 'text/plain')
#         self.send_header('Content-Length', str(len(msg)))
#         self.end_headers()
#         self.wfile.write(msg)
#         return
#
#     def __send_xml(self, code, error, msg):
#         """
#         :synopsis: Sends an XML response in HTTP style
#         :platform: Linux
#
#         """
#         self.send_response(code, error)
#         self.send_header('Server', 'OwnDC/%s' % version)
#         self.send_header('Content-Type', 'text/xml')
#         self.send_header('Content-Length', str(len(msg)))
#         self.end_headers()
#         self.wfile.write(msg)
#         return
#
#     def __send_dynamicfile(self, code, msg, iterFile):
#         """
# :synopsis: Sends a file or similar object. iterFile is expected to have the
#            following attributes: filename and content_type.
#
#         """
#
#         # Cycle through the iterator in order to retrieve one chunck at a time
#         loop = 0
#
#         for data in iterFile:
#             if loop == 0:
#                 # The first thing to do is to send the headers.
#                 # This needs to be done here so that we are sure that there is
#                 # ACTUALLY data to send
#
#                 self.send_response(code, msg)
#                 # Content-length cannot be set because the file size is unknown
#                 self.send_header('Server', 'OwnDC/%s' % version)
#                 self.send_header('Content-Type', iterFile.content_type)
#                 self.send_header('Content-Disposition',
#                                  'attachment; filename=%s' %
#                                  (iterFile.filename))
#                 self.send_header('Transfer-Encoding', 'chunked')
#                 self.end_headers()
#
#             # Increment the loop count
#             loop += 1
#             # and send data
#             try:
#                 # This is sent in CHUNKED mode, so first the length is sent
#                 self.wfile.write('%x\r\n' % len(data))
#                 # then the data
#                 self.wfile.write(data)
#                 # and then an empty line
#                 self.wfile.write('\r\n')
#             except:
#                 logging.error('wfile.closed: %s' % self.wfile.closed)
#
#         if loop == 0:
#             # If there was no data available send the 204 error code
#             self.send_response(204, 'No Content')
#             self.end_headers()
#         else:
#             # Finish transmission
#             self.wfile.write('0\r\n\r\n')
#         return
#
#     def do_GET(self):
#         """
#         :synopsis: Handle a GET request. Input data is read from self.path.
#         :platform: Linux
#
#         """
#         logging.debug("======= GET STARTED =======")
#         logging.debug(self.headers)
#
#         if not self.path.startswith('/fdsnws/dataselect/1/'):
#             self.__send_plain(400, 'Bad Request',
#                               'Wrong path. Not FDSN compliant')
#             return
#
#         reqStr = self.path[len('/fdsnws/dataselect/1/'):]
#
#         # Check whether the function called is implemented
#         implementedFunctions = ['query', 'application.wadl', 'version']
#
#         fname = reqStr[:reqStr.find('?')] if '?' in reqStr else reqStr
#         if fname not in implementedFunctions:
#             logging.error('Function %s not implemented' % fname)
#             # return send_plain_response("400 Bad Request",
#             #                            'Function "%s" not implemented.' %
#             #                            fname, start_response)
#
#         if fname == 'application.wadl':
#             iterObj = ''
#             here = os.path.dirname(__file__)
#             with open(os.path.join(here, 'application.wadl'), 'r') \
#                     as appFile:
#                 iterObj = appFile.read()
#                 self.__send_xml(200, 'OK', iterObj)
#                 return
#
#         elif fname == 'version':
#             self.__send_plain(200, 'OK', self.wi.version)
#             return
#
#         elif fname != 'query':
#             self.__send_plain(400, 'Bad Request',
#                               'Unrecognized method %s' % fname)
#             return
#
#         # Here only the "query" case should remain
#         begPar = reqStr.find('?')
#         if begPar < 0:
#             self.__send_plain(400, 'Bad Request', 'Not enough parameters!')
#             return
#
#         # Parse the string and create a similar object to FieldStorage
#         # so that the code of RoutingCache works
#         listPar = reqStr[begPar + 1:].split('&')
#         dictPar = dict()
#         for i in listPar:
#             k, v = i.split('=')
#             dictPar[k] = FakeStorage(v)
#         logging.info('GET request for %s' % dictPar)
#
#         try:
#             iterObj = self.wi.makeQueryGET(dictPar)
#             self.__send_dynamicfile(200, 'OK', iterObj)
#             return
#
#         except WIError as w:
#             # FIXME all WIError parameters must be reviewed again
#             self.__send_plain(400, 'Bad Request', w.body)
#             return
#
#         self.__send_plain(400, 'Bad Request', str(dictPar))
#         return
#
#     def do_POST(self):
#         """
#         :synopsis: Handle a POST request. Input data is read from self.rfile
#                    and output is written to self.wfile.
#         :platform: Linux
#
#         """
#         logging.debug("======= POST STARTED =======")
#         logging.debug(self.headers)
#
#         # Check that the user calls "query". It is the only option via POST
#         if not self.path.startswith('/fdsnws/dataselect/1/query'):
#             self.__send_plain(400, 'Bad Request',
#                               'Wrong path. Not FDSN compliant')
#             return
#
#         length = int(self.headers['content-length'])
#         logging.debug('Length: %s' % length)
#         lines = self.rfile.read(length)
#
#         # Show request
#         logging.info('POST request with %s lines' % len(lines.split('\n')))
#
#         try:
#             iterObj = self.wi.makeQueryPOST(lines)
#             self.__send_dynamicfile(200, 'OK', iterObj)
#             return
#
#         except WIError as w:
#             return self.__send_plain(w.status, '', w.body)
#
#         self.__send_plain(400, 'Bad Request', lines)
#         return


# def main():
#     parser = argparse.ArgumentParser()
#     parser.add_argument('-H', '--host',
#                         help='Address where this server listens.',
#                         default='localhost')
#     parser.add_argument('-P', '--port',
#                         help='Port where this server listens.',
#                         default='7000')
#     parser.add_argument('-c', '--config',
#                         help='Config file.',
#                         default='ownDC.cfg')
#     parser.add_argument('--version', action='version',
#                         version='ownDC %s' % get_git_version())
#     args = parser.parse_args()
#
#     # Check arguments (IP, port)
#     host = args.host
#
#     configP = configparser.RawConfigParser()
#     configP.read(args.config)
#
#     verbo = configP.get('Service', 'verbosity')
#     verboNum = getattr(logging, verbo.upper(), 30)
#
#     logging.basicConfig(logLevel=verboNum)
#     loclog = logging.getLogger('main')
#     loclog.setLevel(verboNum)
#
#     try:
#         port = int(args.port)
#     except:
#         loclog.error('Error while interpreting port %s' % args.port)
#         sys.exit(-1)
#
#     # Create the object that will resolve and execute all the queries
#     loclog.info('Creating a DataSelectQuery object. Wait...')
#     ServerHandler.wi = DataSelectQuery('ownDC.log', './data/ownDC-routes.xml',
#                                        configFile=args.config)
#     loclog.info('Ready to answer queries!')
#
#     Handler = ServerHandler
#     httpd = socsrv.TCPServer((host, port), Handler)
#
#     loclog.info("Virtual Datacentre at: http://%s:%s/fdsnws/dataselect/1/" %
#                 (host, port))
#     httpd.serve_forever()

dsq = DataSelectQuery('./data/ownDC-routes.xml', './data/masterTable.xml', 'ownDC.cfg')

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
cherrypy.tree.mount(Application(), '/fdsnws/dataselect/1')

if __name__ == '__main__':
    cherrypy.engine.signals.subscribe()
    cherrypy.engine.start()
    cherrypy.engine.block()
    # config = {'/': {'tools.trailing_slash.on': False}}
    # cherrypy.quickstart(Application(), script_name='/', config=config)