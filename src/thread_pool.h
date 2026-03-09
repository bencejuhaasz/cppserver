#pragma once

#include <boost/asio/ip/tcp.hpp>
#include <thread>
#include <vector>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <memory>
#include "worker.h"

class ThreadPool {
public:
    explicit ThreadPool(size_t numThreads);
    ~ThreadPool();

    void start();
    void stop();
    void enqueue(std::unique_ptr<boost::asio::ip::tcp::socket> socket);

private:
    struct Task { std::unique_ptr<boost::asio::ip::tcp::socket> socket; };

    void workerLoop(int id);

    std::vector<std::thread> workers;
    std::queue<Task> tasks;
    std::mutex mtx;
    std::condition_variable cv;
    bool stopping;
    size_t numThreads;
};
