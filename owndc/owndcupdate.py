#!/usr/bin/env python2

"""Retrieve data from a Routing WS to be used locally

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
any later version.

   :Copyright:
       2017 Javier Quinteros, GEOFON, GFZ Potsdam <geofon@gfz-potsdam.de>
   :License:
       GPLv3
   :Platform:
       Linux

.. moduleauthor:: Javier Quinteros <javier@gfz-potsdam.de>, GEOFON, GFZ Potsdam
"""

import os
import argparse
import logging
import urllib2 as ul

try:
    import cPickle as pickle
except ImportError:
    import pickle

import ConfigParser as configparser

try:
    from routing.routeutils.utils import addRemote
    from routing.routeutils.utils import addRoutes
    from routing.routeutils.utils import addVirtualNets
    from routing.routeutils.utils import cacheStations
    from routing.routeutils.utils import Route
    from routing.routeutils.utils import RoutingCache
except:
    raise


def mergeRoutes(fileRoutes, synchroList, allowOverlaps=False):
    """Retrieve routes from different sources and merge them with the local
ones in the routing tables. The configuration file is checked to see whether
overlapping routes are allowed or not. A pickled version of the the routing
table is saved under the same filename plus ``.bin`` (e.g. owndc-tmp.xml.bin).

:param fileRoutes: File containing the local routing table
:type fileRoutes: str
:param synchroList: List of data centres where routes should be imported from
:type synchroList: str
:param allowOverlaps: Specify if overlapping streams should be allowed or not
:type allowOverlaps: boolean

"""

    logs = logging.getLogger('mergeRoutes')
    logs.info('Synchronizing with: %s' % synchroList)

    ptRT = addRoutes(fileRoutes, allowOverlaps=allowOverlaps)
    ptVN = addVirtualNets(fileRoutes)

    for line in synchroList.splitlines():
        if not len(line):
            break
        logs.debug(str(line.split(',')))
        dcid, url = line.split(',')
        try:
            addRemote(os.path.join(os.path.expanduser('~'), '.owndc', 'data', 'owndc-%s.xml' % dcid.strip()),
                      url.strip())
        except:
            msg = 'Failure updating routing information from %s (%s)' % \
                (dcid, url)
            logs.error(msg)

        if os.path.exists(os.path.join(os.path.expanduser('~'), '.owndc', 'data', 'owndc-%s.xml' % dcid.strip())):
            # FIXME addRoutes should return no Exception ever and skip a
            # problematic file returning a coherent version of the routes
            print 'Adding REMOTE %s' % dcid
            ptRT = addRoutes(os.path.join(os.path.expanduser('~'), '.owndc', 'data', 'owndc-%s.xml' % dcid.strip()),
                             routingTable=ptRT, allowOverlaps=allowOverlaps)
            ptVN = addVirtualNets(os.path.join(os.path.expanduser('~'), '.owndc', 'data', 'owndc-%s.xml' % dcid.strip()),
                                  vnTable=ptVN)

    try:
        os.remove(os.path.join(os.path.expanduser('~'), '.owndc', 'data', '%s.bin' % fileRoutes))
    except:
        pass

    stationTable = dict()
    cacheStations(ptRT, stationTable)

    fname = os.path.join(os.path.expanduser('~'), '.owndc', 'data', '%s.bin' % fileRoutes)
    with open(fname, 'wb') as finalRoutes:
        pickle.dump((ptRT, stationTable, ptVN), finalRoutes)
        logs.info('Routes in main Routing Table: %s\n' % len(ptRT))
        logs.info('Stations cached: %s\n' %
                  sum([len(stationTable[dc][st]) for dc in stationTable
                       for st in stationTable[dc]]))
        logs.info('Virtual Networks defined: %s\n' % len(ptVN))


def main():
    # FIXME logLevel must be used via argparser
    # Check verbosity in the output
    msg = 'Prefill the owndc configuration with the routes from EIDA.'
    parser = argparse.ArgumentParser(description=msg)
    parser.add_argument('-l', '--loglevel',
                        help='Verbosity in the output.',
                        choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO',
                                 'DEBUG'])
    # parser.add_argument('-s', '--server',
    #                     help='Arclink server address (address.domain:18001).')
    cfgname = os.path.join(os.path.expanduser('~'), '.owndc', 'owndc.cfg')
    master = os.path.join(os.path.expanduser('~'), '.owndc', 'data', 'masterTable.xml')
    routes = os.path.join(os.path.expanduser('~'), '.owndc', 'data', 'owndc-routes.xml')
    # parser.add_argument('-c', '--config',
    #                     help='Config file to use.',
    #                     default=cfgname)
    parser.add_argument('--reset', action="store_true",
                        help='Remove all configuration files and routes.')
    args = parser.parse_args()

    if args.reset:
        try:
            os.remove(cfgname)
        except:
            pass

        if not os.path.exists(os.path.dirname(cfgname)):
            os.makedirs(os.path.dirname(cfgname))

        url = "https://raw.githubusercontent.com/javiquinte/owndc/package/owndc.cfg.sample"
        cfg = ul.urlopen(url)
        with open(cfgname, "w") as fout:
            fout.write(cfg.read())

    config = configparser.RawConfigParser()
    if not len(config.read(cfgname)):
        print('Configuration file %s could not be read' % cfgname)

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
    logs = logging.getLogger('update')
    logs.setLevel(verbo)

    if args.reset:
        try:
            os.remove(master)
            logging.debug('Master table removed.')
        except:
            pass
        try:
            os.remove(routes)
            logging.debug('Local routes removed.')
        except:
            pass

        if not os.path.exists(os.path.dirname(master)):
            logging.debug('Creating .owndc/data under home directory.')
            os.makedirs(os.path.dirname(master))

        url = "https://raw.githubusercontent.com/javiquinte/owndc/package/data/masterTable.xml"
        mas = ul.urlopen(url)
        with open(master, "w") as fout:
            logging.debug('Creating a standard master table from Github.')
            fout.write(mas.read())

        if not os.path.exists(os.path.dirname(routes)):
            logging.debug('Creating .owndc/data under home directory.')
            os.makedirs(os.path.dirname(routes))

        url = "https://raw.githubusercontent.com/javiquinte/owndc/package/data/owndc-routes.xml"
        rou = ul.urlopen(url)
        with open(routes, "w") as fout:
            logging.debug('Creating a standard routing table from Github.')
            fout.write(rou.read())

    try:
        os.remove(routes + '.bin')
    except:
        pass

    try:
        synchroList = config.get('Service', 'synchronize')
    except:
        # Otherwise, default value
        synchroList = ''

    logs.warning('This process can take up 5 minutes to finalize!')
    mergeRoutes(routes, synchroList)


if __name__ == '__main__':
    main()
