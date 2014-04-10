#!/usr/bin/env python
#
# FDSN-WS Dataselect prototype
#
# (c) 2014 Javier Quinteros, GEOFON team
# <javier@gfz-potsdam.de>
#
# ----------------------------------------------------------------------

"""Classes to access an indexed SDS structure to be used by the Dataselect-WS

(c) 2014 Javier Quinteros, GEOFON, GFZ Potsdam

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2, or (at your option) any later
version. For more information, see http://www.gnu.org/

"""
import os
import datetime
from struct import pack, unpack
import seiscomp.mseedlite


class NoDataAvailable(Exception):
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        Exception.__init__(self, message)
        # Now for your custom code...
        #self.Errors = Errors


class IndexedSDS(object):
    def __init__(self, sdsRoot, idxRoot):
        self.sdsRoot = sdsRoot
        self.idxRoot = idxRoot

    def _getMSName(self, reqDate, net, sta, loc, cha):
        loc = loc if loc != '--' else ''
        return '%s/%d/%s/%s/%s.D/%s.%s.%s.%s.D.%d.%s' % \
            (self.sdsRoot, reqDate.year, net, sta, cha, net, sta, loc, cha,
             reqDate.year, reqDate.strftime('%j'))

    def getRawBytes(self, startt, endt, net, sta, loc, cha):
        eoDay = datetime.datetime(startt.year, startt.month, startt.day)\
            + datetime.timedelta(days=1) - datetime.timedelta(milliseconds=1)
        while startt < endt:
            try:
                yield self.getDayRaw(startt, min(endt, eoDay), net, sta,
                                     loc, cha)
            except NoDataAvailable:
                pass
            except:
                raise

            startt = datetime.datetime(startt.year, startt.month, startt.day)\
                + datetime.timedelta(days=1)
            eoDay = datetime.datetime(startt.year, startt.month, startt.day)\
                + datetime.timedelta(days=2)
        raise StopIteration

    def getDayRaw(self, startt, endt, net, sta, loc, cha):
        """Retrieve records from an SDS archive. The start and end dates must
         be in the same day for this test."""

        if ((startt.year != endt.year) or (startt.month != endt.month) or
           (startt.day != endt.day)):
            msg = "Error in getDayRaw: only the time can differ between" + \
                " start and end dates."
            raise Exception(msg)

        # Take into account the case of empty location
        if loc == '--':
            loc = ''

        # For every file that contains information to be retrieved
        try:
            # Check that the data file exists
            dataFile = self._getMSName(startt, net, sta, loc, cha)
            if not os.path.exists(dataFile):
                raise NoDataAvailable('%s does not exist!' % dataFile)

            # Open the index file
            with open(self.getIndex(startt, net, sta, loc, cha), 'rb') \
                    as idxFile:
                buffer = idxFile.read()

                # Read the record length (integer - constant for the whole
                # file)
                reclen = unpack('i', buffer[:4])[0]
                timeDiffSecs = buffer[4:]

                with open(dataFile, 'rb') as msFile:
                    # Read the baseline for time from the first record
                    rec = msFile.read(reclen)
                    msrec = seiscomp.mseedlite.Record(rec)
                    basetime = msrec.begin_time

                    # Float number that we search for in the index
                    # THIS IS ONLY TO FIND THE STARTING POINT
                    searchFor = (startt - basetime).total_seconds()

                    recStart = 0
                    recEnd = int(len(timeDiffSecs) / 4) - 1

                    timeStart = unpack('f',
                                       timeDiffSecs[recStart * 4:
                                                    (recStart + 1) * 4])[0]
                    timeEnd = unpack('f',
                                     timeDiffSecs[recEnd * 4:
                                                  (recEnd + 1) * 4])[0]

                    recHalf = recStart + int((recEnd - recStart) / 2.0)
                    timeHalf = unpack('f',
                                      timeDiffSecs[recHalf * 4:
                                                   (recHalf + 1) * 4])[0]

                    # print searchFor, timeStart, timeHalf, timeEnd

                    if searchFor <= timeStart:
                        recEnd = recStart
                    if searchFor >= timeEnd:
                        recStart = recEnd

                    while (recEnd - recStart) > 1:
                        if searchFor > timeHalf:
                            recStart = recHalf
                        else:
                            recEnd = recHalf
                        recHalf = recStart + int((recEnd - recStart) / 2.0)
                        # Calculate time
                        timeStart = unpack('f',
                                           timeDiffSecs[recStart * 4:
                                                        (recStart + 1) * 4])[0]
                        timeEnd = unpack('f',
                                         timeDiffSecs[recEnd * 4:
                                                      (recEnd + 1) * 4])[0]
                        timeHalf = unpack('f',
                                          timeDiffSecs[recHalf * 4:
                                                       (recHalf + 1) * 4])[0]
                        # print searchFor, timeStart, timeHalf, timeEnd

                    lower = recStart

                    # Float number that we search for in the index
                    # THIS IS ONLY TO FIND THE END POINT
                    searchFor = (endt - basetime).total_seconds()

                    recStart = 0
                    recEnd = int(len(timeDiffSecs) / 4) - 1

                    timeStart = unpack('f',
                                       timeDiffSecs[recStart * 4:
                                                    (recStart + 1) * 4])[0]
                    timeEnd = unpack('f',
                                     timeDiffSecs[recEnd * 4:
                                                  (recEnd + 1) * 4])[0]

                    recHalf = recStart + int((recEnd - recStart) / 2.0)
                    timeHalf = unpack('f',
                                      timeDiffSecs[recHalf * 4:
                                                   (recHalf + 1) * 4])[0]

                    if searchFor <= timeStart:
                        recEnd = recStart
                    if searchFor >= timeEnd:
                        recStart = recEnd

                    while (recEnd - recStart) > 1:
                        if searchFor > timeHalf:
                            recStart = recHalf
                        else:
                            recEnd = recHalf
                        recHalf = recStart + int((recEnd - recStart) / 2.0)
                        # Calculate time
                        timeStart = unpack('f',
                                           timeDiffSecs[recStart * 4:
                                                        (recStart + 1) * 4])[0]
                        timeEnd = unpack('f',
                                         timeDiffSecs[recEnd * 4:
                                                      (recEnd + 1) * 4])[0]
                        timeHalf = unpack('f',
                                          timeDiffSecs[recHalf * 4:
                                                       (recHalf + 1) * 4])[0]
                        # print searchFor, timeStart, timeHalf, timeEnd

                    upper = recEnd
                    # Now I have a pointer to the record I want (recStart)
                    # and another one (recEnd) to the record where I should
                    # stop
                    msFile.seek(lower * reclen)
                    return msFile.read((upper - lower + 1) * reclen)

        except:
            raise

    def _buildPath(self, startD, net, sta, loc, cha):
        relPath = os.path.join(str(startD.year), net, sta, cha)
        filename = '%s.%s.%s.%s.D.%d.%d' % (net, sta, loc, cha, startD.year,
                                            startD.timetuple().tm_yday)
        idxFileName = os.path.join(self.idxRoot, relPath,
                                   '.%s.idx' % filename)
        return idxFileName

    def getIndex(self, startD, net, sta, loc, cha):
        idxFileName = self._buildPath(startD, net, sta, loc, cha)
        if not os.path.exists(idxFileName):
            fd = None
            try:
                msFile = self._getMSName(startD, net, sta, loc, cha)
                fd = open(msFile, 'rb')
            except:
                raise NoDataAvailable('%s does not exist!' % msFile)

            self._indexMS(startD, net, sta, loc, cha, fd)
            if fd:
                fd.close()
        return idxFileName

    def _indexMS(self, reqDate, net, sta, loc, cha, fd):
        idxFileName = self._buildPath(reqDate, net, sta, loc, cha)
        if not os.path.exists(os.path.dirname(idxFileName)):
            os.makedirs(os.path.dirname(idxFileName))
        idxFile = open(idxFileName, 'wb')

        baseTime = None
        # Loop through the records in the file
        for msrec in seiscomp.mseedlite.Input(fd):
            # setup the base time for the whole file
            if baseTime is None:
                baseTime = msrec.begin_time
                reclen = msrec.size
                print "Indexing %s on %d/%d/%d with records of %d bytes" % \
                    ((net, sta, loc, cha), reqDate.year, reqDate.month,
                     reqDate.day, reclen)
                idxFile.write(pack('i', reclen))

            diffSeconds = (msrec.begin_time - baseTime).total_seconds()
            idxFile.write(pack('f', diffSeconds))

        idxFile.close()
