#!/usr/bin/env python3
"""Run fidelity tests, each against its own fresh emulator container.

usage: python3 -I scripts/run_fidelity.py <suite-dir> <new-output-dir> <tests-file> [workers] [runner options...]

Runner options, such as --retry-timeout, are passed to `fidelity-tests-runner run`.

<tests-file> lists one manifest `path` per line. For each test this starts the pinned image
(telemetry off, host port on 127.0.0.1 only, 2 GB), copies out the emulator's CA and credentials,
runs `fidelity-tests-runner run`, writes reports/<check_id>.json, and removes the container.
runs.csv records the runner exit code (0 passed, 11 failed, 12 error) and duration per test.
"""
import csv, os, ssl, subprocess, sys, tempfile, time, threading, urllib.request
from concurrent.futures import ThreadPoolExecutor

IMAGE = "aws-emulator:pinned"
BASE_PORT = 9400


def sh(*a, **k):
    return subprocess.run(a, capture_output=True, text=True, **k)


def run_one(suite, out, path, worker, extra=()):
    check = os.path.basename(os.path.dirname(path)) + "." + os.path.basename(path)[len("check_"):-3]
    name, port = f"fidelity-{worker}", BASE_PORT + worker
    t0, rc, note = time.time(), None, ""
    sh("docker", "rm", "-f", name)
    try:
        r = sh("docker", "run", "-d", "--name", name, "-e", "EMULATOR_TELEMETRY=off",
               "-p", f"127.0.0.1:{port}:9297", "--memory", "2g", IMAGE)
        if r.returncode:
            raise RuntimeError(r.stderr.strip())
        ctx = ssl._create_unverified_context()
        for _ in range(300):
            try:
                urllib.request.urlopen(f"https://127.0.0.1:{port}/__admin/health", context=ctx, timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("emulator never became healthy")
        with tempfile.TemporaryDirectory() as td:
            for f in ("ca.pem", "emulator_credentials"):
                r = sh("docker", "cp", f"{name}:/home/emulator/.aws/emulator/9297/{f}", td)
                if r.returncode:
                    raise RuntimeError(r.stderr.strip())
            p = sh("uv", "run", "--no-sync", "fidelity-tests-runner", "run", path,
                   "--endpoint", f"https://127.0.0.1:{port}",
                   "--credentials-file", f"{td}/emulator_credentials",
                   "--ca-bundle", f"{td}/ca.pem",
                   "--report", f"{out}/reports/{check}.json", *extra, cwd=suite, timeout=1500)
            rc = p.returncode
            if rc not in (0, 11):
                note = (p.stderr or p.stdout).strip().splitlines()[-1:] and (p.stderr or p.stdout).strip().splitlines()[-1][:200]
    except Exception as e:  # harness failure, not a test verdict
        note = f"harness: {e}"[:200]
    finally:
        sh("docker", "rm", "-f", name)
    return {"check_id": check, "path": path, "exit_code": rc, "seconds": round(time.time() - t0, 1), "note": note}


def main(suite, out, tests_file, workers="1", *extra):
    suite, out = os.path.abspath(suite), os.path.abspath(out)
    os.makedirs(f"{out}/reports")
    tests = [l.strip() for l in open(tests_file) if l.strip()]
    lock, done = threading.Lock(), [0]
    free = list(range(int(workers)))
    with open(f"{out}/runs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, ["check_id", "path", "exit_code", "seconds", "note"])
        w.writeheader()

        def task(path):
            with lock:
                wk = free.pop()
            try:
                row = run_one(suite, out, path, wk, extra)
            finally:
                with lock:
                    free.append(wk)
            with lock:
                w.writerow(row); fh.flush(); done[0] += 1
                if done[0] % 10 == 0:
                    print(f"{done[0]}/{len(tests)}", flush=True)

        with ThreadPoolExecutor(int(workers)) as ex:
            list(ex.map(task, tests))


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
