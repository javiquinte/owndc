#!/usr/bin/env python

import logging
import xml.etree.cElementTree as ET


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

        # Check that it is really a StationXML
        # FIXME This verification should be corrected, checked and enabled again
        # if root.tag[-len('routing'):] != 'routing':
        #     msg = '%s seems not to be a routing file (XML). Skipping it!\n' \
        #         % fileName
        #     logs.error(msg)
        #     return ptRT

        # Extract the namespace from the root node
        # FIXME This should be checked against IRIS
        namesp = root.tag[:root.tag.find('}') + 1]

        for event, netw in context:
            # The tag of this node should be "Network".
            # Now it is not being checked because
            # we need all the data, but if we need to filter, this
            # is the place.
            #
            if event == "end":
                # if netw.tag != 'Network':
                #     print 'Error! netw.tag = %s' % netw.tag
                #     return

                # print netw.tag, namesp
                if netw.tag == '%sNetwork' % namesp:

                    fullXML = ET.ElementTree(ET.Element('FDSNXML'))
                    auxRoot = fullXML.getroot()
                    auxRoot.append(ET.Element('Network', netw.attrib))
                    n2Save = auxRoot.find('Network')

                    # Traverse through the sources
                    for stat in netw:
                        if stat.tag != '%sStation' % namesp:
                            subNet = ET.Element(stat.tag[len(namesp):],
                                                stat.attrib)
                            subNet.text = stat.text
                            # n2Save.append(subNet)
                            n2Save.append(subNet)

                        else:
                            s2Save = ET.Element('Station', stat.attrib)

                            for cha in stat:
                                if cha.tag != '%sChannel' % namesp:
                                    subSta = ET.Element(
                                        cha.tag[len(namesp):],
                                        cha.attrib)
                                    subSta.text = cha.text
                                    s2Save.append(subSta)
                                else:
                                    c2Save = ET.Element('Channel', cha.attrib)

                                    for resp in cha:
                                        if resp.tag != '%sResponse' % namesp:
                                            subCha = ET.Element(
                                                resp.tag[len(namesp):],
                                                resp.attrib)
                                            subCha.text = resp.text
                                            c2Save.append(subCha)
                                        else:
                                            clearResp = ET.tostringlist(resp)
                                            for i, ln in enumerate(clearResp[:10]):
                                                lns = ln.split()
                                                lns2 = [x for x in lns if not x.startswith('xmlns:ns0=')]
                                                clearResp[i] = ''.join(lns2)

                                            for i, ln in enumerate(clearResp):
                                                clearResp[i] = ln.replace('ns0:', '')

                                            with open('%s.%s.%s.resp.xml' %
                                                      (netw.get('code'),
                                                       stat.get('code'),
                                                       cha.get('code')),
                                                      'w') as rf:
                                                rf.write(
                                                    ''.join(clearResp))
                                            resp.clear()

                                    with open('%s.%s.%s.xml' %
                                              (netw.get('code'),
                                               stat.get('code'),
                                               cha.get('code')),
                                              'w') as cf:
                                        cf.write(''.join(ET.tostringlist(
                                            c2Save)[:-1]))
                                    cha.clear()

                            with open('%s.%s.xml' %
                                      (netw.get('code'), stat.get('code')),
                                      'w') as sf:
                                sf.write(''.join(ET.tostringlist(s2Save)[:-1]))
                            stat.clear()

                    with open('%s.xml' % netw.get('code'), 'w') as nf:
                        nf.write(''.join(ET.tostringlist(n2Save)[:-1]))
                    netw.clear()

                root.clear()

    return

parseStation('GE-resp.xml')
