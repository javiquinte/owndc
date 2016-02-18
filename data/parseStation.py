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

parseStation('GE-resp.xml')
