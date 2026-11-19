"""Check native bindings with independent trace collections across threads."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import sysconfig
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
import uuid

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

    @unittest.skipUnless(sysconfig.get_config_var("Py_GIL_DISABLED"), "requires FT Python")
    def test_write_and_read_independent_traces(self):
        self.assertIsNone(sys.flags.gil)
        self.assertFalse(sys._is_gil_enabled())
        start = Barrier(8, timeout=30)
        ctf = babeltrace.CTFWriter

        def write_trace(path, values):
            writer = ctf.Writer(str(path))
            clock = ctf.Clock("worker_clock")
            clock.uuid = uuid.uuid4()
            writer.add_clock(clock)
            event_type = ctf.EventClass("thread_event")
            event_type.add_field(ctf.IntegerFieldDeclaration(32), "value")
            stream_type = ctf.StreamClass("worker_stream")
            stream_type.clock = clock
            stream_type.add_event_class(event_type)
            stream = writer.create_stream(stream_type)
            for timestamp, value in enumerate(values):
                clock.time = timestamp
                event = ctf.Event(event_type)
                event.payload("value").value = value
                stream.append_event(event)
            stream.flush()

        def round_trip(worker):
            start.wait()
            with TemporaryDirectory() as directory:
                values = list(range(worker * 16, (worker + 1) * 16))
                write_trace(directory, values)
                collection = babeltrace.TraceCollection()
                self.assertIsNotNone(collection.add_trace(directory, "ctf"))
                self.assertEqual([event["value"] for event in collection.events], values)

        with ThreadPoolExecutor(max_workers=8) as workers:
            list(workers.map(round_trip, range(8)))
        self.assertFalse(sys._is_gil_enabled())


if __name__ == "__main__":
    unittest.main()
