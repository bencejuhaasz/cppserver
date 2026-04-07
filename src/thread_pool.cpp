#include "thread_pool.h"
#include <iostream>
#include <pthread.h>
#include <sched.h>
#include <unistd.h>
#include <thread>

ThreadPool::ThreadPool(size_t numThreads, WorkerFactory factory, size_t maxQueue)
    : stopping(false), numThreads(numThreads), workerFactory(std::move(factory)), maxQueue(maxQueue) {}

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
        int rc = sched_setaffinity(workers.back().native_handle(), sizeof(cpu_set_t), &cpuset);
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

void ThreadPool::enqueue(std::unique_ptr<boost::asio::ip::tcp::socket> socket) {
    {
        std::unique_lock<std::mutex> lock(mtx);
        if (tasks.size() >= maxQueue) {
            // Drop the connection to avoid unbounded memory growth.
            boost::system::error_code ec;
            try {
                socket->shutdown(boost::asio::ip::tcp::socket::shutdown_both, ec);
            } catch (...) {}
            socket->close(ec);
            std::cerr << "ThreadPool: queue full (" << maxQueue << "), dropped connection\n";
            return;
        }
        tasks.push(Task{std::move(socket)});
    }
    cv.notify_one();
}

void ThreadPool::workerLoop(int id) {
    auto worker = workerFactory(id);
    for (;;) {
        Task task;
        {
            std::unique_lock<std::mutex> lock(mtx);
            cv.wait(lock, [this]() { return stopping || !tasks.empty(); });
            if (stopping && tasks.empty()) break;
            task = std::move(tasks.front());
            tasks.pop();
        }
        worker->handleRequest(std::move(task.socket), id);
    }
}
