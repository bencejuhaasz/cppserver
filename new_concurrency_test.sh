#!/bin/bash

TYPE=cpu

build/src/cppserver --$TYPE &
SERVER_PID=$!

wrk -t8 -c128 -d60s http://127.0.0.1:1234 > wrk-$TYPE-$(date "+%Y-%m-%d_%H-%M-%S").log

kill $SERVER_PID
