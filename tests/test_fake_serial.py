"""Self-check for the test-only Grbl stub (web.server._FakeGrbl)."""
import os
import unittest

os.environ['PLOTTER_FAKE_SERIAL'] = '1'
from web import server  # noqa: E402  (env must be set before import)


class FakeGrblTest(unittest.TestCase):
    def setUp(self):
        server._FAKE_SERIAL_WRITES.clear()

    def test_open_serial_returns_stub_when_enabled(self):
        self.assertIsInstance(server.open_serial('socket://nope:1'), server._FakeGrbl)

    def test_command_gets_ok_and_is_captured(self):
        s = server.open_serial('x')
        s.write(b'G00 X1 Y2\n')
        self.assertEqual(s.readline(), b'ok\r\n')
        self.assertIn('G00 X1 Y2', server._FAKE_SERIAL_WRITES)

    def test_status_query_reports_idle(self):
        s = server.open_serial('x')
        s.write(b'?\n')
        self.assertIn(b'Idle', s.read(s.in_waiting))

    def test_soft_reset_is_silent(self):
        s = server.open_serial('x')
        s.write(b'\x18')
        self.assertEqual(s.in_waiting, 0)
        self.assertEqual(server._FAKE_SERIAL_WRITES, [])


if __name__ == '__main__':
    unittest.main()
