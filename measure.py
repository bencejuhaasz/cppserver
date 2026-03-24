#!/usr/bin/python3

import subprocess
from datetime import datetime

# Measurement config
t = 10 #s
#cons = [10, 25, 50, 100, 500, 1000]
# CPU 500 es 500 kozott szall el
#cons = [100, 200, 300, 400, 500]
# 300 es 500 kozott
cons = [300, 350, 400, 450, 500]
threads = [4, 8]

ADDR = "http://127.0.0.1:1234"

# log file neve timestamp-pel
filename = f"wrk_results_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

with open(filename, "w") as f:
    f.write("=== WRK MEASUREMENT LOG ===\n\n")

    for thread_num in threads:
        for con_num in cons:
            command = f"wrk -c{con_num} -d{t}s -t{thread_num} {ADDR}"
            
            print(f"Running: {command}")
            result = subprocess.run(command, shell=True, capture_output=True, text=True)

            # szépen formázott log entry
            log_entry = f"""
=== threads={thread_num}, connections={con_num} ===
COMMAND: {command}

STDOUT:
{result.stdout}

STDERR:
{result.stderr}

----------------------------------------
"""
            f.write(log_entry)
            f.flush()  # azonnal kiírja diskre (nagyon hasznos!)

print(f"Done. Results saved to {filename}")
