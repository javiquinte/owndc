import os
import datetime
import struct
import seiscomp.sds
import seiscomp.mseedlite


class Indexer(object):
    def __init__(self, idxRoot, mysds):
        self.idxRoot = idxRoot
        self.mysds = mysds

    def _buildPath(self, startD, net, sta, loc, cha):
        relPath = os.path.join(startD.year, net, sta, cha)
        filename = '%s.%s.%s.%s.D.%d.%d' % (net, sta, loc, cha, startD.year,
                                            startD.timetuple().tm_yday)
        idxFileName = os.path.join(self.idxRoot, relPath,
                                   '.%s.idx' % filename)
        return idxFileName

    def getIndex(self, startD, net, sta, loc, cha):
        idxFileName = self._buildPath(startD, net, sta, loc, cha)
        if not os.exist(idxFileName):
            self._indexMS(startD, net, sta, loc, cha)
        return idxFileName

    def _indexMS(self, reqDate, net, sta, loc, cha):
        idxFileName = self._buildPath(reqDate, net, sta, loc, cha)
        idxFile = open(idxFileName, 'wb')

        # Take one hour buffer on both sides
        tfrom = datetime.datetime(reqDate.year, reqDate.month, reqDate.day) -\
            datetime.timedelta(hours=1)
        tto = datetime.datetime(reqDate.year, reqDate.month, reqDate.day) +\
            datetime.timedelta(hours=25)
        print idxFileName

        # Traverse through all records
        baseTime = None
        for recOrder, rec in enumerate(self.mysds.iterdata(tfrom, tto, net,
                                                           sta, loc, cha)):
            msrec = seiscomp.mseedlite.Record(rec)

            # setup the base time for the whole file
            if baseTime is None:
                baseTime = msrec.begin_time
                reclen = msrec.size
                # print "Record length: %d" % reclen
                idxFile.write(struct.pack('i', reclen))

            diffSeconds = (msrec.begin_time - baseTime).total_seconds()
            idxFile.write(struct.pack('f', diffSeconds))

        idxFile.close()
