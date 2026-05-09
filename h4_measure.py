#!/usr/bin/python3

import subprocess
import time
import re
import json
import csv
from datetime import datetime
from pathlib import Path

# ============================================================
# Mérési konfiguráció — H4: task típusok skálázódási profiljának
#                            összehasonlítása
# ============================================================

RUNS = 5
DURATION = 30           # rövidebb a network task lassúsága miatt
WARMUP = 10
COOLDOWN = 5
SERVER_STARTUP_WAIT = 3 # network mód lassabb start (curl init)
QUEUE_SIZE = 2048
WORKERS = 8             # H2 optimum

# Csökkentett tartomány a network task lassúsága miatt
CONNECTIONS = [1, 2, 4, 8, 16, 32, 64]

# Upstream URL a network task számára
UPSTREAM_URL = "https://time.now/developer/api/timezone/Europe/London"

# Task típusok (név, flag-ek)
TASK_TYPES = [
    ("cpu", ["--cpu"]),
    ("io", ["--io-heavy"]),
    ("network", ["--upstream", UPSTREAM_URL]),  # default worker + custom upstream
]

# Mag-pinning
SERVER_CORES = "0-3"
WRK_CORES = "6-7"
WRK_THREADS_DEFAULT = 2

ADDR = "http://127.0.0.1:1234"
SERVER_BIN = "build/src/cppserver"

TIMESTAMP = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
LOG_DIR = Path(f"results_h4_{TIMESTAMP}")
LOG_DIR.mkdir(exist_ok=True)
RAW_LOG = LOG_DIR / "wrk_raw.log"
CSV_LOG = LOG_DIR / "wrk_results.csv"
META_LOG = LOG_DIR / "metadata.json"


# ============================================================
# wrk parser (változatlan)
# ============================================================

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


def wait_for_server(timeout=15):
    """Network task indulása lassabb, ezért 15s timeout."""
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


def start_server(task_flags):
    cmd = [
        "taskset", "-c", SERVER_CORES,
        SERVER_BIN,
        "--max-threads", str(WORKERS),
        "--max-queue", str(QUEUE_SIZE),
    ] + task_flags
    print(f"  Starting: {' '.join(cmd)}")
    server = subprocess.Popen(cmd, stderr=subprocess.DEVNULL)
    time.sleep(SERVER_STARTUP_WAIT)
    if not wait_for_server():
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        raise RuntimeError("Server did not start in time")
    return server


def stop_server(server):
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        print("  Force killing server...")
        server.kill()
        server.wait()
    time.sleep(2)


def run_wrk(connections, duration):
    threads = 1 if connections == 1 else WRK_THREADS_DEFAULT
    cmd = (
        f"taskset -c {WRK_CORES} wrk "
        f"-c{connections} -d{duration}s -t{threads} "
        f"--timeout 30s --latency {ADDR}"
    )
    return subprocess.run(cmd, shell=True, capture_output=True, text=True), cmd


def measure_point(connections, duration, raw_f, run, task_name):
    run_wrk(connections, WARMUP)
    time.sleep(2)

    result, cmd = run_wrk(connections, duration)
    parsed = parse_wrk_output(result.stdout)

    raw_f.write(f"\n=== task={task_name}, c={connections}, run={run} ===\n")
    raw_f.write(f"CMD: {cmd}\n")
    raw_f.write(f"STDOUT:\n{result.stdout}\n")
    if result.stderr:
        raw_f.write(f"STDERR:\n{result.stderr}\n")
    raw_f.flush()

    return parsed


