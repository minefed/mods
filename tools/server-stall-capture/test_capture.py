import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("capture", Path(__file__).with_name("capture.py"))
capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)


class Runner:
    def __init__(self, failure=None):
        self.calls = []
        self.failure = failure

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        assert kwargs["timeout"] <= 60
        output = ""
        if "jcmd" in argv:
            assert "timeout" in argv
            assert argv[argv.index("jcmd") + 1] == "42"
        if "VM.version" in argv:
            output = "OpenJDK 64-Bit Server VM\nJDK 21.0.5"
        if "JFR.start" in argv:
            if self.failure == "timeout":
                raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
            output = "Error: attach failed" if self.failure == "error-text" else "Started recording 1."
        if "JFR.stop" in argv:
            if self.failure == "stop-timeout":
                raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
            output = "No recording found" if self.failure == "auto-stopped" else "Stopped recording test."
        if "summary" in argv:
            output = "Not a valid JFR file" if self.failure == "invalid-jfr" else "Version: 2.1\nChunks: 1"
            if self.failure == "zero-chunks":
                output = "Version: 2.1\nChunks: 0"
        if "sha256sum" in argv:
            output = hashlib.sha256(b"FLR\x00" + bytes(100)).hexdigest() + "  " + argv[-1]
        if "Thread.print" in argv:
            output = "Full thread dump OpenJDK 64-Bit Server VM"
        if argv[:2] == ["podman", "cp"]:
            copied = b"FLR\x00" + (bytes([1]) * 100 if self.failure == "corrupt-copy" else bytes(100))
            Path(argv[-1]).write_bytes(b"" if self.failure == "empty-copy" else copied)
        return subprocess.CompletedProcess(argv, 0, output, "")


class CaptureTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.args = argparse.Namespace(mode="record", container="test-server", pid=42, user="1000",
                                       output=str(Path(self.temp.name) / "new"), duration=10, interval=2)

    def execute(self, failure=None, interrupted=False):
        runner = Runner(failure)
        def sleep(_):
            if interrupted:
                raise KeyboardInterrupt
        task = capture.Capture(self.args, runner=runner, sleeper=sleep)
        # Elapse the bounded collection window without real time or live processes.
        with patch.object(capture.time, "monotonic", side_effect=[0, 0, 0, 11]):
            code = task.run()
        return code, task, runner

    def test_jfr_success_and_only_own_recording_stop(self):
        code, task, runner = self.execute()
        self.assertEqual(code, 0)
        stop = next(call for call in runner.calls if "JFR.stop" in call)
        self.assertIn("name=" + task.name, stop)
        self.assertNotIn("name=all", stop)
        start = next(call for call in runner.calls if "JFR.start" in call)
        self.assertIn("duration=40s", start)
        self.assertIn("maxsize=128M", start)
        for event in ("InitialEnvironmentVariable", "InitialSystemProperty", "JVMInformation"):
            self.assertIn("jdk." + event + "#enabled=false", start)
        self.assertEqual(task.manifest["status"], "complete")

    def test_error_text_with_success_exit_is_failure(self):
        code, task, runner = self.execute("error-text")
        self.assertEqual(code, 1)
        self.assertTrue(any("JFR.stop" in call for call in runner.calls))
        self.assertTrue(any("success marker absent" in error for error in task.errors))

    def test_timeout_still_attempts_own_recording_cleanup(self):
        code, task, runner = self.execute("timeout")
        self.assertEqual(code, 1)
        self.assertTrue(any("JFR.stop" in call for call in runner.calls))
        self.assertIn("failed", task.manifest["status"])

    def test_interrupt_finalizes_and_exports_recording(self):
        code, task, runner = self.execute(interrupted=True)
        self.assertEqual(code, 0)
        self.assertTrue(task.manifest["interrupted"])
        self.assertTrue((task.out / "recording.jfr").exists())

    def test_invalid_summary_is_failure(self):
        code, task, _ = self.execute("invalid-jfr")
        self.assertEqual(code, 1)
        self.assertFalse((task.out / "recording.jfr").exists())

    def test_empty_copy_is_failure(self):
        code, task, _ = self.execute("empty-copy")
        self.assertEqual(code, 1)
        self.assertTrue(any("invalid header" in error for error in task.errors))

    def test_nonempty_corrupted_copy_is_failure(self):
        code, task, _ = self.execute("corrupt-copy")
        self.assertEqual(code, 1)
        self.assertTrue(any("SHA-256 differs" in error for error in task.errors))
        self.assertNotEqual(task.manifest["remote_jfr_sha256"], task.manifest["local_jfr_sha256"])

    def test_zero_chunk_summary_is_failure(self):
        code, task, _ = self.execute("zero-chunks")
        self.assertEqual(code, 1)
        self.assertTrue(any("no positive chunk count" in error for error in task.errors))
        self.assertFalse((task.out / "recording.jfr").exists())

    def test_recovery_manifest_precedes_external_commands(self):
        runner = Runner()
        task = capture.Capture(self.args, runner=runner)
        initial = json.loads((task.out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(initial["status"], "collecting")
        self.assertEqual(initial["recording_name"], task.name)
        self.assertEqual(initial["remote_jfr"], task.remote)
        self.assertEqual(runner.calls, [])

    def test_timeout_preserves_partial_stdout_and_stderr(self):
        task = capture.Capture(self.args, runner=Runner())
        for index, (stdout, stderr) in enumerate(((b"partial out\xff", b"partial err"), ("text out", "text err"))):
            with self.subTest(stdout=stdout):
                def timeout(*_, **kwargs):
                    raise subprocess.TimeoutExpired("test", kwargs["timeout"], output=stdout, stderr=stderr)
                task.runner = timeout
                code, output = task.command("timeout-%d" % index, ["test"], required=False)
                self.assertEqual(code, -1)
                self.assertIn("TIMEOUT after 30 seconds", output)
                self.assertIn("partial out" if isinstance(stdout, bytes) else stdout, output)
                self.assertIn("partial err" if isinstance(stderr, bytes) else stderr, output)
                self.assertEqual((task.out / ("timeout-%d.txt" % index)).read_text(encoding="utf-8"), output)

    def test_autostopped_file_is_recovered_but_uncertainty_is_failure(self):
        code, task, _ = self.execute("auto-stopped")
        self.assertEqual(code, 1)
        self.assertTrue((task.out / "recording.jfr").exists())
        self.assertEqual(task.manifest["status"], "failed")

    def test_stop_timeout_still_recovers_valid_file(self):
        code, task, _ = self.execute("stop-timeout")
        self.assertEqual(code, 1)
        self.assertTrue((task.out / "recording.jfr").exists())
        self.assertEqual(task.manifest["remote_jfr_sha256"], task.manifest["local_jfr_sha256"])

    def test_snapshot_is_independent_and_never_controls_jfr(self):
        self.args.mode = "snapshot"
        code, task, runner = self.execute()
        self.assertEqual(code, 0)
        self.assertEqual(sum("Thread.print" in call for call in runner.calls), 3)
        self.assertFalse(any("JFR.start" in call or "JFR.stop" in call for call in runner.calls))
        self.assertTrue((task.out / "sample-0000.txt").exists())

    def test_invalid_pid(self):
        for value in ("0", "-1", "all", "1;id", "1.0"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                capture.positive_pid(value)

    def test_existing_output_is_never_overwritten(self):
        folder = Path(self.args.output)
        folder.mkdir()
        marker = folder / "manifest.json"
        marker.write_text("preserve", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            capture.Capture(self.args, runner=Runner())
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()
