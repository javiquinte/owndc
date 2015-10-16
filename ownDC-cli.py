#!/usr/bin/python

import sys
import argparse
from urlparse import urlparse
from urlparse import parse_qs
import logging
from query import DataSelectQuery


class SummarizedRun(dict):
    def __init__(self, tws):
        for line in tws.splitlines():
            self[line] = list()

    def __url2nslc(self, url):
        params = parse_qs(urlparse(url).query)
        # Extract NET
        if 'net' in params:
            net = params['net'][0]
        elif 'network' in params:
            net = params['network'][0]
        else:
            net = '*'

        # Extract STA
        if 'sta' in params:
            sta = params['sta'][0]
        elif 'station' in params:
            sta = params['station'][0]
        else:
            sta = '*'

        # Extract LOC
        if 'loc' in params:
            loc = params['loc'][0]
        elif 'location' in params:
            loc = params['location'][0]
        else:
            loc = '*'

        # Extract CHA
        if 'cha' in params:
            cha = params['cha'][0]
        elif 'channel' in params:
            cha = params['channel'][0]
        else:
            cha = '*'

        # Extract START
        if 'start' in params:
            startt = params['start'][0]
        elif 'starttime' in params:
            startt = params['starttime'][0]
        else:
            startt = '*'

        # Extract END
        if 'end' in params:
            endt = params['end'][0]
        elif 'endtime' in params:
            endt = params['endtime'][0]
        else:
            endt = '*'

        return '%s %s %s %s %s %s' % (net, sta, loc, cha, startt, endt)

    def log(self, le, *args, **kwargs):
        
        print self.__url2nslc(le.line)
        try:
            self[self.__url2nslc(le.line)] = self[line].append((le.dt, le.code, le.bytes))
        except:
            self[self.__url2nslc(le.line)] = [(le.dt, le.code, le.bytes)]
        pass


def main():
    parser = argparse.ArgumentParser(description=\
        'Client to download waveforms from different datacentres via FDSN-WS')
    parser.add_argument('-c', '--config', help='Config file.',
                        default='ownDC.cfg')
    parser.add_argument('-p', '--post-file', default=None,
                        help='File with the streams and timewindows requested.')
    parser.add_argument('-o', '--output', default='request',
                        help='Filename used to save the data and the logs.')
    parser.add_argument('-r', '--retries',
                        help='Number of times that data should be requested if there is no answer or if there is an error',
                        default=3)
    parser.add_argument('-v', '--verbosity', action="count", default=0,
                        help='Increase the verbosity level')
    args = parser.parse_args()
    
    # Read the streams and timewindows to download
    if args.post_file is not None:
        fh = open(args.post_file, 'r')
    else:
        fh = sys.stdin

    lines = fh.read()
    summary = SummarizedRun(lines)

    print summary
    ds = DataSelectQuery(summary,
                         routesFile='data/ownDC-routes.xml',
                         configFile='ownDC.cfg')
    iterObj = ds.makeQueryPOST(lines)

    outwav = open('%s.mseed' % args.output, 'wb')
    #outlog = open('%s.log' % args.output, 'w')

    for chunk in iterObj:
        outwav.write(chunk)

    print summary

if __name__ == '__main__':
    main()
