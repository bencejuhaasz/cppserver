#pragma once

#include <netinet/in.h>
#include <thread>
#include <vector>
#include <queue>
#include <mutex>
#include <condition_variable>
#include "worker.h"

class ThreadPool {
public:
    explicit ThreadPool(size_t numThreads);
    ~ThreadPool();

    void start();
    void stop();
    void enqueue(int socket, sockaddr_in address);

private:
    struct Task { int socket; sockaddr_in address; };

    void workerLoop(int id);

    std::vector<std::thread> workers;
    std::queue<Task> tasks;
    std::mutex mtx;
    std::condition_variable cv;
    bool stopping;
    size_t numThreads;
};
