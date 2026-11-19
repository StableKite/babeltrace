"""Check native bindings with independent trace collections across threads."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import sysconfig
from threading import Barrier
import unittest

import babeltrace


class FreeThreadedTraceReader(unittest.TestCase):
    @unittest.skipUnless(sysconfig.get_config_var("Py_GIL_DISABLED"), "requires FT Python")
    def test_read_independent_collections(self):
        self.assertIsNone(sys.flags.gil)
        self.assertFalse(sys._is_gil_enabled())
        trace = Path(__file__).resolve().parents[2] / "ctf-traces" / "succeed" / "succeed1"

        def read_events():
            collection = babeltrace.TraceCollection()
            self.assertIsNotNone(collection.add_trace(str(trace), "ctf"))
            return [(event.name, event.timestamp) for event in collection.events]

        expected = read_events()
        self.assertTrue(expected)
        start = Barrier(8, timeout=30)

        def read_repeatedly(_worker):
            start.wait()
            for _ in range(16):
                self.assertEqual(read_events(), expected)

        with ThreadPoolExecutor(max_workers=8) as workers:
            list(workers.map(read_repeatedly, range(8)))
        self.assertFalse(sys._is_gil_enabled())


if __name__ == "__main__":
    unittest.main()
