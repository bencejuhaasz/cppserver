#pragma once

#include "worker_base.h"
#include <boost/asio/ip/tcp.hpp>
#include <memory>

class Worker : public WorkerBase {
public:
    explicit Worker(int id);
    void handleRequest(std::unique_ptr<boost::asio::ip::tcp::socket> socket, int thread_index) override;
};