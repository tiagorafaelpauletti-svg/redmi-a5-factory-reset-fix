import contextlib
import io
from pathlib import Path
import struct
import tempfile
import unittest

import rescue_config as rc


def fixture(config_block=30):
    block = 4096
    data = bytearray(64 * block)
    def put16(offset, value):
        struct.pack_into('<H', data, offset, value)
    def put32(offset, value):
        struct.pack_into('<I', data, offset, value)
    put32(1024, 64)
    put32(1028, 64)
    put32(1048, 2)
    put32(1064, 64)
    put16(1080, 0xEF53)
    put16(1082, 1)
    put16(1112, 512)
    put32(1120, 0x42)
    put32(1124, 0x7B)
    put32(block + 8, 2)

    def inode(number, mode, physical, size):
        start = 2 * block + (number - 1) * 512
        put16(start, mode)
        put32(start + 4, size)
        put32(start + 32, 0x80000)
        struct.pack_into('<HHHHI', data, start + 40, 0xF30A, 1, 4, 0, 0)
        struct.pack_into('<IHHI', data, start + 52, 0, 1, 0, physical)

    def directory(physical, entries):
        offset = physical * block
        end = offset + block
        for n, (number, name, kind) in enumerate(entries):
            encoded = name.encode()
            length = (8 + len(encoded) + 3) & ~3
            if n == len(entries) - 1:
                length = end - offset
            struct.pack_into('<IHBB', data, offset, number, length, len(encoded), kind)
            data[offset + 8:offset + 8 + len(encoded)] = encoded
            offset += length

    inode(2, 0o40755, 20, block)
    inode(12, 0o40700, 21, block)
    inode(14, 0o100600, config_block, len(rc.BEFORE))
    directory(20, [(2, '.', 2), (2, '..', 2), (12, 'recovery', 2)])
    directory(21, [(12, '.', 2), (2, '..', 2), (14, 'last_extension_parameters', 1)])
    data[config_block * block:config_block * block + len(rc.BEFORE)] = rc.BEFORE
    # A matching string elsewhere must never be patched by global search.
    data[40 * block:40 * block + len(rc.BEFORE)] = rc.BEFORE
    return data


class ImageTests(unittest.TestCase):
    def test_directory_resolution_and_relocated_extent(self):
        for physical in (30, 31):
            data = bytes(fixture(physical))
            number, offset, value = rc.ExtImage(data).configuration()
            self.assertEqual((number, value), (14, rc.BEFORE))
            self.assertEqual(offset, physical * 4096 + len(b'disable_factoryreset='))

    def test_exactly_one_byte_changes_and_decoy_survives(self):
        original = bytes(fixture())
        patched, report = rc.prepare(original, rc.BEFORE, expected_size=len(original))
        changed = [n for n, pair in enumerate(zip(original, patched)) if pair[0] != pair[1]]
        self.assertEqual(changed, [report['offset']])
        self.assertEqual(len(original), len(patched))
        self.assertEqual(patched[40 * 4096:40 * 4096 + len(rc.BEFORE)], rc.BEFORE)

    def test_reference_must_match(self):
        data = bytes(fixture())
        with self.assertRaises(rc.UnsupportedImage):
            rc.prepare(data, b'wrong', expected_size=len(data))

    def test_already_enabled_refuses_a_second_patch(self):
        data = bytes(fixture())
        patched, _ = rc.prepare(data, rc.BEFORE, expected_size=len(data))
        with self.assertRaises(rc.UnsupportedImage):
            rc.prepare(patched, rc.AFTER, expected_size=len(data))

    def test_unsupported_features_and_dirty_filesystem(self):
        for offset, value, format_ in ((1120, 0x46, '<I'), (1120, 0xC2, '<I'),
                                       (1124, 0x47B, '<I'), (1082, 0, '<H')):
            data = fixture()
            struct.pack_into(format_, data, offset, value)
            with self.assertRaises(rc.UnsupportedImage):
                rc.ExtImage(bytes(data))

    def test_malformed_directory_fails_closed(self):
        data = fixture()
        struct.pack_into('<H', data, 20 * 4096 + 4, 0)
        with self.assertRaises(rc.UnsupportedImage):
            rc.ExtImage(bytes(data)).configuration()

    def test_nonregular_target_rejected(self):
        data = fixture()
        struct.pack_into('<H', data, 2 * 4096 + 13 * 512, 0o120777)
        with self.assertRaises(rc.UnsupportedImage):
            rc.ExtImage(bytes(data)).configuration()

    def test_extent_tree_depth_refused(self):
        data = fixture()
        struct.pack_into('<H', data, 2 * 4096 + 13 * 512 + 46, 1)
        with self.assertRaises(rc.UnsupportedImage):
            rc.ExtImage(bytes(data)).configuration()

    def test_truncated_image_rejected(self):
        with self.assertRaises(rc.UnsupportedImage):
            rc.ExtImage(bytes(fixture()[:1024]))

    def test_unexpected_content_rejected(self):
        data = fixture()
        data[30 * 4096] = ord('X')
        with self.assertRaises(rc.UnsupportedImage):
            rc.ExtImage(bytes(data)).configuration()

    def test_wrong_profile_size_rejected(self):
        with self.assertRaises(rc.UnsupportedImage):
            rc.prepare(bytes(fixture()), rc.BEFORE)

    def test_cli_never_overwrites_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, reference, output = root / 'original', root / 'reference', root / 'output'
            original.write_bytes(fixture())
            reference.write_bytes(rc.BEFORE)
            output.write_bytes(b'keep me')
            with contextlib.redirect_stderr(io.StringIO()):
                result = rc.main(['patch', str(original), '--reference-file', str(reference),
                                  '--output', str(output)])
            self.assertEqual(result, 2)
            self.assertEqual(output.read_bytes(), b'keep me')


if __name__ == '__main__':
    unittest.main()
