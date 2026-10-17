#!/usr/bin/env python3
"""Bounded, operator-invoked diagnostics for a Linux Podman Minecraft JVM."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import threading
import time
import uuid


PREFLIGHT = r'''
set -eu
command -v timeout
command -v jcmd
command -v jfr
command -v sha256sum
test -r "/proc/$1/stat"
test -r "/proc/$1/cgroup"
'''
SAMPLE = r'''
read_file() {
    printf '\n=== %s ===\n' "$1"
    if [ -r "$1" ]; then cat "$1"; else printf 'MISSING_OR_UNREADABLE\n'; fi
}
for f in stat status io schedstat cgroup; do read_file "/proc/$1/$f"; done
for f in /proc/stat /proc/meminfo /proc/loadavg /proc/net/dev /proc/pressure/cpu /proc/pressure/io /proc/pressure/memory; do read_file "$f"; done
cg=$(awk -F: '$1 == "0" {print $3}' "/proc/$1/cgroup")
printf '\nCGROUP_V2_REPORTED_PATH=%s\n' "$cg"
case "$cg" in
    /*) for base in "/sys/fs/cgroup$cg" /sys/fs/cgroup; do
        printf '\nCGROUP_CANDIDATE=%s\n' "$base"
        if [ ! -d "$base" ]; then printf 'MISSING_DIRECTORY\n'; continue; fi
        for f in cgroup.controllers cgroup.procs cpu.stat cpu.max io.stat memory.current memory.max memory.events cpu.pressure io.pressure memory.pressure; do read_file "$base/$f"; done
    done ;;
    *) printf 'NO_CGROUP_V2_PATH_FOUND\n' ;;
esac
'''


class CaptureError(Exception):
    pass


def utc():
    return datetime.now(timezone.utc).isoformat()


def positive_pid(value):
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise argparse.ArgumentTypeError("PID must be a positive integer; PID 0 is forbidden")
    return int(value)


def uid(value):
    if not re.fullmatch(r"0|[1-9][0-9]*", value):
        raise argparse.ArgumentTypeError("--user must be a numeric UID (0 is allowed)")
    return value


class Capture:
    def __init__(self, args, runner=subprocess.run, sleeper=time.sleep):
        self.args, self.runner, self.sleep = args, runner, sleeper
        self.out = Path(args.output)
        self.out.mkdir(mode=0o700, parents=True, exist_ok=False)
        self.name = "minefed_stall_" + uuid.uuid4().hex
        self.remote = "/tmp/" + self.name + ".jfr"
        self.errors = []
        self.stop_samples = threading.Event()
        self.worker = None
        self.interrupted = False
        self.manifest = {"started_utc": utc(), "mode": args.mode,
                         "container": args.container, "pid": args.pid, "uid": args.user,
                         "recording_name": self.name, "remote_jfr": self.remote,
                         "duration_seconds": args.duration, "interval_seconds": args.interval,
                         "status": "collecting", "errors": []}
        self.write_manifest()

    def write_manifest(self):
        temporary = self.out / "manifest.json.tmp"
        temporary.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.out / "manifest.json")

    def command(self, label, argv, timeout=30, required=True):
        started = utc()
        try:
            result = self.runner(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
                                 encoding="utf-8", errors="replace")
            output = (result.stdout or "") + (result.stderr or "")
            code = result.returncode
        except subprocess.TimeoutExpired as exc:
            def decode(value):
                return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else (value or "")
            output = ("TIMEOUT after %s seconds\n--- partial stdout ---\n" % timeout
                      + decode(exc.stdout) + "\n--- partial stderr ---\n" + decode(exc.stderr))
            code = -1
        except OSError as exc:
            output, code = str(exc), -1
        (self.out / (label + ".txt")).write_text(output, encoding="utf-8")
        (self.out / (label + ".json")).write_text(json.dumps(
            {"started_utc": started, "ended_utc": utc(), "returncode": code,
             "timeout_seconds": timeout}, indent=2), encoding="utf-8")
        if code != 0:
            message = label + ": command failed or timed out (see raw output)"
            self.errors.append(message)
            if required:
                raise CaptureError(message)
        return code, output

    def container(self, *argv):
        return ["podman", "exec", "--user", self.args.user, self.args.container, *argv]

    def jcmd(self, label, *operation):
        return self.command(label, self.container("timeout", "-k", "2s", "20s", "jcmd",
                                                  str(self.args.pid), *operation))

    def require_text(self, label, output, marker):
        if marker not in output:
            message = label + ": expected success marker absent (attach may have failed)"
            self.errors.append(message)
            raise CaptureError(message)

    def preflight(self):
        self.command("preflight", self.container("sh", "-c", PREFLIGHT, "capture", str(self.args.pid)))

    def check_jvm(self):
        # This also verifies attach permission and that the supplied PID is a JVM.
        _, output = self.jcmd("jvm-version", "VM.version")
        self.require_text("jvm-version", output, "JDK")

    def sample_loop(self):
        index = 0
        while not self.stop_samples.is_set():
            try:
                self.command("sample-%04d" % index,
                             self.container("timeout", "-k", "2s", "8s", "sh", "-c",
                                            SAMPLE, "capture", str(self.args.pid)), timeout=15, required=False)
            except Exception as exc:
                self.errors.append("OS sample worker failed: " + str(exc))
                return
            index += 1
            self.stop_samples.wait(self.args.interval)

    def logs(self):
        self.command("recent-container-log", ["podman", "logs", "--timestamps", "--since", "15m",
                                             "--tail", "10000", self.args.container], required=False)

    def stop_recording(self):
        _, output = self.jcmd("jfr-stop", "JFR.stop", "name=" + self.name, "filename=" + self.remote)
        self.require_text("jfr-stop", output, "Stopped recording")

    def export_recording(self):
        _, output = self.command("jfr-summary", self.container("timeout", "-k", "2s", "20s",
                                                              "jfr", "summary", self.remote))
        self.require_text("jfr-summary", output, "Version:")
        chunks = re.search(r"(?m)^\s*Chunks:\s*([0-9]+)\s*$", output)
        if not chunks or int(chunks.group(1)) <= 0:
            raise CaptureError("jfr-summary: no positive chunk count; recording is invalid or empty")
        _, digest_output = self.command("jfr-remote-sha256", self.container("timeout", "-k", "2s", "20s",
                                                                          "sha256sum", self.remote))
        remote_digest = digest_output.split()[0] if digest_output.split() else ""
        if not re.fullmatch(r"[0-9a-fA-F]{64}", remote_digest):
            raise CaptureError("jfr-remote-sha256: no valid SHA-256 digest returned")
        destination = self.out / "recording.jfr"
        self.command("jfr-copy", ["podman", "cp", self.args.container + ":" + self.remote,
                                  str(destination)], timeout=60)
        with destination.open("rb") as stream:
            if destination.stat().st_size < 68 or stream.read(4) != b"FLR\x00":
                self.errors.append("JFR copy is empty, truncated, or has an invalid header")
                raise CaptureError(self.errors[-1])
            stream.seek(0)
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        self.manifest.update({"remote_jfr_sha256": remote_digest.lower(), "local_jfr_sha256": digest.hexdigest()})
        if digest.hexdigest() != remote_digest.lower():
            raise CaptureError("JFR copy SHA-256 differs from the validated container recording")

    def record(self):
        requested = False
        try:
            requested = True
            # Extra 30 seconds allows an explicit stop after the requested collection window.
            # The JVM still stops by itself if this wrapper or its terminal disappears.
            _, output = self.jcmd("jfr-start", "JFR.start", "name=" + self.name, "settings=profile",
                                  "duration=%ds" % (self.args.duration + 30), "maxage=10m",
                                  "maxsize=128M", "disk=true", "filename=" + self.remote,
                                  "jdk.InitialEnvironmentVariable#enabled=false",
                                  "jdk.InitialSystemProperty#enabled=false", "jdk.JVMInformation#enabled=false")
            self.require_text("jfr-start", output, "Started recording")
            deadline = time.monotonic() + self.args.duration
            while time.monotonic() < deadline:
                self.sleep(min(1, max(0, deadline - time.monotonic())))
        except KeyboardInterrupt:
            self.interrupted = True
        except (CaptureError, OSError) as exc:
            if str(exc) not in self.errors:
                self.errors.append(str(exc))
        finally:
            if requested:
                try:
                    self.stop_recording()
                except (CaptureError, OSError) as exc:
                    if str(exc) not in self.errors:
                        self.errors.append(str(exc))
        # A timed-out stop or the JVM's own duration fallback may still have saved a valid file.
        self.export_recording()

    def snapshot(self):
        for index in range(3):
            _, output = self.jcmd("threads-%d" % (index + 1), "Thread.print", "-l")
            self.require_text("threads-%d" % (index + 1), output, "Full thread dump")
            if index < 2:
                self.sleep(2)

    def run(self):
        try:
            self.preflight()
            self.worker = threading.Thread(target=self.sample_loop, daemon=True)
            self.worker.start()
            self.check_jvm()
            if self.args.mode == "record":
                self.record()
            else:
                self.snapshot()
        except KeyboardInterrupt:
            self.interrupted = True
            self.errors.append("Interrupted before capture completed")
        except (CaptureError, OSError) as exc:
            if str(exc) not in self.errors:
                self.errors.append(str(exc))
        finally:
            self.stop_samples.set()
            if self.worker:
                self.worker.join(timeout=17)
                if self.worker.is_alive():
                    self.errors.append("OS sample worker did not finish within its timeout")
            try:
                self.logs()
            except KeyboardInterrupt:
                self.errors.append("Interrupted while collecting final logs")
            self.manifest.update({"ended_utc": utc(), "interrupted": self.interrupted,
                                  "status": "failed" if self.errors else "complete", "errors": self.errors})
            self.write_manifest()
        return 1 if self.errors else 0


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("mode", choices=("record", "snapshot"))
    result.add_argument("--container", required=True, help="Exact Podman container name or ID")
    result.add_argument("--pid", required=True, type=positive_pid, help="JVM PID inside that container")
    result.add_argument("--user", required=True, type=uid, help="Numeric container UID with attach permission")
    result.add_argument("--output", required=True, help="New local directory; existing paths are refused")
    result.add_argument("--duration", type=int, default=600, help="record collection seconds (10..3600; default 600)")
    result.add_argument("--interval", type=float, default=3, help="OS sample interval seconds (2..5)")
    return result


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    if not 10 <= args.duration <= 3600 or not 2 <= args.interval <= 5:
        cli.error("--duration must be 10..3600 and --interval must be 2..5")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.container):
        cli.error("Invalid container name or ID")
    try:
        capture = Capture(args)
    except OSError as exc:
        cli.error("Cannot create a new output directory: " + str(exc))
    code = capture.run()
    print(("Capture failed; inspect " if code else "Capture complete: ") + str(capture.out / "manifest.json"))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
