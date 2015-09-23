#!/usr/bin/python
# ownDC: An FDSN Virtual Datacentre prototype
#
# (c) 2015 Javier Quinteros, GEOFON team
# <javier@gfz-potsdam.de>
#
# ----------------------------------------------------------------------


"""ownDC: An FDSN-WS Virtual Datacentre prototype

(c) 2015 Javier Quinteros, GEOFON, GFZ Potsdam

>>> python ownDC.py 0.0.0.0 8001
serving on 0.0.0.0:8001

or simply

>>> python ownDC.py
Serving on localhost:7000

"""

import logging
import datetime
import cgi
import os
import sys
import errno
import socket
from query import DataSelectQuery
from wsgicomm import WIError

try:
    import http.server as htserv
except ImportError:
    import SimpleHTTPServer as htserv

try:
    import socketserver as socsrv
except ImportError:
    import SocketServer as socsrv

# Version of this software
version = '1.0.0'

# Create the object that will resolve and execute all the queries
wi = DataSelectQuery('VDC', 'ownDC.log')

# Check arguments (IP, port) and assign default values if needed
if len(sys.argv) > 2:
    PORT = int(sys.argv[2])
    I = sys.argv[1]
elif len(sys.argv) > 1:
    PORT = int(sys.argv[1])
    I = "localhost"
else:
    PORT = 7000
    I = "localhost"


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

# Patch a bug in the SocketServer affecting the TCPServer
class MyTCPServer(socsrv.TCPServer):
    acceptable_errors = (errno.EPIPE, errno.ECONNABORTED)

    #def handle_error(self, request, client_address):
    #    error = sys.exc_value

    #    if isinstance(error, socket.error) and isinstance(error.args, tuple) \
    #            and error.args[0] in self.acceptable_errors:
    #        logging.warning('%s detected and skipped' % error)
    #        pass
    #    else:
    #        logging.error(error)

# Implement the web server
class ServerHandler(htserv.SimpleHTTPRequestHandler):

    def finish(self):
        try:
            logging.debug('Enter try')
            if not self.wfile.closed:
                logging.debug('Want to flush')
                self.wfile.flush()
                logging.debug('Want to close')
                self.wfile.close()
        except socket.error:
            # An final socket error may have occurred here, such as
            # the local error ECONNABORTED.
            pass
        self.rfile.close()

    def __send_plain(self, code, error, msg):
        self.send_response(code, error)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(msg)
        return

    def __send_xml(self, code, error, msg):
        self.send_response(code, error)
        self.send_header('Content-Type', 'text/xml')
        self.end_headers()
        self.wfile.write(msg)
        return

    def __send_dynamicfile(self, code, msg, iterFile):
        """
:synopsis: Sends a file or similar object. Caller must set the filename, size \
           and content_type attributes of the iterFile.
    
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
                self.send_header('Content-Type', iterFile.content_type)
                self.send_header('Content-Disposition',
                                 'attachment; filename=%s' % (iterFile.filename))
                self.end_headers()
    
            # Increment the loop count
            loop += 1
            # and send data
            try:
                self.wfile.write(data)
            except:
                logging.error('wfile.closed: %s' % self.wfile.closed)
    
        if loop == 0:
            self.send_response(204, 'No Content')
            self.end_headers()
        return

    def do_GET(self):
        logging.debug("======= GET STARTED =======")
        logging.debug(self.headers)

        if not self.path.startswith('/fdsnws/dataselect/1/'):
            self.__send_plain(400, 'Bad Request',
                              'Wrong path. Not FDSN compliant')
            return

        reqStr = self.path[len('/fdsnws/dataselect/1/'):]
        
        # Check whether the function called is implemented
        implementedFunctions = ['query', 'application.wadl', 'version']

        fname = reqStr[:reqStr.find('?')] if '?' in reqStr else reqStr
        if fname not in implementedFunctions:
            logging.error('Function %s not implemented' % fname)
            #return send_plain_response("400 Bad Request",
            #                           'Function "%s" not implemented.' % fname,
            #                           start_response)

        if fname == 'application.wadl':
            iterObj = ''
            here = os.path.dirname(__file__)
            with open(os.path.join(here, 'application.wadl'), 'r') \
                    as appFile:
                iterObj = appFile.read()
                self.__send_xml(200, 'OK', iterObj)
                return

        elif fname == 'version':
            self.__send_plain(200, 'OK', version)
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
            iterObj = wi.makeQueryGET(dictPar)
            self.__send_dynamicfile(200, 'OK', iterObj)
            return

        except WIError as w:
            return self.__send_plain(w.status, '', w.body)

        self.__send_plain(400, 'Bad Request', str(dictPar))
        return
        #SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        logging.debug("======= POST STARTED =======")
        logging.debug(self.headers)

        # Check that the user calls "query". It is the only option via POST
        if not self.path.startswith('/fdsnws/dataselect/1/query'):
            self.__send_plain(400, 'Bad Request',
                              'Wrong path. Not FDSN compliant')
            return

        # CITATION: http://stackoverflow.com/questions/4233218/python-basehttprequesthandler-post-variables
        ctype, pdict = cgi.parse_header(self.headers['content-type'])

        #if ctype == 'application/x-www-form-urlencoded':
        length = int(self.headers['content-length'])
        logging.debug('Length: %s' % length)
        lines = self.rfile.read(length)
        #else:
        #    msg = 'Content-Type must be application/x-www-form-urlencoded'
        #    self.__send_plain(400, 'Bad Request', msg)
        #    return

        # Show request
        logging.info('POST request with %s lines' % len(lines.split('\n')))

        try:
            iterObj = wi.makeQueryPOST(lines)
            self.__send_dynamicfile(200, 'OK', iterObj)
            return

        except WIError as w:
            return self.__send_plain(w.status, '', w.body)

        self.__send_plain(400, 'Bad Request', lines)
        return

Handler = ServerHandler
#httpd = socsrv.TCPServer(("", PORT), Handler)
httpd = MyTCPServer(("", PORT), Handler)

logging.info("Virtual Datacentre at: http://%s:%s/fdsnws/dataselect/1/" %
             (I, PORT))
httpd.serve_forever()