def main():
    total_points = len(TASK_TYPES) * len(CONNECTIONS) * RUNS
    sec_per_point = WARMUP + DURATION + COOLDOWN + 5
    server_starts = len(TASK_TYPES)
    total_sec = total_points * sec_per_point + server_starts * 5
    print(f"=== H4 mérés indítása ===")
    print(f"Pontok: {total_points}, várt idő: ~{total_sec/60:.0f} perc")
    print(f"Worker pool: {WORKERS}, Queue: {QUEUE_SIZE}")
    print(f"Kliensszámok: {CONNECTIONS}")
    print(f"Task típusok: {[n for n, _ in TASK_TYPES]}")
    print(f"Upstream URL (network): {UPSTREAM_URL}")
    print()

    metadata = {
        "timestamp": TIMESTAMP,
        "hypothesis": "H4",
        "description": "CPU, IO és network task skálázódási profiljának összehasonlítása",
        "config": {
            "runs": RUNS,
            "duration_sec": DURATION,
            "warmup_sec": WARMUP,
            "cooldown_sec": COOLDOWN,
            "queue_size": QUEUE_SIZE,
            "workers": WORKERS,
            "connections": CONNECTIONS,
            "task_types": [n for n, _ in TASK_TYPES],
            "upstream_url": UPSTREAM_URL,
            "server_cores": SERVER_CORES,
            "wrk_cores": WRK_CORES,
            "address": ADDR,
        }
    }
    with open(META_LOG, "w") as f:
        json.dump(metadata, f, indent=2)

    csv_fields = [
        "task", "connections", "run",
        "requests_per_sec",
        "latency_avg_ms", "latency_stdev_ms", "latency_max_ms",
        "latency_p50_ms", "latency_p75_ms", "latency_p90_ms", "latency_p99_ms",
        "total_requests", "socket_errors_connect", "socket_errors_read",
        "socket_errors_write", "socket_errors_timeout", "non_2xx_responses"
    ]
    with open(CSV_LOG, "w", newline="") as f:
        csv.writer(f).writerow(csv_fields)

    raw_f = open(RAW_LOG, "w")
    raw_f.write(f"=== H4 measurement, started {TIMESTAMP} ===\n")
    raw_f.write(json.dumps(metadata, indent=2) + "\n\n")

    parser_failures = 0
    point_idx = 0

    try:
        for task_name, task_flags in TASK_TYPES:
            print(f"\n--- Server: task={task_name} ---")
            server = start_server(task_flags)

            try:
                for connections in CONNECTIONS:
                    for run in range(1, RUNS + 1):
                        point_idx += 1
                        print(f"[{point_idx}/{total_points}] "
                              f"task={task_name}, c={connections}, run={run}")

                        parsed = measure_point(
                            connections, DURATION, raw_f, run, task_name
                        )

                        row = [task_name, connections, run] + [
                            parsed[k] if parsed[k] is not None else ""
                            for k in csv_fields[3:]
                        ]
                        with open(CSV_LOG, "a", newline="") as csv_f:
                            csv.writer(csv_f).writerow(row)

                        errors = (parsed["socket_errors_connect"] +
                                  parsed["socket_errors_read"] +
                                  parsed["socket_errors_write"] +
                                  parsed["socket_errors_timeout"])
                        if errors > 0:
                            print(f"  WARNING: {errors} socket errors")
                        if parsed["non_2xx_responses"] > 0:
                            print(f"  WARNING: {parsed['non_2xx_responses']} non-2xx")

                        rps_str = fmt(parsed["requests_per_sec"], ".1f")
                        p50_str = fmt(parsed["latency_p50_ms"], ".1f")
                        p99_str = fmt(parsed["latency_p99_ms"], ".1f")
                        print(f"  rps={rps_str}, p50={p50_str}ms, p99={p99_str}ms")

                        if parsed["requests_per_sec"] is None:
                            parser_failures += 1
                            print(f"  WARNING: parser failed")

                        time.sleep(COOLDOWN)
            finally:
                print(f"  Stopping server")
                stop_server(server)

    except KeyboardInterrupt:
        print("\nMeasurement interrupted by user.")
    finally:
        raw_f.close()

    print(f"\nDone. Results in {LOG_DIR}/")
    if parser_failures > 0:
        print(f"FIGYELEM: {parser_failures} parser failure")


if __name__ == "__main__":
    main()
