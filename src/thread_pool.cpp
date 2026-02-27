#include "thread_pool.h"
#include <iostream>
#include <pthread.h>
#include <sched.h>
#include <unistd.h>
#include <thread>

ThreadPool::ThreadPool(size_t numThreads)
    : stopping(false), numThreads(numThreads) {}

ThreadPool::~ThreadPool() {
    stop();
}

void ThreadPool::start() {
    stopping = false;
    unsigned int ncores = std::thread::hardware_concurrency();
    if (ncores == 0) ncores = static_cast<unsigned int>(sysconf(_SC_NPROCESSORS_ONLN));
    if (ncores == 0) ncores = 1;

    for (size_t i = 0; i < numThreads; ++i) {
        workers.emplace_back([this, i]() { workerLoop(static_cast<int>(i)); });

        // Pin the newly-created thread to a specific CPU core in round-robin fashion
        cpu_set_t cpuset;
        CPU_ZERO(&cpuset);
        CPU_SET(static_cast<int>(i % ncores), &cpuset);
        int rc = pthread_setaffinity_np(workers.back().native_handle(), sizeof(cpu_set_t), &cpuset);
        if (rc != 0) {
            std::cerr << "ThreadPool: failed to set affinity for thread " << i << " rc=" << rc << std::endl;
        }
    }
}

void ThreadPool::stop() {
    {
        std::unique_lock<std::mutex> lock(mtx);
        stopping = true;
    }
    cv.notify_all();
    for (auto &t : workers) {
        if (t.joinable()) t.join();
    }
    workers.clear();
}

void ThreadPool::enqueue(int socket, sockaddr_in address) {
    {
        std::unique_lock<std::mutex> lock(mtx);
        tasks.push(Task{socket, address});
    }
    cv.notify_one();
}

void ThreadPool::workerLoop(int id) {
    Worker w(id);
    for (;;) {
        Task task;
        {
            std::unique_lock<std::mutex> lock(mtx);
            cv.wait(lock, [this]() { return stopping || !tasks.empty(); });
            if (stopping && tasks.empty()) break;
            task = tasks.front();
            tasks.pop();
        }
        w.handleRequest(task.socket, task.address, id);
    }
}
