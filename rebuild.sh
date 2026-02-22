#!/bin/bash
rm -r build
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -- -j
./build/src/cppserver