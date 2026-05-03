#!/usr/bin/python3

import subprocess
import time
import re
import json
import csv
from datetime import datetime
from pathlib import Path

# ============================================================
# Mérési konfiguráció — H1: telítési pont a kliensszám függvényében
# ============================================================

RUNS = 5
DURATION = 60
WARMUP = 10
COOLDOWN = 5
SERVER_STARTUP_WAIT = 2
QUEUE_SIZE = 2048
WRK_THREADS = 2  # default; c=1-nél automatikusan 1-re vált

CONNECTIONS = [1, 2, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256]

SERVER_CORES = "0-3"
WRK_CORES = "6-7"

ADDR = "http://127.0.0.1:1234"
SERVER_BIN = "build/src/cppserver"

TIMESTAMP = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
LOG_DIR = Path(f"results_{TIMESTAMP}")
LOG_DIR.mkdir(exist_ok=True)
RAW_LOG = LOG_DIR / "wrk_raw.log"
CSV_LOG = LOG_DIR / "wrk_results.csv"
META_LOG = LOG_DIR / "metadata.json"


def parse_wrk_output(stdout):
    result = {
        "requests_per_sec": None,
        "transfer_per_sec": None,
        "latency_avg_ms": None,
        "latency_stdev_ms": None,
        "latency_max_ms": None,
        "latency_p50_ms": None,
        "latency_p75_ms": None,
        "latency_p90_ms": None,
        "latency_p99_ms": None,
        "total_requests": None,
        "socket_errors_connect": 0,
        "socket_errors_read": 0,
        "socket_errors_write": 0,
        "socket_errors_timeout": 0,
        "non_2xx_responses": 0,
    }

    def to_ms(value, unit):
        v = float(value)
        unit = unit.lower()
        if unit == "us":
            return v / 1000.0
        if unit == "ms":
            return v
        if unit == "s":
            return v * 1000.0
        if unit == "m":
            return v * 60_000.0
        return v

    m = re.search(
        r"Latency\s+([\d.]+)(us|ms|s|m)\s+([\d.]+)(us|ms|s|m)\s+([\d.]+)(us|ms|s|m)",
        stdout
    )
    if m:
        result["latency_avg_ms"] = to_ms(m.group(1), m.group(2))
        result["latency_stdev_ms"] = to_ms(m.group(3), m.group(4))
        result["latency_max_ms"] = to_ms(m.group(5), m.group(6))

    for pct, key in [("50", "latency_p50_ms"), ("75", "latency_p75_ms"),
                      ("90", "latency_p90_ms"), ("99", "latency_p99_ms")]:
        m = re.search(rf"{pct}%\s+([\d.]+)(us|ms|s|m)", stdout)
        if m:
            result[key] = to_ms(m.group(1), m.group(2))

    m = re.search(r"Requests/sec:\s*([\d.]+)", stdout, re.IGNORECASE)
    if m:
        result["requests_per_sec"] = float(m.group(1))

    m = re.search(r"Transfer/sec:\s*(\S+)", stdout, re.IGNORECASE)
    if m:
        result["transfer_per_sec"] = m.group(1)

    m = re.search(r"(\d+)\s+requests\s+in", stdout)
    if m:
        result["total_requests"] = int(m.group(1))

    m = re.search(
        r"Socket errors:\s+connect\s+(\d+),\s+read\s+(\d+),\s+write\s+(\d+),\s+timeout\s+(\d+)",
        stdout
    )
    if m:
        result["socket_errors_connect"] = int(m.group(1))
        result["socket_errors_read"] = int(m.group(2))
        result["socket_errors_write"] = int(m.group(3))
        result["socket_errors_timeout"] = int(m.group(4))

    m = re.search(r"Non-2xx or 3xx responses:\s+(\d+)", stdout)
    if m:
        result["non_2xx_responses"] = int(m.group(1))

    return result


def fmt(val, spec=".0f"):
    if val is None:
        return "N/A"
    return f"{val:{spec}}"


def wait_for_server(timeout=10):
    for _ in range(timeout * 2):
        try:
            r = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", ADDR],
                capture_output=True, text=True, timeout=2
            )
            if r.stdout.strip().startswith("2"):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def run_wrk(connections, duration):
    # JAVÍTÁS: c=1 esetén csak 1 thread, különben a wrk korán kilép
    threads = 1 if connections == 1 else WRK_THREADS
    cmd = (
        f"taskset -c {WRK_CORES} wrk "
        f"-c{connections} -d{duration}s -t{threads} --latency {ADDR}"
    )
    return subprocess.run(cmd, shell=True, capture_output=True, text=True), cmd


