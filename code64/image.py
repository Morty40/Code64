#! /usr/bin/env python3

import unittest
import struct


class Image:    
    def __init__(self, width: int, height: int, pixels: list):
        self.width = width
        self.height = height

        self.data = []

        # TODO: convert pixels from 1/4/8bits to 8-bit

        #blockSize = (8, 8)
        #blockAlign = 8

        blockSize = (24, 21)
        blockAlign = 64

        blockWidth, blockHeight = blockSize

        for y in range(0, height, blockHeight):
            for x in range(0, width, blockWidth):
                
                for yy in range(0, blockHeight):
                    for xx in range(0, blockWidth, 8):


                        index = (height - 1 - (y + yy)) * width + (x+xx)
                        byte = self.pixelsToByte(pixels[index:index+8])

                        self.data.append(byte)

                # align
                while len(self.data) % blockAlign != 0:
                    self.data.append(0)

        # TODO: convert pixels from 8-bit to 1bit (single color) or 2 bits (multicolor)


    def pixelsToByte(self, pixels):
        bits = [128, 64, 32, 16, 8, 4, 2, 1]
        byte = 0
        x = 0
        for p in pixels:
            if p != 0:
                byte |= bits[x]
            x += 1

        return byte


def load(fileName: str, context):
    image = None

    try:
        with open(fileName, 'rb') as f:
            bytes = f.read()

            bmpHeaderFormat = '<2sIHHI'
            bmpHeaderSize = struct.calcsize(bmpHeaderFormat)
            bmpHeaderUnpacked = struct.unpack(bmpHeaderFormat, bytes[:bmpHeaderSize])
            (magicId, fileSize, reserved1, reserved2, dataOffset) = bmpHeaderUnpacked

            if magicId == b'BM':
                dibHeaderFormat = '<IiiHH'
                dibHeaderSize = struct.calcsize(dibHeaderFormat)
                dibHeaderUnpacked = struct.unpack(dibHeaderFormat, bytes[bmpHeaderSize:bmpHeaderSize+dibHeaderSize])
                (size, width, height, planes, bitsPerPixel) = dibHeaderUnpacked
        
                if bitsPerPixel == 8:
                    if (width % 8) == 0:
                        image = Image(width, height, bytes[dataOffset:])
                    else:
                        context.reportError(f'Image width {width} not a multiple of 8: "{fileName}"')
                else:
                    context.reportError(f'Image bits per pixel {bitsPerPixel} not supported: "{fileName}"')
            else:
                context.reportError(f'Not a valid bmp file: "{fileName}"')

    except FileNotFoundError:
        context.reportError(f'File not found "{fileName}"')

    return image
    
################################################################################

#class TestImage(unittest.TestCase):

#    def testSomething():
#        pass
        
if __name__ == '__main__':
    unittest.main()
