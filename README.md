# cppserver

## Dependencies

### Ubuntu/Debian
```sh
sudo apt-get update
sudo apt-get install -y build-essential cmake libcurl4-openssl-dev libboost-all-dev
```

## Build and run

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -- -j
./build/src/cppserver
```