def main():
    metadata = {
        "timestamp": TIMESTAMP,
        "hypothesis": "H1",
        "description": "Telítési pont a kliensszám függvényében (CPU-bound)",
        "config": {
            "runs": RUNS,
            "duration_sec": DURATION,
            "warmup_sec": WARMUP,
            "cooldown_sec": COOLDOWN,
            "queue_size": QUEUE_SIZE,
            "wrk_threads": WRK_THREADS,
            "wrk_threads_note": "c=1 esetén automatikusan 1 thread",
            "connections": CONNECTIONS,
            "server_cores": SERVER_CORES,
            "wrk_cores": WRK_CORES,
            "address": ADDR,
        }
    }
    with open(META_LOG, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"=== Starting server (queue={QUEUE_SIZE}, cores={SERVER_CORES}) ===")
    server_cmd = [
        "taskset", "-c", SERVER_CORES,
        SERVER_BIN, "--cpu", "--max-queue", str(QUEUE_SIZE)
    ]
    server = subprocess.Popen(server_cmd)
    time.sleep(SERVER_STARTUP_WAIT)

    if not wait_for_server():
        print("ERROR: Server did not start in time.")
        server.terminate()
        return

    print("Server is up. Starting measurements.")

    csv_fields = [
        "run", "connections", "requests_per_sec",
        "latency_avg_ms", "latency_stdev_ms", "latency_max_ms",
        "latency_p50_ms", "latency_p75_ms", "latency_p90_ms", "latency_p99_ms",
        "total_requests", "socket_errors_connect", "socket_errors_read",
        "socket_errors_write", "socket_errors_timeout", "non_2xx_responses"
    ]
    with open(CSV_LOG, "w", newline="") as f:
        csv.writer(f).writerow(csv_fields)

    raw_f = open(RAW_LOG, "w")
    raw_f.write(f"=== H1 measurement, started {TIMESTAMP} ===\n")
    raw_f.write(json.dumps(metadata, indent=2) + "\n\n")

    total_points = RUNS * len(CONNECTIONS)
    point_idx = 0
    parser_failures = 0

    try:
        for run in range(1, RUNS + 1):
            for con in CONNECTIONS:
                point_idx += 1
                print(f"[{point_idx}/{total_points}] run={run}, c={con}")

                run_wrk(con, WARMUP)
                time.sleep(2)

                result, cmd = run_wrk(con, DURATION)
                parsed = parse_wrk_output(result.stdout)

                raw_f.write(f"\n=== run={run}, c={con} ===\n")
                raw_f.write(f"CMD: {cmd}\n")
                raw_f.write(f"STDOUT:\n{result.stdout}\n")
                if result.stderr:
                    raw_f.write(f"STDERR:\n{result.stderr}\n")
                raw_f.flush()

                row = [run, con] + [
                    parsed[k] if parsed[k] is not None else ""
                    for k in csv_fields[2:]
                ]
                with open(CSV_LOG, "a", newline="") as csv_f:
                    csv.writer(csv_f).writerow(row)

                errors = (parsed["socket_errors_connect"] +
                          parsed["socket_errors_read"] +
                          parsed["socket_errors_write"] +
                          parsed["socket_errors_timeout"])
                if errors > 0:
                    print(f"  WARNING: {errors} socket errors at c={con}")
                if parsed["non_2xx_responses"] > 0:
                    print(f"  WARNING: {parsed['non_2xx_responses']} non-2xx responses")

                rps_str = fmt(parsed["requests_per_sec"], ".0f")
                p50_str = fmt(parsed["latency_p50_ms"], ".1f")
                p99_str = fmt(parsed["latency_p99_ms"], ".1f")
                print(f"  rps={rps_str}, p50={p50_str}ms, p99={p99_str}ms")

                if parsed["requests_per_sec"] is None:
                    parser_failures += 1
                    print(f"  WARNING: parser failed at c={con}, run={run} — "
                          f"check {RAW_LOG.name}")

                time.sleep(COOLDOWN)

    except KeyboardInterrupt:
        print("\nMeasurement interrupted by user.")
    finally:
        raw_f.close()
        print("Stopping server...")
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Force killing server...")
            server.kill()
            server.wait()

    print(f"\nDone. Results in {LOG_DIR}/")
    print(f"  - {RAW_LOG.name}: teljes wrk kimenet")
    print(f"  - {CSV_LOG.name}: parsolt eredmények")
    print(f"  - {META_LOG.name}: konfiguráció és metaadatok")
    if parser_failures > 0:
        print(f"\nFIGYELEM: {parser_failures} mérésnél hiányzott a Requests/sec érték.")
        print(f"Nézd meg a {RAW_LOG.name} fájlt a részletekért.")


if __name__ == "__main__":
    main()
