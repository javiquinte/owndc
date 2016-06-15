#!/usr/bin/python
# ownDC: An FDSN Virtual Datacentre prototype
#
# (c) 2015 Javier Quinteros, GEOFON team
# <javier@gfz-potsdam.de>
#
# ----------------------------------------------------------------------


"""ownDC: An FDSN-WS Virtual Datacentre prototype

   :Platform:
       Linux
   :Copyright:
       GEOFON, GFZ Potsdam <geofon@gfz-potsdam.de>
   :License:
       To be decided!

.. moduleauthor:: Javier Quinteros <javier@gfz-potsdam.de>, GEOFON, GFZ Potsdam
"""

import argparse
import logging
import datetime
import os
import sys
try:
    import configparser
except ImportError:
    import ConfigParser as configparser

from query import DataSelectQuery
from wsgicomm import WIError
from wsgicomm import WIContentError
from version import get_git_version

# These "tries" are needed to support also Python3
try:
    import http.server as htserv
except ImportError:
    import SimpleHTTPServer as htserv

try:
    import socketserver as socsrv
except ImportError:
    import SocketServer as socsrv

# Version of this software
version = '0.9a2'


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


# Implement the web server
class ServerHandler(htserv.SimpleHTTPRequestHandler):
    """
:synopsis: Implements the methods to handle the Dataselect requests via
           GET and POST.
:platform: Linux
    """

    def log_message(self, format, *args):
        # This is important to "mute" the logging messages alla Apache
        pass

    def __send_plain(self, code, error, msg):
        """
        :synopsis: Sends a plain response in HTTP style
        :platform: Linux

        """
        self.send_response(code, error)
        self.send_header('Server', 'OwnDC/%s' % version)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(msg)))
        self.end_headers()
        self.wfile.write(msg)
        return

    def __send_xml(self, code, error, msg):
        """
        :synopsis: Sends an XML response in HTTP style
        :platform: Linux

        """
        self.send_response(code, error)
        self.send_header('Server', 'OwnDC/%s' % version)
        self.send_header('Content-Type', 'text/xml')
        self.send_header('Content-Length', str(len(msg)))
        self.end_headers()
        self.wfile.write(msg)
        return

    def __send_dynamicfile(self, code, msg, iterFile):
        """
:synopsis: Sends a file or similar object. iterFile is expected to have the
           following attributes: filename and content_type.

        """

        # Cycle through the iterator in order to retrieve one chunck at a time
        loop = 0

        for data in iterFile:
            if loop == 0:
                # The first thing to do is to send the headers.
                # This needs to be done here so that we are sure that there is
                # ACTUALLY data to send

                self.send_response(code, msg)
                # Content-length cannot be set because the file size is unknown
                self.send_header('Server', 'OwnDC/%s' % version)
                self.send_header('Content-Type', iterFile.content_type)
                self.send_header('Content-Disposition',
                                 'attachment; filename=%s' %
                                 (iterFile.filename))
                self.send_header('Transfer-Encoding', 'chunked')
                self.end_headers()

            # Increment the loop count
            loop += 1
            # and send data
            try:
                # This is sent in CHUNKED mode, so first the length is sent
                self.wfile.write('%x\r\n' % len(data))
                # then the data
                self.wfile.write(data)
                # and then an empty line
                self.wfile.write('\r\n')
            except:
                logging.error('wfile.closed: %s' % self.wfile.closed)

        if loop == 0:
            # If there was no data available send the 204 error code
            self.send_response(204, 'No Content')
            self.end_headers()
        else:
            # Finish transmission
            self.wfile.write('0\r\n\r\n')
        return

    def do_GET(self):
        """
        :synopsis: Handle a GET request. Input data is read from self.path.
        :platform: Linux

        """
        logging.debug("======= GET STARTED =======")
        logging.debug(self.headers)

        if not self.path.startswith('/fdsnws/dataselect/1/'):
            self.__send_plain(400, 'Bad Request',
                              'Wrong path. Not FDSN compliant')
            return

        if len(self.path) > 1000:
            self.__send_plain(414, "Request URI too large",
                              "maximum URI length is 1000 characters")
            return

        reqStr = self.path[len('/fdsnws/dataselect/1/'):]

        # Check whether the function called is implemented
        implementedFunctions = ['query', 'application.wadl', 'version']

        fname = reqStr[:reqStr.find('?')] if '?' in reqStr else reqStr
        if fname not in implementedFunctions:
            logging.error('Function %s not implemented' % fname)
            # return send_plain_response("400 Bad Request",
            #                            'Function "%s" not implemented.' %
            #                            fname, start_response)

        if fname == 'application.wadl':
            iterObj = ''
            here = os.path.dirname(__file__)
            with open(os.path.join(here, 'application.wadl'), 'r') \
                    as appFile:
                iterObj = appFile.read()
                self.__send_xml(200, 'OK', iterObj)
                return

        elif fname == 'version':
            self.__send_plain(200, 'OK', self.wi.version)
            return

        elif fname != 'query':
            self.__send_plain(400, 'Bad Request',
                              'Unrecognized method %s' % fname)
            return

        # Here only the "query" case should remain
        begPar = reqStr.find('?')
        if begPar < 0:
            self.__send_plain(400, 'Bad Request', 'Not enough parameters!')
            return

        # Parse the string and create a similar object to FieldStorage
        # so that the code of RoutingCache works
        listPar = reqStr[begPar + 1:].split('&')
        dictPar = dict()
        for i in listPar:
            k, v = i.split('=')
            dictPar[k] = FakeStorage(v)

        logging.info('GET request for %s' % dictPar)

        try:
            iterObj = self.wi.makeQueryGET(dictPar)
            self.__send_dynamicfile(200, 'OK', iterObj)
            return

        except WIContentError as w:
            # print 'I caught a WIContentError condition %s' % dictPar
            self.__send_plain(204, 'No Content', str(dictPar))
            return

        except WIError as w:
            # print 'I ended up at the except condition %s' % dictPar
            # FIXME all WIError parameters must be reviewed again
            self.__send_plain(400, 'Bad Request', w.body)
            return

        self.__send_plain(400, 'Bad Request', str(dictPar))
        return

    def do_POST(self):
        """
        :synopsis: Handle a POST request. Input data is read from self.rfile
                   and output is written to self.wfile.
        :platform: Linux

        """
        logging.debug("======= POST STARTED =======")
        logging.debug(self.headers)

        # Check that the user calls "query". It is the only option via POST
        if not self.path.startswith('/fdsnws/dataselect/1/query'):
            self.__send_plain(400, 'Bad Request',
                              'Wrong path. Not FDSN compliant')
            return

        length = int(self.headers['content-length'])
        logging.debug('Length: %s' % length)
        lines = self.rfile.read(length)

        # Show request
        logging.info('POST request with %s lines' % len(lines.split('\n')))

        try:
            iterObj = self.wi.makeQueryPOST(lines)
            self.__send_dynamicfile(200, 'OK', iterObj)
            return

        except WIError as w:
            return self.__send_plain(w.status, '', w.body)

        self.__send_plain(400, 'Bad Request', lines)
        return


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
                        version='ownDC %s' % get_git_version())
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
        sys.exit(-1)

    # Create the object that will resolve and execute all the queries
    loclog.info('Creating a DataSelectQuery object. Wait...')
    ServerHandler.wi = DataSelectQuery('ownDC.log', './data/ownDC-routes.xml',
                                       configFile=args.config)
    loclog.info('Ready to answer queries!')

    Handler = ServerHandler
    httpd = socsrv.TCPServer((host, port), Handler)

    loclog.info("Virtual Datacentre at: http://%s:%s/fdsnws/dataselect/1/" %
                (host, port))
    httpd.serve_forever()

if __name__ == '__main__':
    main()
