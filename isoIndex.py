#!/usr/bin/env python
#
# FDSN-WS Dataselect prototype
#
# (c) 2014 Javier Quinteros, GEOFON team
# <javier@gfz-potsdam.de>
#
# ----------------------------------------------------------------------

"""Classes to access an indexed ISO structure to be used by the Dataselect-WS

(c) 2014 Javier Quinteros, GEOFON, GFZ Potsdam

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2, or (at your option) any later
version. For more information, see http://www.gnu.org/

"""
import os
import datetime
import zlib
import iso9660
from pycdio import ISO_BLOCKSIZE
from math import ceil, floor
from struct import pack, unpack
import seiscomp.mseedlite


class ISONoDataAvailable(Exception):
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        Exception.__init__(self, message)
        # Now for your custom code...
        #self.Errors = Errors


class FileInISO(object):
    def __init__(self, isoName, pathName):
        self.iso = iso9660.ISO9660.IFS(source=isoName)
        self.pathName = pathName

        # Check if the file exists
        self.stat = self.iso.stat(pathName, translate=True)

        # Internal buffer to simulate a read operation
        size, self.__header = self.iso.seek_read(self.stat['LSN'])
        self.__posCByte = 0
        self.__posUByte = 0
        self.__posSect = 1

        # Check the header
        # First the magic numbers
        magic = '\x37\xe4\x53\x96\xc9\xdb\xd6\x07'
        if not self.__header[:8] == magic:
            raise Exception('No magic numbers found in header!')

        # Check the length of the decompressed file
        self.length = unpack('i', self.__header[8:12])[0]

        # Check the header size
        self.hs = 1 << unpack('B', self.__header[12])[0]

        # Check the block size
        self.bs = 1 << unpack('B', self.__header[13])[0]

        startData = unpack('I', self.__header[16:20])[0]
        # Check that I will have all the pointers in self.__header
        if startData >= len(self.__header):
            size, auxbuf = self.iso.seek_read(self.stat['LSN'] +
                                              self.__posSect)
            self.__header += auxbuf
            self.__posSect += 1

        # Next two bytes (14, 15) are reserved

        # Read the pointers to the blocks
        numBlocks = ceil(self.length / float(self.bs))
        self.blkPtr = list()

        ptr = self.hs
        for block in range(int(numBlocks)):
            self.blkPtr.append(unpack('I', self.__header[ptr:ptr + 4])[0])
            ptr += 4

    def readBlock(self, blkNum):
        b2read = self.blkPtr[blkNum + 1] - self.blkPtr[blkNum]

        cmpBuf = ''
        curBlk = int(floor(self.blkPtr[blkNum] / float(ISO_BLOCKSIZE)))

        while len(cmpBuf) < b2read:
            size, auxBuf = self.iso.seek_read(self.stat['LSN'] + curBlk)
            # Normally just append what has been read
            if len(cmpBuf):
                cmpBuf += auxBuf
            else:
                # but from the first block we should remove teh unwanted bytes
                cmpBuf = auxBuf[self.blkPtr[blkNum] % ISO_BLOCKSIZE:]

            curBlk += 1

        # Decompress exactly the contents of one block of the original file
        return zlib.decompress(cmpBuf[:b2read])


class IndexedISO(object):
    def __init__(self, isoRoot, idxRoot):
        if isinstance(isoRoot, basestring):
            self.isoRoot = [isoRoot]
        elif type(isoRoot) == type(list()):
            self.isoRoot = isoRoot
        self.idxRoot = idxRoot

    def _getISOName(self, reqDate, net, sta):
        for root in self.isoRoot:
            yield '%s/%d/%s/%s.%s.%d.iso' % \
                (root, reqDate.year, net, sta, net, reqDate.year)
        raise StopIteration

    def _getMSNameInISO(self, reqDate, net, sta, loc, cha):
        loc = loc if loc != '--' else ''

        return '/%d/%s/%s/%s.D/%s.%s.%s.%s.D.%d.%s' % \
            (reqDate.year, net, sta, cha, net, sta, loc, cha,
             reqDate.year, reqDate.strftime('%j'))
        raise StopIteration

    def getRawBytes(self, startt, endt, net, sta, loc, cha):
        eoYear = datetime.datetime(startt.year + 1, 1, 1)\
            - datetime.timedelta(milliseconds=1)
        while startt < endt:
            try:
                print self.checkYear(startt, min(endt, eoYear), net, sta,
                                     loc, cha)
            except ISONoDataAvailable:
                pass
            except:
                raise

            startt = datetime.datetime(startt.year + 1, 1, 1)
            eoYear = datetime.datetime(startt.year + 1, 1, 1)\
                - datetime.timedelta(milliseconds=1)
        raise StopIteration

    def checkYear(self, startt, endt, net, sta, loc, cha):
        """Check the presence of data inside an ISO file for the specified
        time range."""

        if (startt.year != endt.year):
            msg = "Error in checkYear: year must be the same in both dates."
            raise Exception(msg)

        # Take into account the case of empty location
        if loc == '--':
            loc = ''

        # For every file that contains information to be retrieved
        try:
            # Check that the data file exists
            for dataFile in self._getISOName(startt, net, sta):
                if not os.path.exists(dataFile):
                    continue

                # Open the index file
                with open(self.getIndex(startt, net, sta, loc, cha), 'rb') \
                        as idxFile:
                    break

            else:
                raise ISONoDataAvailable('Error: No data for %s on %d!' %
                                         ((net, sta), startt.year))
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
            for isoFile in self._getISOName(startD, net, sta):
                try:
                    isofd = iso9660.ISO9660.IFS(source=isoFile)
                    if isofd is not None:
                        fName = self._getMSName(startD, net, sta, loc, cha)
                        statbuf = isofd.stat(fName, translate=True)
                        print statbuf
                    else:
                        continue

                    if fd is not None:
                        break
                except:
                    pass
            else:
                raise ISONoDataAvailable('Requested data not available!')

            self._indexISO(startD, net, sta, fd)
            if fd:
                fd.close()
        return idxFileName

    def _indexISO(self, reqDate, net, sta, fd):
        pass

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
