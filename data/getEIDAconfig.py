#!/usr/bin/python

import os
import sys
import telnetlib
from time import sleep

try:
    import cPickle as pickle
except ImportError:
    import pickle

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

sys.path.append('..')

from utils import addRemote
from utils import addRoutes
import logging

"""
.. todo::
    We need to include a function that is able to "translate" from arclink
    to dataselect. It should read routing.xml.download and change the addresses
    and services following the same table that we had previously.

"""

def arc2fdsnws(filein, fileout):
    """Read the routing file in XML format and add the Dataselect and Station
routes based on the Arclink information. The resulting table is stored in 

:param filein: Input file with routes (usually from an Arclink server).
:type filein: str
:param fileout: Output file with all routes from the input file plus new
                Station and Dataselect routes based on the Arclink route.
:type fileout: str
"""

    logs = logging.getLogger('addRoutes')
    logs.debug('Entering addRoutes(%s)\n' % fileName)

    # Read the configuration file and checks when do we need to update
    # the routes
    config = configparser.RawConfigParser()

    here = os.path.dirname(__file__)
    config.read(os.path.join(here, configF))

    if 'allowoverlap' in config.options('Service'):
        allowOverlap = config.getboolean('Service', 'allowoverlap')
    else:
        allowOverlap = False

    logs.info('Overlaps between routes will ' +
              '' if allowOverlap else 'NOT ' + 'be allowed')

    with open(fileName, 'r') as testFile:
        # Parse the routing file
        # Traverse through the networks
        # get an iterable
        try:
            context = ET.iterparse(testFile, events=("start", "end"))
        except IOError:
            msg = 'Error: %s could not be parsed. Skipping it!\n' % fileName
            logs.error(msg)
            return ptRT

        # turn it into an iterator
        context = iter(context)

        # get the root element
        if hasattr(context, 'next'):
            event, root = context.next()
        else:
            event, root = next(context)

        # Check that it is really an inventory
        if root.tag[-len('routing'):] != 'routing':
            msg = '%s seems not to be a routing file (XML). Skipping it!\n' \
                % fileName
            logs.error(msg)
            return ptRT

        # Extract the namespace from the root node
        namesp = root.tag[:-len('routing')]

        for event, route in context:
            # The tag of this node should be "route".
            # Now it is not being checked because
            # we need all the data, but if we need to filter, this
            # is the place.
            #
            if event == "end":
                if route.tag == namesp + 'route':

                    # Extract the location code
                    try:
                        locationCode = route.get('locationCode')
                        if len(locationCode) == 0:
                            locationCode = '*'

                        # Do not allow "?" wildcard in the input, because it
                        # will be impossible to match with the user input if
                        # this also has a mixture of "*" and "?"
                        if '?' in locationCode:
                            logging.error('Wildcard "?" is not allowed!')
                            continue

                    except:
                        locationCode = '*'

                    # Extract the network code
                    try:
                        networkCode = route.get('networkCode')
                        if len(networkCode) == 0:
                            networkCode = '*'

                        # Do not allow "?" wildcard in the input, because it
                        # will be impossible to match with the user input if
                        # this also has a mixture of "*" and "?"
                        if '?' in networkCode:
                            logging.error('Wildcard "?" is not allowed!')
                            continue

                    except:
                        networkCode = '*'

                    # Extract the station code
                    try:
                        stationCode = route.get('stationCode')
                        if len(stationCode) == 0:
                            stationCode = '*'
                    
                        # Do not allow "?" wildcard in the input, because it
                        # will be impossible to match with the user input if
                        # this also has a mixture of "*" and "?"
                        if '?' in stationCode:
                            logging.error('Wildcard "?" is not allowed!')
                            continue

                    except:
                        stationCode = '*'

                    # Extract the stream code
                    try:
                        streamCode = route.get('streamCode')
                        if len(streamCode) == 0:
                            streamCode = '*'

                        # Do not allow "?" wildcard in the input, because it
                        # will be impossible to match with the user input if
                        # this also has a mixture of "*" and "?"
                        if '?' in streamCode:
                            logging.error('Wildcard "?" is not allowed!')
                            continue

                    except:
                        streamCode = '*'

                    # Traverse through the sources
                    for serv in route:
                        assert serv.tag[:len(namesp)] == namesp

                        service = serv.tag[len(namesp):]
                        att = serv.attrib

                        # Extract the address (mandatory)
                        try:
                            address = att.get('address')
                            if len(address) == 0:
                                logs.error('Could not add %s' %att)
                                continue
                        except:
                            logs.error('Could not add %s' %att)
                            continue

                        try:
                            startD = att.get('start', None)
                            if len(startD):
                                startParts = startD.replace('-', ' ')
                                startParts = startParts.replace('T', ' ')
                                startParts = startParts.replace(':', ' ')
                                startParts = startParts.replace('.', ' ')
                                startParts = startParts.replace('Z', '')
                                startParts = startParts.split()
                                startD = datetime.datetime(*map(int,
                                                                startParts))
                            else:
                                startD = None
                        except:
                            startD = None
                            #msg = 'Error while converting START attribute\n'
                            #logs.error(msg)

                        # Extract the end datetime
                        try:
                            endD = att.get('end', None)
                            if len(endD):
                                endParts = endD.replace('-', ' ')
                                endParts = endParts.replace('T', ' ')
                                endParts = endParts.replace(':', ' ')
                                endParts = endParts.replace('.', ' ')
                                endParts = endParts.replace('Z', '').split()
                                endD = datetime.datetime(*map(int,
                                                              endParts))
                            else:
                                endD = None
                        except:
                            endD = None
                            #msg = 'Error while converting END attribute.\n'
                            #logs.error(msg)

                        # Extract the priority
                        try:
                            priority = att.get('priority', '99')
                            if len(priority) == 0:
                                priority = 99
                            else:
                                priority = int(priority)
                        except:
                            priority = 99

                        # Append the network to the list of networks
                        st = Stream(networkCode, stationCode, locationCode,
                                    streamCode)
                        tw = TW(startD, endD)

                        try:
                            # Check the overlap between the routes to import
                            # and the ones already present in the main Routing
                            # table
                            addIt = True
                            logs.debug('[RT] Checking %s\n' % str(st))
                            for testStr in ptRT.keys():
                                # This checks the overlap of Streams and also
                                # of timewindows and priority
                                if checkOverlap(testStr, ptRT[testStr], st,
                                                Route(service, address, tw, priority)):
                                    msg = '%s: Overlap between %s and %s!\n'\
                                        % (fileName, st, testStr)
                                    logs.error(msg)
                                    if not allowOverlap:
                                        logs.error('Skipping %s\n' % str(st))
                                        addIt = False
                                    break

                            if addIt:
                                ptRT[st].append(Route(service, address, tw, priority))
                            else:
                                logs.warning('Skip %s - %s\n' %
                                             (st, Route(service, address, tw,
                                                        priority)))

                        except KeyError:
                            ptRT[st] = [Route(service, address, tw, priority)]
                        serv.clear()

                    route.clear()

                root.clear()

    # Order the routes by priority
    for keyDict in ptRT:
        ptRT[keyDict] = sorted(ptRT[keyDict])

    return ptRT


