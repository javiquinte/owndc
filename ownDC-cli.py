#!/usr/bin/python

import sys
import argparse
from urlparse import urlparse
from urlparse import parse_qs
import logging
from query import DataSelectQuery


class SummarizedRun(dict):
    def __init__(self, tws=None):
        if tws is not None:
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
                        help='Filename (without extension) used to save the data and the logs.')
    parser.add_argument('-r', '--retries', type=int,
                        help='Number of times that data should be requested if there is no answer or if there is an error',
                        default=0)
    parser.add_argument('-m', '--minutes',
                        help='Number of minutes between retries for the lines without data',
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
    #summary = SummarizedRun(lines)
    summary = SummarizedRun()

    ds = DataSelectQuery(summary,
                         routesFile='data/ownDC-routes.xml',
                         configFile=args.config)

    outwav = open('%s.mseed' % args.output, 'wb')

    # Attempt number to download the waveforms
    attempt = 0

    while ((attempt <= args.retries) and (len(lines.splitlines()) > 0)):
        print 'Attempt Nr. %d of %d' % (attempt+1, args.retries+1)

        iterObj = ds.makeQueryPOST(lines)
        
        for chunk in iterObj:
            outwav.write(chunk)

        lines = ''
        for k, v in summary.iteritems():
            if sum([l[2] for l in v]) <= 0:
                lines = '%s%s\n' % (lines, k)

        attempt += 1
        print 'Summary', summary
        print 'Lines\n', lines

    
    # FIXME I should decide here a nice format for the output
    # and also if it should be to stdout, a file or a port
    with open('%s.log' % args.output, 'w') as outlog:
        for k, v in summary.iteritems():
            outlog.write('%s %s %d bytes\n' % (k, [le[1] for le in v], sum([le[2] for le in v])))

    outwav.close()

if __name__ == '__main__':
    main()
