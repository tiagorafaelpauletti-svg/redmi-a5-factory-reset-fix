#!/usr/bin/env python3
"""Offline, narrowly scoped rescue-image inspection and patch preparation.

This program never connects to USB and never flashes a phone.
"""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import struct
import sys

IMAGE_SIZE = 128 * 1024 * 1024
TARGET = 'recovery/last_extension_parameters'
BEFORE = b'disable_factoryreset=1\n'
AFTER = b'disable_factoryreset=0\n'


class UnsupportedImage(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise UnsupportedImage(message)


class ExtImage:
    """Read only the small extent-backed files needed by the tested profile."""

    def __init__(self, data):
        self.data = data
        require(len(data) >= 2048, 'Truncated superblock')
        require(self.u16(1080) == 0xEF53, 'Not an ext filesystem')
        log_block = self.u32(1048)
        require(log_block <= 2, 'Unsupported block size')
        self.block = 1024 << log_block
        self.ipg = self.u32(1064)
        self.inode_size = self.u16(1112)
        self.inode_count = self.u32(1024)
        require(self.ipg > 0 and self.inode_count > 0, 'Invalid inode counts')
        require(self.inode_size in (128, 256, 512), 'Unsupported inode size')
        # FILETYPE and EXTENTS only; no replay-needed journal, 64-bit,
        # inline data, encrypted files, bigalloc or metadata checksums.
        require(self.u32(1120) & ~0x42 == 0, 'Unsupported incompatible features / journal replay required')
        require(self.u32(1124) & ~0x7B == 0, 'Unsupported read-only features / checksums')
        require(self.u16(1082) & 1, 'Filesystem is not marked clean')
        self.descriptors = (2 if self.block == 1024 else 1) * self.block

    def bounds(self, offset, size):
        require(offset >= 0 and size >= 0 and offset + size <= len(self.data), 'Out-of-image reference')

    def u16(self, offset):
        self.bounds(offset, 2)
        return struct.unpack_from('<H', self.data, offset)[0]

    def u32(self, offset):
        self.bounds(offset, 4)
        return struct.unpack_from('<I', self.data, offset)[0]

    def inode(self, number):
        require(1 <= number <= self.inode_count, 'Invalid inode number')
        group, index = divmod(number - 1, self.ipg)
        table = self.u32(self.descriptors + group * 32 + 8)
        start = table * self.block + index * self.inode_size
        self.bounds(start, self.inode_size)
        return start

    def layout(self, number):
        start = self.inode(number)
        size = self.u32(start + 4) | (self.u32(start + 108) << 32)
        require(size <= 1024 * 1024, 'Only small configuration files and directories supported')
        flags = self.u32(start + 32)
        require(flags & 0x80000 and not flags & (0x800 | 0x10000000), 'Unsupported inode flags')
        header = start + 40
        require(self.u16(header) == 0xF30A, 'Invalid extent magic')
        count, maximum, depth = self.u16(header + 2), self.u16(header + 4), self.u16(header + 6)
        require(depth == 0 and 0 < count <= maximum <= 4, 'Unsupported extent tree')
        chunks = []
        previous_end = 0
        for n in range(count):
            entry = header + 12 + n * 12
            logical = self.u32(entry) * self.block
            blocks = self.u16(entry + 4)
            require(0 < blocks <= 0x8000, 'Uninitialized extent unsupported')
            physical = ((self.u16(entry + 6) << 32) | self.u32(entry + 8)) * self.block
            length = blocks * self.block
            require(logical == previous_end, 'Sparse or overlapping extents unsupported')
            self.bounds(physical, length)
            chunks.append((logical, physical, length))
            previous_end = logical + length
        require(previous_end >= size, 'Extents do not cover file')
        return start, size, chunks

    def read(self, number):
        _, size, chunks = self.layout(number)
        result = bytearray(size)
        for logical, physical, length in chunks:
            count = min(length, size - logical)
            if count > 0:
                result[logical:logical + count] = self.data[physical:physical + count]
        return bytes(result)

    def child(self, directory, wanted):
        require(stat.S_ISDIR(self.u16(self.inode(directory))), 'Path parent is not a directory')
        data = self.read(directory)
        offset = 0
        matches = []
        while offset < len(data):
            require(offset + 8 <= len(data), 'Truncated directory')
            number, length, name_len, _ = struct.unpack_from('<IHBB', data, offset)
            require(length >= 8 and length % 4 == 0, 'Invalid directory record length')
            require(offset + length <= len(data) and name_len <= length - 8, 'Invalid directory record bounds')
            if number and data[offset + 8:offset + 8 + name_len] == wanted.encode('ascii'):
                matches.append(number)
            offset += length
        require(len(matches) == 1, 'Missing or ambiguous path component: ' + wanted)
        return matches[0]

    def configuration(self):
        number = self.child(self.child(2, 'recovery'), 'last_extension_parameters')
        start, size, chunks = self.layout(number)
        require(stat.S_ISREG(self.u16(start)), 'Configuration is not a regular file')
        require(size == len(BEFORE), 'Unexpected configuration size; inspect manually')
        content = self.read(number)
        require(content in (BEFORE, AFTER), 'Unexpected configuration content; inspect manually')
        logical_offset = len(b'disable_factoryreset=')
        locations = [physical + logical_offset - logical for logical, physical, length in chunks
                     if logical <= logical_offset < logical + length]
        require(len(locations) == 1, 'Ambiguous configuration byte')
        return number, locations[0], content


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def prepare(data, reference, *, expected_size=IMAGE_SIZE):
    require(len(data) == expected_size, 'Unexpected image size for tested profile')
    image = ExtImage(data)
    number, offset, before = image.configuration()
    require(before == BEFORE, 'Factory reset already enabled; no patch needed')
    require(reference == before, 'Independent extracted reference does not match image')
    patched = data[:offset] + b'0' + data[offset + 1:]
    require(len(patched) == len(data), 'Image size changed')
    require(data[offset] == ord('1') and patched[offset] == ord('0'), 'Unexpected byte change')
    require(ExtImage(patched).configuration()[2] == AFTER, 'Patched file verification failed')
    return patched, {
        'file': TARGET, 'inode': number, 'offset': offset, 'different_bytes': 1,
        'image_bytes': len(data), 'before': BEFORE.decode().rstrip(),
        'after': AFTER.decode().rstrip(), 'original_sha256': sha256(data),
        'patched_sha256': sha256(patched),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect', help='Inspect local image; no writes')
    inspect.add_argument('image', type=Path)
    patch = commands.add_parser('patch', help='Create an offline patched COPY; never flashes')
    patch.add_argument('image', type=Path)
    patch.add_argument('--reference-file', required=True, type=Path,
                       help='Configuration independently extracted using e.g. 7-Zip')
    patch.add_argument('--output', required=True, type=Path)
    verify = commands.add_parser('verify', help='Compare expected image and full device readback')
    verify.add_argument('expected', type=Path)
    verify.add_argument('readback', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'inspect':
            data = args.image.read_bytes()
            require(len(data) == IMAGE_SIZE, 'Expected tested 128 MiB rescue image')
            number, offset, content = ExtImage(data).configuration()
            print(json.dumps({'file': TARGET, 'inode': number, 'offset': offset,
                              'configuration': content.decode().rstrip(), 'sha256': sha256(data)}, indent=2))
        elif args.command == 'patch':
            require(args.image.resolve() != args.output.resolve(), 'Never overwrite the original')
            require(not args.output.exists(), 'Output already exists; choose a new filename')
            patched, report = prepare(args.image.read_bytes(), args.reference_file.read_bytes())
            # Exclusive creation also protects against an output created after the check.
            with args.output.open('xb') as stream:
                stream.write(patched)
            print(json.dumps(report, indent=2))
        else:
            expected, actual = args.expected.read_bytes(), args.readback.read_bytes()
            require(len(expected) == len(actual) == IMAGE_SIZE, 'Readback size mismatch')
            require(sha256(expected) == sha256(actual), 'READBACK MISMATCH: do not reboot; recover original')
            require(ExtImage(actual).configuration()[2] == AFTER, 'Reset-enable configuration missing')
            print(json.dumps({'verified': True, 'sha256': sha256(actual), 'image_bytes': len(actual)}, indent=2))
        return 0
    except (OSError, ValueError, struct.error) as error:
        print('Refused: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
