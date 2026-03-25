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

with open(log_path, "r") as f:
    for line in f:
        line = line.strip()

        # fejléc parsing
        m = re.match(r"=== max-queue=(\d+), threads=\d+, connections=(\d+) ===", line)
        if m:
            current_queue = int(m.group(1))
            current_conn = int(m.group(2))

        # socket errors parsing
        if "Socket errors:" in line:
            tm = re.search(r"timeout (\d+)", line)
            if tm and current_queue is not None:
                timeout = int(tm.group(1))
                data[current_queue].append((current_conn, timeout))

# plotolás
for queue, values in data.items():
    values.sort()

    cons = [v[0] for v in values]
    timeouts = [v[1] for v in values]

    plt.figure()
    plt.plot(cons, timeouts)
    plt.xlabel("Connections")
    plt.ylabel("Failed requests (timeouts)")
    plt.title(f"Queue size = {queue}")
    plt.grid()

    # fájlba mentés (nagyon hasznos később)
    plt.savefig(f"plot_queue_{queue}.png")

plt.show()
