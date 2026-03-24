#!/usr/bin/python3

import subprocess

# Measurement config
t = 10 #s
cons = [10, 25, 50, 100, 500, 1000]

ADDR="http://127.0.0.1:1234"

threads = [4, 8]

results = []

for thread_num in threads:
	for con_num in cons:
		command=f"wrk -c{con_num} -d{t}s -t{thread_num} {ADDR}"
		result = subprocess.run(command, shell=True, capture_output=True, text=True)
		results.append(f"stdout: {result.stdout} stderr: {result.stderr}")


print("================= DONE ==================")
for result in results:
	print(result)
             
