#!/usr/bin/python

"""
Save this file as server.py
>>> python server.py 0.0.0.0 8001
serving on 0.0.0.0:8001

or simply

>>> python server.py
Serving on localhost:7000

You can use this to test GET and POST methods.

"""

import SimpleHTTPServer
import SocketServer
import logging
import cgi
import os
import sys
from query import DataSelectQuery
from wsgicomm import WIError

version = '1.0.0'
wi = DataSelectQuery('EIDA FDSN-WS', 'virtual-ds.log')

if len(sys.argv) > 2:
    PORT = int(sys.argv[2])
    I = sys.argv[1]
elif len(sys.argv) > 1:
    PORT = int(sys.argv[1])
    I = ""
else:
    PORT = 7000
    I = ""


class FakeStorage(dict):
    def __init__(self, s=None):
        self.value = s
    def getvalue(self, k):
        return self[k]
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self.value)

class ServerHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

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
               and content_type attributes of body.
    
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
            self.wfile.write(data)
    
        if loop == 0:
            self.send_response(204, 'No Content')
            self.end_headers()
        return

    def do_GET(self):
        logging.warning("======= GET STARTED =======")
        logging.warning(self.headers)

        if not self.path.startswith('/fdsnws/dataselect/1/'):
            self.__send_plain(400, 'Wrong path. Not FDSNWS compliant', 'Sarasa')
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
        logging.warning(dictPar)

        try:
            iterObj = wi.makeQueryGET(dictPar)
            logging.warning(iterObj)
            self.__send_dynamicfile(200, 'OK', iterObj)
            return

        except WIError as w:
            return self.__send_plain(w.status, '', w.body)

        self.__send_plain(400, 'Bad Request', str(dictPar))
        return
        #SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        logging.warning("======= POST STARTED =======")
        logging.warning(self.headers)
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD':'POST',
                     'CONTENT_TYPE':self.headers['Content-Type'],
                     })
        logging.warning("======= POST VALUES =======")
        for item in form.list:
            logging.warning(item)
        logging.warning("\n")


        # To be tested!
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

            fdsnws = self.routes.getRoute(net, sta, loc, cha, start, endt,
                                          'dataselect')

            urlList.extend(applyFormat(fdsnws, 'get').splitlines())

        if not len(urlList):
            raise WIContentError('No routes have been found!')

        iterObj = ResultFile(urlList, self.acc.log if self.acc is not None
                             else None)
        return iterObj


        #SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

Handler = ServerHandler

httpd = SocketServer.TCPServer(("", PORT), Handler)

print "@rochacbruno Python http server version 0.1 (for testing purposes only)"
print "Serving at: http://%(interface)s:%(port)s" % dict(interface=I or "localhost", port=PORT)
httpd.serve_forever()

