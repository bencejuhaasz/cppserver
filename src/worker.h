#pragma once

#include <boost/asio/ip/tcp.hpp>
#include <memory>

class Worker {
public:
    explicit Worker(int id);
    int getId() const;
    void handleRequest(std::unique_ptr<boost::asio::ip::tcp::socket> socket, int thread_index);
private:
    int id;
};