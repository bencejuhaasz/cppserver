#pragma once

#include <boost/asio/ip/tcp.hpp>
#include <memory>

class WorkerBase {
public:
    explicit WorkerBase(int id) : id(id) {}
    virtual ~WorkerBase() = default;
    
    int getId() const { return id; }
    virtual void handleRequest(std::unique_ptr<boost::asio::ip::tcp::socket> socket, int thread_index) = 0;

protected:
    int id;
};
