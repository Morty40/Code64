#! /usr/bin/env python3

import os
import struct
import tempfile
import unittest
from dataclasses import dataclass, field

from .context import Context


_HEADER = '>4sHHHHHHHL32s32s32s' # all versions: $76 bytes
_HEADER_V2 = '>HBBBB'            # version 2 and later: flags, startPage, pageLength, secondSIDAddress, thirdSIDAddress

_CLOCKS = ['unknown', 'PAL', 'NTSC', 'PAL and NTSC']
_SID_MODELS = ['unknown', 'MOS6581', 'MOS8580', 'MOS6581 and MOS8580']


@dataclass
class Music:
    """The music data from a SID file, the addresses to load, init and play it, and the other header fields.

    Supports PSID versions 1 to 4, and RSID versions 2 to 4, as described in
    https://hvsc.c64.org/download/C64Music/DOCUMENTS/SID_file_format.txt
    """
    loadAddress: int
    initAddress: int # the load address if 0 in the file, except for a BASIC tune
    playAddress: int # 0 if the init routine installs its own interrupt handler
    data: bytes
    magicId: str = 'PSID' # or 'RSID', for tunes that need a real C64 environment
    version: int = 2
    songs: int = 1
    startSong: int = 1 # 1 is the first song
    speed: int = 0 # see usesCiaTimer()
    name: str = ''
    author: str = ''
    released: str = ''
    flags: int = 0 # version 2 and later, see the properties below
    startPage: int = 0 # free memory for relocation, in pages: 0 is clean, $ff is none
    pageLength: int = 0
    sidAddresses: list = field(default_factory=lambda: [0xd400]) # with a second and third SID in version 3 and 4

    @property
    def isBasic(self) -> bool:
        """RSID only: the music is a BASIC program, to be started with RUN."""
        return self.magicId == 'RSID' and bool(self.flags & 0b10)

    @property
    def isPlaySidSpecific(self) -> bool:
        """PSID only: the music uses PlaySID samples, so needs a PlaySID compatible player."""
        return self.magicId == 'PSID' and bool(self.flags & 0b10)

    @property
    def clock(self) -> str:
        """The video standard: 'unknown', 'PAL', 'NTSC' or 'PAL and NTSC'."""
        return _CLOCKS[self.flags >> 2 & 0b11]

    @property
    def sidModels(self) -> list:
        """The model of each SID: 'unknown', 'MOS6581', 'MOS8580' or 'MOS6581 and MOS8580'."""
        return [_SID_MODELS[self.flags >> shift & 0b11] for shift in [4, 6, 8][:len(self.sidAddresses)]]

    def usesCiaTimer(self, song: int) -> bool:
        """True if the song, from 1, is played by a CIA timer, and False for the vertical blank interrupt."""
        return bool(self.speed >> min(song - 1, 31) & 1) # songs 32 and later share bit 31


def parse(fileData: bytes) -> Music:
    """Parse the contents of a SID file. Raises ValueError if it is not valid, or can't be assembled."""
    def _string(value: bytes) -> str:
        """A Latin-1 string field, padded with zeros, or filling all 32 bytes."""
        return value.split(b'\0')[0].decode('latin-1')

    def _sidAddress(value: int):
        """The address of an extra SID from its header byte, $xy for $dxy0, or None if not a valid address."""
        if value % 2 == 0 and (0x42 <= value <= 0x7e or 0xe0 <= value <= 0xfe):
            return 0xd000 | value << 4
        return None

    if len(fileData) < struct.calcsize(_HEADER):
        raise ValueError('the header is too short')
    (magicId, version, dataOffset, loadAddress, initAddress, playAddress,
     songs, startSong, speed, name, author, released) = struct.unpack_from(_HEADER, fileData)

    if magicId not in [b'PSID', b'RSID']:
        raise ValueError('not PSID or RSID')
    magicId = magicId.decode('ascii')
    if not (1 if magicId == 'PSID' else 2) <= version <= 4:
        raise ValueError(f'unsupported {magicId} version {version}')

    headerSize = struct.calcsize(_HEADER) + (struct.calcsize(_HEADER_V2) if version >= 2 else 0)
    if not headerSize <= dataOffset <= len(fileData):
        raise ValueError(f'the data offset ${dataOffset:x} is not after the header, or is past the end of the file')

    flags, startPage, pageLength, sidAddresses = 0, 0, 0, [0xd400]
    if version >= 2:
        flags, startPage, pageLength, secondSid, thirdSid = struct.unpack_from(_HEADER_V2, fileData, struct.calcsize(_HEADER))
        extraSids = [secondSid] if version == 3 else [secondSid, thirdSid] if version == 4 else []
        sidAddresses += [address for address in map(_sidAddress, extraSids) if address is not None]

    if flags & 0b01:
        raise ValueError('Compute!\'s Sidplayer MUS data needs a separate player, and is not supported')
    if magicId == 'RSID':
        if loadAddress != 0:
            raise ValueError('the RSID load address must be 0, with the load address in the data')
        if playAddress != 0:
            raise ValueError('the RSID play address must be 0')
        if speed != 0:
            raise ValueError('the RSID speed must be 0')

    # a load address of 0 means the first two bytes of the data are the load address (lo, hi)
    data = fileData[dataOffset:]
    if loadAddress == 0:
        loadAddress = int.from_bytes(data[:2], 'little')
        data = data[2:]
    if not data:
        raise ValueError('no music data')
    if loadAddress + len(data) > 0x10000:
        raise ValueError(f'the music data from ${loadAddress:04x} goes past $ffff')

    music = Music(loadAddress, initAddress, playAddress, data, magicId, version, songs, startSong, speed,
                  _string(name), _string(author), _string(released), flags, startPage, pageLength, sidAddresses)
    if music.initAddress == 0 and not music.isBasic:
        music.initAddress = loadAddress
    return music