def getArcRoutes(arcServ='eida.gfz-potsdam.de', arcPort=18001):
    """Connects via telnet to an Arclink server to get routing information.
The data is saved in the file ``routing.xml``. Generally used to start
operating with an EIDA default configuration.

:param arcServ: Arclink server address
:type arcServ: str
:param arcPort: Arclink server port
:type arcPort: int

.. warning::

    In the future this method should not be used and the configuration should
    be independent from Arclink. Namely, the ``routing.xml`` file must exist in
    advance.

    """

    logs = logging.getLogger('getArcRoutes')

    tn = telnetlib.Telnet(arcServ, arcPort)
    tn.write('HELLO\n')
    # FIXME The institution should be detected here. Shouldn't it?
    logs.info(tn.read_until('GFZ', 5))
    tn.write('user routing@eida\n')
    logs.debug(tn.read_until('OK', 5))
    tn.write('request routing\n')
    logs.debug(tn.read_until('OK', 5))
    tn.write('1920,1,1,0,0,0 2030,1,1,0,0,0 * * * *\nEND\n')

    reqID = 0
    while not reqID:
        text = tn.read_until('\n', 5).splitlines()
        for line in text:
            try:
                testReqID = int(line)
            except:
                continue
            if testReqID:
                reqID = testReqID

    myStatus = 'UNSET'
    logs.debug('\n' + myStatus)
    while (myStatus in ('UNSET', 'PROCESSING')):
        sleep(1)
        tn.write('status %s\n' % reqID)
        stText = tn.read_until('END', 15)

        stStr = 'status='
        oldStatus = myStatus
        myStatus = stText[stText.find(stStr) + len(stStr):].split()[0]
        myStatus = myStatus.replace('"', '').replace("'", "")
        if myStatus == oldStatus:
            logs.debug('.')
        else:
            logs.debug('\n' + myStatus)

    if myStatus != 'OK':
        logs.error('Error! Request status is not OK.\n')
        return

    tn.write('download %s\n' % reqID)
    routTable = tn.read_until('END', 180)
    start = routTable.find('<')
    logs.info('\nLength: %s\n' % routTable[:start])

    here = os.path.dirname(__file__)
    try:
        os.remove(os.path.join(here, 'routing.xml.download'))
    except:
        pass

    with open(os.path.join(here, 'routing.xml.download'), 'w') as fout:
        fout.write(routTable[routTable.find('<'):-3])

    try:
        os.rename(os.path.join(here, './routing.xml'),
                  os.path.join(here, './routing.xml.bck'))
    except:
        pass

    try:
        os.rename(os.path.join(here, './routing.xml.download'),
                  os.path.join(here, './routing.xml'))
    except:
        pass

    logs.info('Routing information succesfully read from Arclink!\n')


