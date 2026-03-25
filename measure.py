#!/usr/bin/python3

import subprocess
import time
from datetime import datetime

# Measurement config
t = 10  # seconds
cons = [300, 350, 400, 450, 500]
threads = [4]
queues = [256, 1024, 2048]

ADDR = "http://127.0.0.1:1234"

filename = f"wrk_results_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

with open(filename, "w") as f:
    f.write("=== WRK MEASUREMENT LOG ===\n\n")

    for queue_size in queues:
        print(f"\n=== Starting server with max-queue={queue_size} ===")

        # server indítása
        server_cmd = ["build/src/cppserver", "--cpu", "--max-queue", str(queue_size)]
        server = subprocess.Popen(server_cmd)

        # várunk kicsit hogy felálljon
        time.sleep(2)

        f.write(f"\n\n###############################\n")
        f.write(f"### max-queue = {queue_size}\n")
        f.write(f"###############################\n\n")
        f.flush()

        for thread_num in threads:
            for con_num in cons:
                command = f"wrk -c{con_num} -d{t}s -t{thread_num} {ADDR}"

                print(f"Running: {command}")
                result = subprocess.run(command, shell=True, capture_output=True, text=True)

                log_entry = f"""
=== max-queue={queue_size}, threads={thread_num}, connections={con_num} ===
COMMAND: {command}

STDOUT:
{result.stdout}

STDERR:
{result.stderr}

----------------------------------------
"""
                f.write(log_entry)
                f.flush()

        # server leállítása
        print(f"Stopping server (queue={queue_size})...")
        server.terminate()

        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Force killing server...")
            server.kill()
            server.wait()

print(f"\nDone. Results saved to {filename}")
