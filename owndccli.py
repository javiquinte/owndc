#!/usr/bin/env python2

import sys
import argparse
from urlparse import urlparse
from urlparse import parse_qs
from time import sleep
import logging
from owndc import DataSelectQuery
from version import get_git_version


class SummarizedRun(dict):
    def __init__(self, tws=None):
        self.mapCode = dict()
        self.mapCode[0] = 'ERROR'
        self.mapCode[200] = 'OK'
        self.mapCode[400] = 'BAD REQUEST'
        self.mapCode[500] = 'SERVER ERROR'
        self.mapCode[204] = 'NODATA'

        if tws is not None:
            for line in tws.splitlines():
                self[line] = list()

    def __code2desc(self, httpCode):
        try:
            return self.mapCode[httpCode]
        except:
            return str(httpCode)

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
            # Append another log item to the proper request line
            self[self.__url2nslc(le.line)].append((le.dt, self.__code2desc(le.code), le.bytes))
        except:
            self[self.__url2nslc(le.line)] = [(le.dt, self.__code2desc(le.code), le.bytes)]
        pass


def main():
    owndcver = '0.9a2'

    parser = argparse.ArgumentParser(description=\
        'Client to download waveforms from different datacentres via FDSN-WS')
    parser.add_argument('-c', '--config', help='Config file.',
                        default='owndc.cfg')
    parser.add_argument('-p', '--post-file', default=None,
                        help='File with the streams and timewindows requested.')
    parser.add_argument('-o', '--output', default='request',
                        help='Filename (without extension) used to save the data and the logs.')
    parser.add_argument('-r', '--retries', type=int,
                        help='Number of times that data should be requested if there is no answer or if there is an error',
                        default=0)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-s", "--seconds", type=int,
                        help='Number of seconds between retries for the lines without data')
    group.add_argument("-m", "--minutes", type=int,
                        help='Number of minutes between retries for the lines without data')
    parser.add_argument('-v', '--verbosity', action="count", default=0,
                        help='Increase the verbosity level')
    parser.add_argument('--version', action='version', version='owndc-cli %s ' % get_git_version())
    args = parser.parse_args()
    
    # Read the streams and timewindows to download
    if args.post_file is not None:
        fh = open(args.post_file, 'r')
    else:
        fh = sys.stdin

    lines = fh.read()
    summary = SummarizedRun()

    ds = DataSelectQuery(summary,
                         routesFile='data/owndc-routes.xml',
                         configFile=args.config)

    outwav = open('%s.mseed' % args.output, 'wb')

    # Attempt number to download the waveforms
    attempt = 0

    while ((attempt <= args.retries) and (len(lines.splitlines()) > 0)):
        print '\n\nAttempt Nr. %d of %d' % (attempt+1, args.retries+1)

        iterObj = ds.makeQueryPOST(lines)
        
        for chunk in iterObj:
            outwav.write(chunk)
            print '.',

        print

        lines = ''
        for k, v in summary.iteritems():

            # Print summary
            totBytes = sum([l[2] for l in v])
            status = ','.join([l[1] for l in v])

            print '[%s] %s %d bytes' % ('\033[92mOK\033[0m' if totBytes else \
                                        '\033[91m' + status + '\033[0m', k, totBytes)
            # Check the total amount of bytes received
            if totBytes <= 0:
                lines = '%s%s\n' % (lines, k)

        attempt += 1

        if args.minutes:
            print 'Waiting %d minutes to retry again...' % args.minutes
            sleep(args.minutes * 60)
        else:
            seconds = 2 if args.seconds is None else args.seconds
            
            print 'Waiting %d seconds to retry again...' % seconds
            sleep(seconds)

    outwav.close()
    
    # FIXME I should decide here a nice format for the output
    # and also if it should be to stdout, a file or a port
    with open('%s.log' % args.output, 'w') as outlog:
        for k, v in summary.iteritems():
            outlog.write('%s %s %d bytes\n' % (k, [le[1] for le in v], sum([le[2] for le in v])))

if __name__ == '__main__':
    main()
