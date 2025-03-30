#! /usr/bin/env python3

import unittest
import struct


class Music:    
    def __init__(self, loadAddress, initAddress, playAddress, data):
        self.loadAddress = loadAddress
        self.initAddress = initAddress
        self.playAddress = playAddress
        self.data = data
        

def load(fileName: str, context):
    music = None
    
    try:
        with open(fileName, 'rb') as f:
            bytes = f.read()

            headerFormat = '>4sHHHHHHHL32s32s32s'
            headerSize = struct.calcsize(headerFormat)
            unpacked = struct.unpack(headerFormat, bytes[:headerSize])
            (magicId, version, dataOffset, loadAddress, initAddress, playAddress, songs, startSong, speed, name, author, copyright) = unpacked

            if magicId == b'PSID':
      
                data = bytes[dataOffset:]

                # Memory location of data. Zero means the two first bytes of the data is the load address (lo, hi).
                if loadAddress == 0 and len(data) >= 2:
                    loadAddress = data[1] * 256 + data[0]
                    data = data[2:]

                music = Music(loadAddress, initAddress, playAddress, data)

            else:
                context.reportError(f'Not a valid sid file: "{fileName}"')

    except FileNotFoundError:
        context.reportError(f'File not found "{fileName}"')

    return music


################################################################################

#class TestMusic(unittest.TestCase):

#    def testSomething():
#        pass
        
if __name__ == '__main__':
    unittest.main()