def getArcInv(arcServ='eida.gfz-potsdam.de', arcPort=18001):
    """Connects via telnet to an Arclink server to get inventory information.
The data is saved in the file ``Arclink-inventory.xml``. Generally used to
start operating with an EIDA default configuration.

:param arcServ: Arclink server address
:type arcServ: str
:param arcPort: Arclink server port
:type arcPort: int

.. deprecated:: since version 1.0.2

.. warning::

    In the future this method should not be used and the configuration should
    be independent from Arclink. Namely, the ``routing.xml`` file must exist in
    advance.

    """

    logs = logging.getLogger('getArcInv')

    logs.warning('This function should probably not be used! Be carefull!')

    tn = telnetlib.Telnet(arcServ, arcPort)
    tn.write('HELLO\n')
    # FIXME The institution should be detected here. Shouldn't it?
    logs.info(tn.read_until('GFZ', 5))
    tn.write('user routing@eida\n')
    logs.debug('\nuser routing@eida')
    logs.debug(tn.read_until('OK', 5))
    tn.write('request inventory\n')
    logs.debug('\nrequest inventory')
    logs.debug(tn.read_until('OK', 5))
    tn.write('1920,1,1,0,0,0 2030,1,1,0,0,0 * * * *\nEND\n')
    logs.debug('\n1920,1,1,0,0,0 2030,1,1,0,0,0 * * * *\nEND')

    reqID = 0
    while not reqID:
        text = tn.read_until('\n', 5).splitlines()
        for line in text:
            try:
                testReqID = int(line)
            except:
                continue
            if testReqID:
                reqID = testReqID

    logs.debug('status %s\n' % reqID)
    myStatus = 'UNSET'
    logs.debug('\n' + myStatus)
    while (myStatus in ('UNSET', 'PROCESSING')):
        sleep(1)
        tn.write('status %s\n' % reqID)
        stText = tn.read_until('END', 15)

        stStr = 'status='
        oldStatus = myStatus
        myStatus = stText[stText.find(stStr) + len(stStr):].split()[0]
        myStatus = myStatus.replace('"', '').replace("'", "")
        if myStatus == oldStatus:
            logs.debug('.')
        else:
            logs.debug('\n' + myStatus)

    if myStatus != 'OK':
        logs.error('Error! Request status is not OK.\n')
        return

    tn.write('download %s\n' % reqID)
    logs.debug('download %s\n' % reqID)
    here = os.path.dirname(__file__)
    try:
        os.remove(os.path.join(here, 'Arclink-inventory.xml.download'))
    except:
        pass

    # Write the downloaded file

    with open(os.path.join(here, 'Arclink-inventory.xml.download'), 'w') \
            as fout:
        #try:
        fd = tn.get_socket().makefile('rb+')
        # Read the size of the inventory
        length = fd.readline(100).strip()
        # Max number of retries
        maxRet = 8
        while not isinstance(length, int) and maxRet:
            try:
                length = int(length)
            except:
                sleep(1)
                tn.write('download %s\n' % reqID)
                logs.debug('Retrying! download %s\n' % reqID)
                length = fd.readline(100).strip()
                maxRet -= 1

        logs.info('\nExpected size: %s\n' % length)
        bytesRead = 0
        while bytesRead < length:
            buf = fd.read(min(4096, length - bytesRead))
            bytesRead += len(buf)
            bar = '|' + '=' * int(bytesRead * 100 / (2 * length)) + \
                ' ' * int((length - bytesRead) * 100 / (2 * length)) + '|'
            logs.debug('\r%s' % bar)
            fout.write(buf)

        buf = fd.readline(100).strip()
        if buf != "END" or bytesRead != length:
            raise Exception('Wrong length!')
        #finally:
        #    tn.write('PURGE %d\n' % reqID)

    try:
        os.rename(os.path.join(here, './Arclink-inventory.xml'),
                  os.path.join(here, './Arclink-inventory.xml.bck'))
    except:
        pass

    try:
        os.rename(os.path.join(here, './Arclink-inventory.xml.download'),
                  os.path.join(here, './Arclink-inventory.xml'))
    except:
        pass

    logs.info('\nInventory read from Arclink!\n')


