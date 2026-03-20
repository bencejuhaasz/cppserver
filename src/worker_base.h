#pragma once

#include <boost/asio/ip/tcp.hpp>
#include <boost/asio/read_until.hpp>
#include <boost/asio/streambuf.hpp>
#include <boost/system/error_code.hpp>
#include <memory>

class WorkerBase {
public:
    explicit WorkerBase(int id) : id(id) {}
    virtual ~WorkerBase() = default;
    
    int getId() const { return id; }
    virtual void handleRequest(std::unique_ptr<boost::asio::ip::tcp::socket> socket, int thread_index) = 0;

protected:
    bool readRequestHeader(boost::asio::ip::tcp::socket& socket) {
        boost::asio::streambuf request_buffer;
        boost::system::error_code ec;
        boost::asio::read_until(socket, request_buffer, "\r\n\r\n", ec);

        if (ec == boost::asio::error::eof) {
            return false;
        }

        return !ec;
    }

    int id;
};
