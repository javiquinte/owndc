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
from math import floor
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
        self.__iso = iso9660.ISO9660.IFS(source=isoName)
        self.pathName = pathName

        # Check if the file exists
        self.__stat = self.__iso.stat(pathName, translate=True)

        # Internal buffer to simulate a read operation
        size, self.__header = self.__iso.seek_read(self.__stat['LSN'])

        # Check the header
        # First the magic numbers
        magic = '\x37\xe4\x53\x96\xc9\xdb\xd6\x07'
        if not self.__header[:8] == magic:
            raise Exception('No magic numbers found in header!')

        # Check the length of the decompressed file
        self.__length = unpack('i', self.__header[8:12])[0]

        # Check the header size
        self.__hs = 1 << unpack('B', self.__header[12])[0]

        # Check the block size
        self.__bs = 1 << unpack('B', self.__header[13])[0]

        # Set the position of the decompressed file
        self.__fileOffset = 0
        self.__decblkNum = None

        # Next two bytes (14, 15) are reserved
        # Read the pointer to the first data block
        startData = unpack('I', self.__header[16:20])[0]

        # Check that I will have all the pointers in self.__header
        secPtr = self.__stat['LSN'] + 1
        if startData >= len(self.__header):
            size, auxbuf = self.__iso.seek_read(secPtr)
            self.__header += auxbuf
            secPtr += 1

        # Read the pointers to the blocks
        # Check in which block is the last byte of the file and add 1 to
        # translate from block number (f.i. 7) to number of blocks (8).
        numBlocks = self.__inFileBlock(self.__length - 1) + 1
        self.__blkPtr = list()

        ptr = self.__hs
        # Read one pointer more than the number of blocks (signalize the EOF)
        for block in range(numBlocks + 1):
            self.__blkPtr.append(unpack('I', self.__header[ptr:ptr + 4])[0])
            ptr += 4

    def __inFileBlock(self, offset):
        return int(floor(offset / float(self.__bs)))

    def __inISOBlock(self, offset):
        return int(floor(offset / float(ISO_BLOCKSIZE)))

    def __readBlock(self, blkNum):
        if blkNum >= len(self.__blkPtr):
            raise Exception('Error: Block number beyond the end of the file.')

        b2read = self.__blkPtr[blkNum + 1] - self.__blkPtr[blkNum]

        cmpBuf = ''
        curBlk = self.__inISOBlock(self.__blkPtr[blkNum])

        while len(cmpBuf) < b2read:
            size, auxBuf = self.__iso.seek_read(self.__stat['LSN'] + curBlk)
            # Normally just append what has been read
            if len(cmpBuf):
                cmpBuf += auxBuf
            else:
                # but from the first block we should remove teh unwanted bytes
                cmpBuf = auxBuf[self.__blkPtr[blkNum] % ISO_BLOCKSIZE:]

            curBlk += 1

        # Decompress exactly the contents of one block of the original file
        self.__decBuf = zlib.decompress(cmpBuf[:b2read])
        self.__decblkNum = blkNum

        return self.__decBuf

    def seek(self, offset, whence=0):
        """Seek operation on the file inside the ISO image.
        It works exactly as a normal seek method on a regular file.
        """

        if whence == 0:
            self.__fileOffset = 0
        elif whence == 2:
            self.__fileOffset = self.__length
        else:
            raise IOError('[Errno 22] Invalid argument')

        self.__fileOffset += offset

    def tell(self):
        """Tell operation on the file inside the ISO image.
        It works exactly as a normal teel method on a regular file.
        """
        return self.__fileOffset

    def read(self, size=None):
        """Tell operation on the file inside the ISO image.
        It works exactly as a normal teel method on a regular file.
        """

        # If the size is negative or was not passed as a parameter, read until
        # the end of the file
        if (size is None) or (size < 0):
            size = self.__length - self.__fileOffset

        # If the size goes beyond the end of the file, make it point to EOF
        if (self.__fileOffset + size > self.__length):
            size = self.__length - self.__fileOffset

        result = ''
        blkNum = self.__inFileBlock(self.__fileOffset)
        firstByte = self.__fileOffset % self.__bs

        # Check if the first block is already in the buffer or should be read
        if blkNum != self.__decblkNum:
            result = self.__readBlock(blkNum)[firstByte:]
        else:
            result = self.__decBuf[firstByte:]

        while len(result) < size:
            result += self.__readBlock(blkNum)
            blkNum += 1

        self.__fileOffset += size
        return result[:size]

    def close(self):
        """Close the open file inside the ISO image AND the ISO file.
        It works exactly as a normal close method on a regular file.
        """
        self.__iso.close()


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
        eoDay = datetime.datetime(startt.year, startt.month, startt.day)\
            + datetime.timedelta(days=1) - datetime.timedelta(milliseconds=1)
        while startt < endt:
            try:
                yield self.getDayRaw(startt, min(endt, eoDay), net, sta,
                                     loc, cha)
            except ISONoDataAvailable:
                pass
            except:
                raise

            startt = datetime.datetime(startt.year, startt.month, startt.day)\
                + datetime.timedelta(days=1)
            eoDay = datetime.datetime(startt.year, startt.month, startt.day) +\
                datetime.timedelta(days=1) - datetime.timedelta(milliseconds=1)
        raise StopIteration

    def getDayRaw(self, startt, endt, net, sta, loc, cha):
        """Retrieve records from a file in an ISO image. The start and end
        dates must be in the same day for this test."""

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
            for isoFile in self._getISOName(startt, net, sta):
                if not os.path.exists(isoFile):
                    continue

                dataFile = self.__getMSName(startt, net, sta, loc, cha)
                try:
                    msFile = FileInISO(isoFile, dataFile)
                except ISONoDataAvailable:
                    continue
                except:
                    raise

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

            else:
                raise NoDataAvailable('Error: No data for %s on %d/%d/%d!' %
                                      ((net, sta, loc, cha), startt.year,
                                       startt.month, startt.day))
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
