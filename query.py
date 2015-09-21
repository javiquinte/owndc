#!/usr/bin/env python
#
# FDSN-WS Virtual Datacentre prototype
#
# (c) 2015 Javier Quinteros, GEOFON team
# <javier@gfz-potsdam.de>
#
# ----------------------------------------------------------------------


"""FDSN-WS Virtual Datacentre prototype

(c) 2015 Javier Quinteros, GEOFON, GFZ Potsdam

"""

import os
import cgi
import datetime
import urllib2
import fcntl
import smtplib
from email.mime.text import MIMEText

#from wsgicomm import Logs
import logging
import ConfigParser
from wsgicomm import WIError
from wsgicomm import WIContentError
from wsgicomm import send_plain_response
from wsgicomm import send_xml_response
from wsgicomm import send_html_response
from wsgicomm import send_dynamicfile_response
from wsgicomm import send_file_response
from utils import RoutingCache
from utils import RoutingException
from routing import applyFormat
from routing import lsNSLC

# Verbosity level a la SeisComP logging.level: 1=ERROR, ... 4=DEBUG
# (global parameters, settable in wsgi file)
#verbosity = 4
config = ConfigParser.RawConfigParser()
here = os.path.dirname(__file__)
config.read(os.path.join(here, 'routing.cfg'))
#verbo = config.getint('Service', 'verbosity')
verbo = config.get('Service', 'verbosity')
# "WARNING" is the default value
verboNum = getattr(logging, verbo.upper(), 30)
logging.basicConfig(level=verboNum)

# Maximum size of POST data, in bytes? Or roubles?
cgi.maxlen = 1000000

##################################################################


class Accounting(object):
    """Receive information about all the requests and log it in a file disk
    or send it per Mail."""

    def __init__(self, logName):
        self.logName = logName
        self.lFD = open(logName, 'a')

    def log(self, data, user=None):
        fcntl.flock(self.lFD, fcntl.LOCK_EX)
        self.lFD.write(data)
        self.lFD.flush()
        fcntl.flock(self.lFD, fcntl.LOCK_UN)

        if user is not None:
            msg = MIMEText(data)
            msg['Subject'] = 'Feedback from the Dataselect web service'
            msg['From'] = 'javier@gfz-potsdam.de'
            msg['To'] = user

            # Send the message via our own SMTP server, but don't include the
            # envelope header.
            s = smtplib.SMTP('smtp.gfz-potsdam.de')
            s.sendmail('javier@gfz-potsdam.de', [user],
                       msg.as_string())
            s.quit()


class ResultFile(object):
    """Define a class that is an iterable. We can start returning the file
    before everything was retrieved from the sources."""

    def __init__(self, urlList, callback=None, user=None):
        self.urlList = urlList
        self.content_type = 'application/vnd.fdsn.mseed'
        now = datetime.datetime.now()
        nowStr = '%04d%02d%02d-%02d%02d%02d' % (now.year, now.month, now.day,
                                                now.hour, now.minute,
                                                now.second)
        self.filename = 'eidaws-%s.mseed' % nowStr
        #self.logs = Logs(verbosity)
        self.logs = logging.getLogger('ResultFile')
        self.callback = callback
        self.user = user

    def __iter__(self):
        # Read a maximum of 25 blocks of 4k (or 200 of 512b) each time
        # This will allow us to use threads and multiplex records from
        # different sources
        blockSize = 25 * 4096

        status = ''

        for pos, url in enumerate(self.urlList):
            # Prepare Request
            req = urllib2.Request(url)

            totalBytes = 0
            httpErr = 200
            # Connect to the proper FDSN-WS
            try:
                u = urllib2.urlopen(req)

                # Read the data in blocks of predefined size
                buffer = u.read(blockSize)
                if not len(buffer):
                    self.logs.error('Error code: %s' % u.getcode())
                    self.logs.error('Info: %s' % u.info())

                while len(buffer):
                    totalBytes += len(buffer)
                    # Return one block of data
                    yield buffer
                    buffer = u.read(blockSize)

                # Close the connection to avoid overloading the server
                u.close()

            except urllib2.URLError as e:
                if hasattr(e, 'reason'):
                    self.logs.error('%s - Reason: %s' % (url, e.reason))
                elif hasattr(e, 'code'):
                    self.logs.error('The server couldn\'t fulfill the request')
                    self.logs.error('Error code: %s' % e.code)

                if hasattr(e, 'code'):
                    httpErr = e.code
            except Exception as e:
                self.logs.error('%s' % e)

            if self.callback is not None:
                status += '%s %s %s %s\n' % \
                    (datetime.datetime.now().isoformat(), httpErr, url,
                     totalBytes)

        if self.callback is not None:
            self.callback(status, self.user)

        raise StopIteration


