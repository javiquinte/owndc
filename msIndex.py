import os
import datetime
from struct import pack, unpack
import seiscomp.sds
import seiscomp.mseedlite


class Indexer(object):
    def __init__(self, sdsRoot, idxRoot):
        self.mysds = seiscomp.sds.SDS('', sdsRoot, '')
        self.idxRoot = idxRoot

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
            self._indexMS(startD, net, sta, loc, cha)
        return idxFileName

    def _indexMS(self, reqDate, net, sta, loc, cha):
        idxFileName = self._buildPath(reqDate, net, sta, loc, cha)
        if not os.path.exists(os.path.dirname(idxFileName)):
            os.makedirs(os.path.dirname(idxFileName))
        idxFile = open(idxFileName, 'wb')

        # Take one hour buffer on both sides
        tfrom = datetime.datetime(reqDate.year, reqDate.month, reqDate.day)
        tto = datetime.datetime(reqDate.year, reqDate.month, reqDate.day) +\
            datetime.timedelta(days=1)

        # Traverse through all records
        baseTime = None
        # FIXME I should not use iterdata because I need to index A FILE!
        # I need direct access to it
        for recOrder, rec in enumerate(self.mysds.iterdata(tfrom, tto, net,
                                                           sta, cha, loc)):
            msrec = seiscomp.mseedlite.Record(rec)

            # setup the base time for the whole file
            if baseTime is None:
                baseTime = msrec.begin_time
                reclen = msrec.size
                # print "Record length: %d" % reclen
                idxFile.write(pack('i', reclen))

            diffSeconds = (msrec.begin_time - baseTime).total_seconds()
            idxFile.write(pack('f', diffSeconds))

        idxFile.close()


class IndexedSDS(object):
    def __init__(self, sdsRoot, idxRoot):
        self.sdsRoot = sdsRoot
        self.idxRoot = idxRoot
        self.idx = Indexer(sdsRoot, idxRoot)

    def _getMSName(self, reqDate, net, sta, loc, cha):
        loc = loc if loc != '--' else ''
        return '%s/%d/%s/%s/%s.D/%s.%s.%s.%s.D.%d.%s' % \
            (self.sdsRoot, reqDate.year, net, sta, cha, net, sta, loc, cha,
             reqDate.year, reqDate.strftime('%j'))

    def getRawBytes(self, startt, endt, net, sta, loc, cha):
        eoDay = datetime.datetime(startt.year, startt.month, startt.day)\
            + datetime.timedelta(days=1) - datetime.timedelta(milliseconds=1)
        while startt < endt:
            yield self.getDayRaw(startt, min(endt, eoDay), net, sta, loc, cha)
            startt = datetime.datetime(startt.year, startt.month, startt.day)\
                + datetime.timedelta(days=1)
            eoDay = datetime.datetime(startt.year, startt.month, startt.day)\
                + datetime.timedelta(days=2)
        raise StopIteration

    def getDayRaw(self, startt, endt, net, sta, loc, cha):
        """Retrieve records from an SDS archive. The start and end dates must
         be in the same day for this test. This can be later improved."""

        if ((startt.year != endt.year) or (startt.month != endt.month) or
           (startt.day != endt.day)):
            print "Error: Start and end dates should be in the same day."
            return None

        # Take into account the case of empty location
        if loc == '--':
            loc = ''

        # For every file that contains information to be retrieved
        try:
            # Open the index file
            with open(self.idx.getIndex(startt, net, sta, loc, cha), 'rb') \
                    as idxFile:
                buffer = idxFile.read()

                # Read the record length (integer - constant for the whole
                # file)
                reclen = unpack('i', buffer[:4])[0]
                timeDiffSecs = buffer[4:]

                with open(self._getMSName(startt, net, sta, loc, cha), 'rb') \
                        as msFile:
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
            return None
