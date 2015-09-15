#!/usr/bin/python

"""
Save this file as server.py
>>> python server.py 0.0.0.0 8001
serving on 0.0.0.0:8001

or simply

>>> python server.py
Serving on localhost:8000

You can use this to test GET and POST methods.

"""

import SimpleHTTPServer
import SocketServer
import logging
import cgi
import os

import sys

version = '1.0.0'

if len(sys.argv) > 2:
    PORT = int(sys.argv[2])
    I = sys.argv[1]
elif len(sys.argv) > 1:
    PORT = int(sys.argv[1])
    I = ""
else:
    PORT = 8000
    I = ""


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

        elif fname == 'query':
            begPar = reqStr.find('?')
            if begPar < 0:
                self.__send_plain(400, 'Bad Request', 'Not enough parameters!')
                return

            listPar = reqStr[begPar + 1:].split('&')
            logging.error(listPar)
            dictPar = dict()
            for i in listPar:
                k, v = i.split('=')
                dictPar[k] = v
            logging.debug(dictPar)

            self.__send_plain(200, 'OK', str(dictPar))
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
        SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

Handler = ServerHandler

httpd = SocketServer.TCPServer(("", PORT), Handler)

print "@rochacbruno Python http server version 0.1 (for testing purposes only)"
print "Serving at: http://%(interface)s:%(port)s" % dict(interface=I or "localhost", port=PORT)
httpd.serve_forever()