class DataSelectQuery(object):
    def __init__(self, appName, logName=None):
        # set up logging
        #self.logs = Logs(verbosity)
        self.logs = logging.getLogger('DataSelectQuery')

        self.logs.info("Starting Virtual Datacentre Web Service\n")

        # Add routing cache here, to be accessible to all modules
        here = os.path.dirname(__file__)
        routesFile = os.path.join(here, 'data', 'routing.xml')
        masterFile = os.path.join(here, 'data', 'masterTable.xml')
        self.routes = RoutingCache(routesFile, masterFile)

        self.ID = str(datetime.datetime.now())

        if logName is not None:
            here = os.path.dirname(__file__)
            self.acc = Accounting(os.path.join(here, logName))
        else:
            self.acc = None

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
                startParts = start.replace('-', ' ').replace('T', ' ')
                startParts = startParts.replace(':', ' ').replace('.', ' ')
                startParts = startParts.replace('Z', '').split()
                start = datetime.datetime(*map(int, startParts))
            except:
                logging.error('Cannot convert "starttime" parameter.')
                continue

            try:
                endParts = endt.replace('-', ' ').replace('T', ' ')
                endParts = endParts.replace(':', ' ').replace('.', ' ')
                endParts = endParts.replace('Z', '').split()
                endt = datetime.datetime(*map(int, endParts))
            except:
                logging.error('Cannot convert "endtime" parameter.')
                continue

            try:
                fdsnws = self.routes.getRoute(net, sta, loc, cha, start, endt,
                                              'dataselect')
                urlList.extend(applyFormat(fdsnws, 'get').splitlines())

            except RoutingException:
                continue
                #pass

        if not len(urlList):
            raise WIContentError('No routes have been found!')

        iterObj = ResultFile(urlList, self.acc.log if self.acc is not None
                             else None)
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
                return 'Unknown parameter: %s' % param

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

        try:
            if 'user' in parameters:
                user = parameters['user'].value
            else:
                user = None
        except:
            return 'Error while checking the user parameter'

        urlList = []

        for (n, s, l, c) in lsNSLC(net, sta, loc, cha):
            try:
                fdsnws = self.routes.getRoute(n, s, l, c, start, endt,
                                              'dataselect')
                urlList.extend(applyFormat(fdsnws, 'get').splitlines())

            except RoutingException:
                pass

        if not len(urlList):
            raise WIContentError('No routes have been found!')

        iterObj = ResultFile(urlList, self.acc.log if self.acc is not None
                             else None, user)
        return iterObj


##################################################################
#
# Initialization of variables used inside the module
#
##################################################################

#wi = DataSelectQuery('EIDA FDSN-WS', 'virtual-ds.log')


def application(environ, start_response):
    """Main WSGI handler that processes client requests and calls
    the proper functions.

    Begun by Javier Quinteros <javier@gfz-potsdam.de>,
    GEOFON team, February 2014

    """

    version = '1.1.0'
    fname = environ['PATH_INFO']

    # Among others, this will filter wrong function names,
    # but also the favicon.ico request, for instance.
    if fname is None:
        status = '400 Bad Request'
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
    implementedFunctions = ['query', 'application.wadl', 'version']

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

    elif fname == 'version':
        status = '200 OK'
        return send_plain_response(status, version, start_response)

    elif fname == 'query':
        makeQuery = getattr(wi, 'makeQuery%s' % environ['REQUEST_METHOD'])
        try:
            iterObj = makeQuery(form)
        except WIError as w:
            return send_plain_response(w.status, w.body, start_response)

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
