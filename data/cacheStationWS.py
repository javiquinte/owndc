#!/usr/bin/python

import sys
import os
import argparse
import logging
from collections import namedtuple
import xml.etree.cElementTree as ET


# More Python 3 compatibility
try:
    import urllib.request as ul
except ImportError:
    import urllib2 as ul

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

sys.path.append('..')
from utils import RoutingCache
from utils import text2Datetime

"""
.. todo::
    We need to include a function that is able to "translate" from arclink
    to dataselect. It should read routing.xml.download and change the addresses
    and services following the same table that we had previously.

"""


class Station(namedtuple('Station', ['network', 'station', 'latitutde',
                                     'longitude', 'elevation',
                                     'sitedescription', 'start', 'end'])):
    __slots__ = ()


def parseStation(fileName, **kwargs):
    """Read the stationXML file and split it into pieces.

The input file is expected to include the 'response' level. We generate one file
per object (e.g. one for network, one for each station and so on).

:param fileName: File with routes to add the the routing table.
:type fileName: str
"""

    logs = logging.getLogger('parseStation')
    logs.debug('Entering parseStation(%s)\n' % fileName)

    with open(fileName, 'r') as testFile:
        # Parse the station file
        # Traverse through the networks
        # get an iterable
        try:
            context = ET.iterparse(testFile, events=("start", "end"))
        except IOError:
            msg = 'Error: %s could not be parsed. Skipping it!\n' % fileName
            logs.error(msg)
            return

        # turn it into an iterator
        context = iter(context)

        # get the root element
        # More Python 3 compatibility
        if hasattr(context, 'next'):
            event, root = context.next()
        else:
            event, root = next(context)

        # Extract the namespace from the root node
        # FIXME This should be checked against IRIS
        namesp = root.tag[:root.tag.find('}') + 1]

        for event, netw in context:
            # Loop through the events and elements in the upper hierarchy
            if event == "end":
                # Check that this is a Network
                if netw.tag == '%sNetwork' % namesp:

                    # Include another element at the top, so that the namespace
                    # definition is here and NOT in the Network
                    fullXML = ET.ElementTree(ET.Element('FDSNXML'))
                    auxRoot = fullXML.getroot()
                    # Create an Element based on the original one but without
                    # namespace in the tag
                    auxRoot.append(ET.Element('Network', netw.attrib))
                    n2Save = auxRoot.find('Network')

                    # Iterate through the stations
                    for stat in netw:
                        # Everything at this level that is NOT a Station should
                        # be added to the Network
                        if stat.tag != '%sStation' % namesp:
                            subNet = ET.Element(stat.tag[len(namesp):],
                                                stat.attrib)
                            subNet.text = stat.text
                            n2Save.append(subNet)

                        else:
                            # Create the Station without NS
                            s2Save = ET.Element('Station', stat.attrib)

                            for cha in stat:
                                # Add everything that is not a Channel
                                if cha.tag != '%sChannel' % namesp:
                                    subSta = ET.Element(
                                        cha.tag[len(namesp):],
                                        cha.attrib)
                                    subSta.text = cha.text
                                    s2Save.append(subSta)
                                else:
                                    # Create the Channel
                                    c2Save = ET.Element('Channel', cha.attrib)

                                    for resp in cha:
                                        # Add everything that is not a Response
                                        if resp.tag != '%sResponse' % namesp:
                                            subCha = ET.Element(
                                                resp.tag[len(namesp):],
                                                resp.attrib)
                                            subCha.text = resp.text
                                            c2Save.append(subCha)
                                        else:
                                            # Create a Response from the
                                            # original Element. Mainly because
                                            # we need all the content and we
                                            # won't iterate to parse it
                                            clearResp = ET.tostringlist(resp)
                                            # Check in the first 10 lines if
                                            # there is a NS and delete it
                                            for i, ln in enumerate(clearResp[:10]):
                                                lns = ln.split()
                                                lns2 = [x for x in lns if not x.startswith('xmlns:ns0=')]
                                                clearResp[i] = ''.join(lns2)

                                            # Remove all traces from a NS
                                            for i, ln in enumerate(clearResp):
                                                clearResp[i] = ln.replace('ns0:', '')

                                            # Save the Response file (includes
                                            # closing element
                                            with open('%s.%s.%s.resp.xml' %
                                                      (netw.get('code'),
                                                       stat.get('code'),
                                                       cha.get('code')),
                                                      'w') as rf:
                                                rf.write(
                                                    ''.join(clearResp))
                                            resp.clear()

                                    # Save the Channel file without the closing
                                    # element!
                                    with open('%s.%s.%s.xml' %
                                              (netw.get('code'),
                                               stat.get('code'),
                                               cha.get('code')),
                                              'w') as cf:
                                        cf.write(''.join(ET.tostringlist(
                                            c2Save)[:-1]))
                                    cha.clear()

                            # Save the Station file without the closing element!
                            with open('%s.%s.xml' %
                                      (netw.get('code'), stat.get('code')),
                                      'w') as sf:
                                sf.write(''.join(ET.tostringlist(s2Save)[:-1]))
                            stat.clear()

                    # Save the Network file without the closing element!
                    with open('%s.xml' % netw.get('code'), 'w') as nf:
                        nf.write(''.join(ET.tostringlist(n2Save)[:-1]))
                    netw.clear()

                root.clear()

    return