def load(fileName: str, context):
    """Load a SID file, PSID or RSID, without its header. The path is relative to the folder of the main source file.

    Returns the Music, or None after reporting an error.
    """
    try:
        with open(os.path.join(context.path, fileName), 'rb') as f:
            fileData = f.read()
    except FileNotFoundError:
        context.reportError(f'File not found: "{fileName}"')
        return None

    try:
        return parse(fileData)
    except ValueError as exception:
        context.reportError(f'Not a valid sid file: "{fileName}": {exception}')
        return None


################################################################################

class TestMusic(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = directory.name

    def _sidFile(self, magicId=b'PSID', version=2, dataOffset=None, loadAddress=0x1000, initAddress=0x1000, playAddress=0x1003,
                 songs=1, startSong=1, speed=0, name=b'', author=b'', released=b'',
                 flags=0, startPage=0, pageLength=0, secondSid=0, thirdSid=0, data=b'\x4c\x00\x10\x60') -> str:
        """Write a SID file, with the header of the version, and return its name."""
        if dataOffset is None:
            dataOffset = 0x76 if version == 1 else 0x7c
        header = struct.pack('>4sHHHHHHHL32s32s32s', magicId, version, dataOffset, loadAddress, initAddress, playAddress,
                             songs, startSong, speed, name, author, released)
        if version >= 2:
            header += struct.pack('>HBBBB', flags, startPage, pageLength, secondSid, thirdSid)
        fileName = os.path.join(self.directory, f'{len(os.listdir(self.directory))}.sid')
        with open(fileName, 'wb') as f:
            f.write(header[:dataOffset] + data)
        return fileName

    def _load(self, fileName: str):
        """Load the file, and return the Music, or None, and the errors."""
        context = Context({})
        return load(fileName, context), context.errors

    def testPsidVersion1(self):
        """Version 1 has the shorter header, and no flags."""
        music, errors = self._load(self._sidFile(version=1, songs=3, startSong=2, name=b'Song', author=b'Me', released=b'2021 Me'))
        self.assertEqual(errors, [])
        self.assertEqual((music.magicId, music.version), ('PSID', 1))
        self.assertEqual((music.loadAddress, music.initAddress, music.playAddress), (0x1000, 0x1000, 0x1003))
        self.assertEqual(music.data, b'\x4c\x00\x10\x60')
        self.assertEqual((music.songs, music.startSong), (3, 2))
        self.assertEqual((music.name, music.author, music.released), ('Song', 'Me', '2021 Me'))
        self.assertEqual((music.flags, music.clock, music.sidModels, music.sidAddresses), (0, 'unknown', ['unknown'], [0xd400]))

    def testLoadAddressInData(self):
        """A load address of 0 means the first two bytes of the data are the load address."""
        music, errors = self._load(self._sidFile(loadAddress=0, data=b'\x00\x20\x60'))
        self.assertEqual(errors, [])
        self.assertEqual((music.loadAddress, music.data), (0x2000, b'\x60'))

    def testInitAddressDefault(self):
        """An init address of 0 means the load address."""
        music, errors = self._load(self._sidFile(loadAddress=0x1800, initAddress=0))
        self.assertEqual(music.initAddress, 0x1800)

    def testPsidVersion2(self):
        """Version 2 adds the flags and the relocation range. Strings are Latin-1, and can fill all 32 bytes."""
        flags = 0b01 << 2 | 0b10 << 4 # PAL, MOS8580
        music, errors = self._load(self._sidFile(flags=flags, startPage=0x20, pageLength=0x10, name=b'J\xe4ger' + b'x'*27, author=b'A'*32))
        self.assertEqual(errors, [])
        self.assertEqual((music.clock, music.sidModels, music.isBasic, music.isPlaySidSpecific), ('PAL', ['MOS8580'], False, False))
        self.assertEqual((music.startPage, music.pageLength), (0x20, 0x10))
        self.assertEqual((music.name, music.author), ('Jäger' + 'x'*27, 'A'*32))
        music, errors = self._load(self._sidFile(flags=0b11 << 2 | 0b11 << 4 | 0b10)) # PAL and NTSC, both SID models, PlaySID specific
        self.assertEqual((music.clock, music.sidModels, music.isPlaySidSpecific), ('PAL and NTSC', ['MOS6581 and MOS8580'], True))

    def testExtraSids(self):
        """Version 3 adds a second SID, and version 4 a third, each with its own model and address."""
        flags = 0b01 << 4 | 0b10 << 6 | 0b01 << 8 # MOS6581, MOS8580, MOS6581
        music, errors = self._load(self._sidFile(version=3, flags=flags, secondSid=0x42))
        self.assertEqual(errors, [])
        self.assertEqual((music.sidAddresses, music.sidModels), ([0xd400, 0xd420], ['MOS6581', 'MOS8580']))
        music, errors = self._load(self._sidFile(version=4, flags=flags, secondSid=0x42, thirdSid=0xe0))
        self.assertEqual((music.sidAddresses, music.sidModels), ([0xd400, 0xd420, 0xde00], ['MOS6581', 'MOS8580', 'MOS6581']))
        music, errors = self._load(self._sidFile(version=2, secondSid=0x42, thirdSid=0xe0)) # reserved before version 3 and 4
        self.assertEqual(music.sidAddresses, [0xd400])
        for address in [0x43, 0x40, 0x80, 0xd4, 0xff]: # odd, or outside $42-$7f and $e0-$fe
            with self.subTest(address=address):
                music, errors = self._load(self._sidFile(version=4, secondSid=address, thirdSid=address))
                self.assertEqual(music.sidAddresses, [0xd400])

    def testRsid(self):
        """RSID has versions 2 to 4, with the load address in the data, and no play address."""
        for version in [2, 3, 4]:
            with self.subTest(version=version):
                music, errors = self._load(self._sidFile(magicId=b'RSID', version=version, loadAddress=0, initAddress=0x1000, playAddress=0,
                                                         data=b'\x00\x10\x60'))
                self.assertEqual(errors, [])
                self.assertEqual((music.magicId, music.version), ('RSID', version))
                self.assertEqual((music.loadAddress, music.initAddress, music.playAddress, music.data), (0x1000, 0x1000, 0, b'\x60'))
        music, errors = self._load(self._sidFile(magicId=b'RSID', loadAddress=0, initAddress=0, playAddress=0, flags=0b10,
                                                 data=b'\x01\x08\x00')) # a BASIC program, started with RUN
        self.assertEqual(errors, [])
        self.assertEqual((music.isBasic, music.isPlaySidSpecific, music.initAddress), (True, False, 0))

    def testSpeed(self):
        """Bit n of the speed is set if song n+1 uses a CIA timer, with bit 31 for song 32 and later."""
        music, errors = self._load(self._sidFile(songs=40, speed=0b101 | 1 << 31))
        self.assertEqual([song for song in range(1, 41) if music.usesCiaTimer(song)], [1, 3] + list(range(32, 41)))

    def testInvalid(self):
        """Invalid files report an error, and return None."""
        for name, fileName, error in [
            ('not found',          os.path.join(self.directory, 'missing.sid'),                             'File not found'),
            ('magic id',           self._sidFile(magicId=b'MSID'),                                          'Not a valid sid file'),
            ('short header',       self._sidFile(dataOffset=0x20, data=b''),                                'Not a valid sid file'),
            ('PSID version',       self._sidFile(version=5),                                                'unsupported PSID version 5'),
            ('RSID version 1',     self._sidFile(magicId=b'RSID', version=1, loadAddress=0, playAddress=0), 'unsupported RSID version 1'),
            ('data offset',        self._sidFile(version=2, dataOffset=0x76),                               'data offset'),
            ('no data',            self._sidFile(data=b''),                                                 'no music data'),
            ('no data after load', self._sidFile(loadAddress=0, data=b'\x00\x10'),                          'no music data'),
            ('past $ffff',         self._sidFile(loadAddress=0xfffe, data=b'\x60\x60\x60'),                 'past $ffff'),
            ('MUS data',           self._sidFile(flags=0b01),                                               'Sidplayer MUS'),
            ('RSID load',          self._sidFile(magicId=b'RSID', loadAddress=0x1000, playAddress=0),       'RSID load address'),
            ('RSID play',          self._sidFile(magicId=b'RSID', loadAddress=0, data=b'\x00\x10\x60'),     'RSID play address'),
            ('RSID speed',         self._sidFile(magicId=b'RSID', loadAddress=0, playAddress=0, speed=1,
                                                 data=b'\x00\x10\x60'),                                     'RSID speed')]:
            with self.subTest(name=name):
                music, errors = self._load(fileName)
                self.assertIsNone(music)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(error, errors[0])


if __name__ == '__main__':
    unittest.main()
