#!/usr/bin/python

import os
import sys
import telnetlib
import argparse
from time import sleep
import logging

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

sys.path.append('..')
from utils import Route
from utils import RoutingCache

"""
.. todo::
    We need to include a function that is able to "translate" from arclink
    to dataselect. It should read routing.xml.download and change the addresses
    and services following the same table that we had previously.

"""


def mapArcFDSN(route):
    """Map from an Arclink address to a Dataselect one

:param route: Arclink route
:type route: str
:returns: Base URL equivalent of the given Arclink route
:rtype: str
:raises: Exception

    """

    gfz = 'http://geofon.gfz-potsdam.de'
    odc = 'http://www.orfeus-eu.org'
    eth = 'http://eida.ethz.ch'
    resif = 'http://ws.resif.fr'
    ingv = 'http://webservices.rm.ingv.it'
    bgr = 'http://eida.bgr.de'
    lmu = 'http://erde.geophysik.uni-muenchen.de'
    ipgp = 'http://eida.ipgp.fr'
    niep = 'http://eida-sc3.infp.ro'
    koeri = 'http://eida-service.koeri.boun.edu.tr'

    # Try to identify the hosting institution
    host = route.split(':')[0]

    if host.endswith('gfz-potsdam.de'):
        return gfz
    elif host.endswith('knmi.nl'):
        return odc
    elif host.endswith('ethz.ch'):
        return eth
    elif host.endswith('resif.fr'):
        return resif
    elif host.endswith('ingv.it'):
        return ingv
    elif host.endswith('bgr.de'):
        return bgr
    elif host.startswith('141.84.') or host.endswith('uni-muenchen.de'):
        return lmu
    elif host.endswith('ipgp.fr'):
        return ipgp
    elif host.endswith('infp.ro'):
        return niep
    elif host.endswith('boun.edu.tr') or host.startswith('193.140.203'):
        return koeri
    raise Exception('No FDSN-WS equivalent found for %s' % route)


def arc2fdsnws(filein, fileout, config='../ownDC.cfg'):
    """Read the routing file in XML format and add the Dataselect and Station
routes based on the Arclink information. The resulting table is stored in

:param filein: Input file with routes (usually from an Arclink server).
:type filein: str
:param fileout: Output file with all routes from the input file plus new
                Station and Dataselect routes based on the Arclink route.
:type fileout: str
"""
    rc = RoutingCache(filein, config=config)
    for st, lr in rc.routingTable.iteritems():
        toAdd = list()
        for r in lr:
            if r.service == 'arclink':
                stat = Route('station', '%s/fdsnws/station/1/query' %
                             mapArcFDSN(r.address), r.tw, r.priority)
                toAdd.append(stat)

                data = Route('dataselect', '%s/fdsnws/dataselect/1/query' %
                             mapArcFDSN(r.address), r.tw, r.priority)
                toAdd.append(data)

        lr.extend(toAdd)

    rc.toXML(fileout)


def getArcRoutes(arcServ='eida.gfz-potsdam.de', arcPort=18001,
                 foutput='routing.xml'):
    """Connects via telnet to an Arclink server to get routing information.
The data is saved in the file specified by foutput. Generally used to start
operating with an EIDA default configuration.

:param arcServ: Arclink server address
:type arcServ: str
:param arcPort: Arclink server port
:type arcPort: int
:param foutput: Filename where the output must be saved
:type foutput: str

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
        os.remove(os.path.join(here, '%s.download' % foutput))
    except:
        pass

    with open(os.path.join(here, '%s.download' % foutput), 'w') as fout:
        fout.write(routTable[routTable.find('<'):-3])

    try:
        os.rename(os.path.join(here, foutput),
                  os.path.join(here, '%s.bck' % foutput))
    except:
        pass

    try:
        os.rename(os.path.join(here, '%s.download' % foutput),
                  os.path.join(here, foutput))
    except:
        pass

    logs.info('Routing information succesfully read from Arclink!\n')


def main():
    # FIXME logLevel must be used via argparser
    # Check verbosity in the output
    desc = 'Get EIDA routes and "export" them to the FDSN-WS style.'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('-l', '--loglevel',
                        help='Verbosity in the output.',
                        choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO',
                                 'DEBUG'])
    parser.add_argument('-s', '--server',
                        help='Arclink server address (address.domain:18001).')
    parser.add_argument('-c', '--config',
                        help='Config file to use.',
                        default='../ownDC.cfg')
    args = parser.parse_args()

    config = configparser.RawConfigParser()
    config.read(args.config)

    # Command line parameter has priority
    try:
        verbo = getattr(logging, args.loglevel)
    except:
        # If no command-line parameter then read from config file
        try:
            verbo = config.get('Service', 'verbosity')
            verbo = getattr(logging, verbo)
        except:
            # Otherwise, default value
            verbo = logging.INFO

    # INFO is the default value
    logging.basicConfig(level=verbo)
    logs = logging.getLogger('getEIDAconfig')

    # Check Arclink server that must be contacted to get a routing table
    if args.server:
        arcServ, arcPort = args.server.split(':')
    else:
        # If no command-line parameter then read from config file
        try:
            arcServ = config.get('Arclink', 'server')
            arcPort = config.getint('Arclink', 'port')
        except:
            # Otherwise, default value
            arcServ = 'eida.gfz-potsdam.de'
            arcPort = 18002

    getArcRoutes(arcServ, arcPort, 'ownDC-routes-tmp.xml')
    logs.debug('Translating Arclink routes to FDSN WS')
    arc2fdsnws('ownDC-routes-tmp.xml', 'ownDC-routes.xml', config=args.config)
    try:
        logs.debug('Remove temporary files (1/2)')
        os.remove('ownDC-routes-tmp.xml')
    except:
        pass

    try:
        logs.debug('Remove temporary files (2/2)')
        os.remove('ownDC-routes-tmp.xml.bin')
    except:
        pass


if __name__ == '__main__':
    main()