def readFromURL(url, foutName=None):
    # FIXME For sure I would like to change the approach here and use yield to
    # send data in chunks.
    # Read at most in chunks of 1 MB
    blockSize = 1024 * 1024

    dcBytes = 0
    if foutName is not None:
        fout = open(foutName, 'wb')
    else:
        dcResult = ''

    logging.debug('Querying %s' % url)
    req = ul.Request(url)

    try:
        u = ul.urlopen(req)

        # Read the data in blocks of predefined size
        try:
            buffer = u.read(blockSize)
        except:
            logging.error('Error while querying %s' % url)

        if not len(buffer):
            logging.debug('Error code: %s' % u.getcode())

        while len(buffer):
            dcBytes += len(buffer)
            # Return one block of data
            if foutName is not None:
                fout.write(buffer)
            else:
                dcResult += buffer

            try:
                buffer = u.read(blockSize)
            except:
                logging.error('Error while querying %s' % url)
            logging.debug('%s bytes from %s' % (dcBytes, url))

        # Close the connection to avoid overloading the server
        logging.debug('%s bytes from %s' % (dcBytes, url))
        u.close()

    except ul.URLError as e:
        if hasattr(e, 'reason'):
            logging.error('%s - Reason: %s' % (url, e.reason))
        elif hasattr(e, 'code'):
            logging.error('The server couldn\'t fulfill the request')
            logging.error('Error code: %s' % e.code)

    except Exception as e:
        logging.error('%s' % e)

    if foutName is not None:
        fout.close()
        return dcBytes
    else:
        return dcResult


def expandStation(dcURL, net='*', sta='*', loc='*', cha='*', start=None,
                  endt=None, format='text', level='station'):
    stationQuery = '%s?net=%s&sta=%s&loc=%s&cha=%s&format=%s&level=%s'

    aux = stationQuery % (dcURL, net, sta, loc, cha, format, level)

    if start is not None:
        aux += '&start=%s' % start.isoformat()

    if endt is not None:
        aux += '&end=%s' % endt.isoformat()

    # FIXME This function should be seriously tested!
    dcResult = readFromURL(aux)

    listResult = list()
    for st in dcResult.splitlines()[1:]:
        splSt = st.split('|')
        # logging.debug('%s' % splSt)
        try:
            splSt[6] = text2Datetime(splSt[6])
        except ValueError:
            logging.error("Couldn't convert start time attribute (%s)."
                          % splSt[6])
            continue

        try:
            splSt[7] = text2Datetime(splSt[7])
        except ValueError:
            splSt[7] = None

        splSt[2] = float(splSt[2])
        splSt[3] = float(splSt[3])
        splSt[4] = float(splSt[4])

        staTup = Station(*splSt)
        listResult.append(staTup)

    logging.info('%s stations found' % len(listResult))

    return listResult


def cacheStationWS(routes):
    rc = RoutingCache(routes)
    # Iterate for the defined Routes and cache the ones related to the
    # Station-WS
    # The values are lists of Routes
    rt = rc.routingTable
    for st, lR in rt.iteritems():
        dcURL = None
        for r in lR:
            if r.service != 'station':
                continue
            # I need to query here
            dcURL = r.address
            start = r.tw.start
            endt = r.tw.end
            break

        logging.debug('%s %s' % (st, dcURL))
        # Loop for all stations and do a query for every station. Mainly to
        # avoid problems with the limits on the size of the query or the results
        if st.s == '*':
            # Expand the station list
            listSta = [x.station for x in expandStation(dcURL, st.n, '*',
                                                        st.l,
                                                        st.c)]
        else:
            listSta = [st.s]

        logging.debug('%s' % listSta)
        stationQuery = '%s?net=%s&sta=%s&loc=%s&cha=%s&format=%s&level=%s'

        for sta in listSta:
            aux = stationQuery % (dcURL, st.n, sta, st.l, st.c,
                                  'xml', 'response')

            if start is not None:
                aux += '&start=%s' % start.isoformat()

            if endt is not None:
                aux += '&end=%s' % endt.isoformat()

            # FIXME This function should be seriously tested!
            dcBytes = readFromURL(aux, '%s-%s-resp.xml' % (st.n, sta))
            logging.info('%d Bytes received for station %s.%s' %
                         (dcBytes, st.n, sta))
            if dcBytes:
                try:
                    parseStation('%s-%s-resp.xml' % (st.n, sta))
                    os.remove('%s-%s-resp.xml' % (st.n, sta))
                except Exception as e:
                    raise e



def main():
    # FIXME logLevel must be used via argparser
    # Check verbosity in the output
    desc = 'Read the Routes available for the Station-WS and cache the data.'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('-l', '--loglevel',
                        help='Verbosity in the output.',
                        choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO',
                                 'DEBUG'])
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
    logs = logging.getLogger('cachestationWS')

    logs.debug('Reading routes and starting caching procedure')
    cacheStationWS('ownDC-routes.xml')

if __name__ == '__main__':
    main()