def mergeRoutes(synchroList):
    """Retrieve routes from different sources and merge them with the local
ones in the routing table. The configuration file is checked to see whether
overlapping routes are allowed or not. A pickled version of the three routing
tables is saved in ``routing.bin``.

:param synchroList: List of data centres where routes should be imported from
:type synchroList: str

"""

    logs = logging.getLogger('mergeRoutes')

    ptRT = addRoutes('./routing.xml')

    for line in synchroList.splitlines():
        if not len(line):
            break
        logs.debug(str(line.split(',')))
        dcid, url = line.split(',')
        try:
            addRemote('./routing-' + dcid.strip() + '.xml', url.strip(), logs)
        except:
            msg = 'Failure updating routing information from %s (%s)' % \
                (dcid, url)
            logs.error(msg)

        if os.path.exists('./routing-' + dcid.strip() + '.xml'):
            # FIXME addRoutes should return no Exception ever and skip a
            # problematic file returning a coherent version of the routes
            ptRT = addRoutes('./routing-' + dcid.strip() + '.xml',
                                         ptRT, logs)

    try:
        os.remove('./routing.bin')
    except:
        pass

    with open('./routing.bin', 'wb') as finalRoutes:
        pickle.dump((ptRT, ptSL, ptST), finalRoutes)
        logs.info('Routes in main Routing Table: %s\n' % len(ptRT))


def main(logLevel=2):
    # FIXME logLevel must be used via argparser
    # Check verbosity in the output
    config = configparser.RawConfigParser()
    here = os.path.dirname(__file__)
    config.read(os.path.join(here, '..', 'ownDC.cfg'))
    #verbo = config.getint('Service', 'verbosity')
    verbo = config.get('Service', 'verbosity')
    # Warning is the default value
    verboNum = getattr(logging, verbo.upper(), 30)

    logging.basicConfig(level=verboNum)
    logs = logging.getLogger('getEIDAconfig')

    # Check Arclink server that must be contacted to get a routing table
    arcServ = config.get('Arclink', 'server')
    arcPort = config.getint('Arclink', 'port')

    getArcRoutes(arcServ, arcPort)
    #getArcInv(arcServ, arcPort)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(int(sys.argv[1]))
    else:
        main()
