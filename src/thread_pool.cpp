#include "thread_pool.h"
#include <iostream>

ThreadPool::ThreadPool(size_t numThreads)
    : stopping(false), numThreads(numThreads) {}

ThreadPool::~ThreadPool() {
    stop();
}

void ThreadPool::start() {
    stopping = false;
    for (size_t i = 0; i < numThreads; ++i) {
        workers.emplace_back([this, i]() { workerLoop(static_cast<int>(i)); });
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
