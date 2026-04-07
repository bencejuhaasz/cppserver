#!/usr/bin/python3

import re
import matplotlib.pyplot as plt
from collections import defaultdict
import sys

if len(sys.argv) != 2:
    print("Usage: python plot_wrk.py <logfile>")
    sys.exit(1)

log_path = sys.argv[1]

data = defaultdict(list)

current_queue = None
current_conn = None
current_requests = None

with open(log_path, "r") as f:
    for line in f:
        line = line.strip()

        # fejléc parsing
        m = re.match(r"=== max-queue=(\d+), threads=\d+, connections=(\d+) ===", line)
        if m:
            current_queue = int(m.group(1))
            current_conn = int(m.group(2))
            current_requests = None

        # total requests parsing
        rm = re.search(r"(\d+) requests in", line)
        if rm:
            current_requests = int(rm.group(1))

        # socket errors parsing
        em = re.search(
            r"Socket errors:\s*connect (\d+), read (\d+), write (\d+), timeout (\d+)",
            line
        )

        if em and current_queue is not None:
            connect, read, write, timeout = map(int, em.groups())
            total_errors = connect + read + write + timeout

            # safety (ha valamiért nincs request adat)
            if current_requests is None or current_requests == 0:
                failure_rate = 0
            else:
                failure_rate = (total_errors / current_requests) * 100

            data[current_queue].append((current_conn, failure_rate))

# ------------------------
# 📈 PLOTTOLÁS (queue size-onként külön)
# ------------------------
for queue, values in data.items():
    values.sort(key=lambda x: x[0])

    cons = [v[0] for v in values]
    failure_rates = [v[1] for v in values]

    plt.figure()
    plt.plot(cons, failure_rates)
    plt.xlabel("Connections")
    plt.ylabel("Failed requests (%)")
    plt.title(f"Queue size = {queue}")
    plt.grid()

    plt.savefig(f"plot_queue_{queue}_failure_rate.png")

plt.show()
