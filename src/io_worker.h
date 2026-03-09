#pragma once

#include "worker_base.h"
#include <boost/asio/ip/tcp.hpp>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>

class IoWorker : public WorkerBase {
public:
    explicit IoWorker(int id);
    void handleRequest(std::unique_ptr<boost::asio::ip::tcp::socket> socket, int thread_index) override;

private:
    struct IoStats {
        std::size_t bytes_written;
        std::size_t bytes_read;
        std::uint64_t checksum;
    };

    IoStats runDiskIoWorkload(int thread_index, int rounds, std::size_t chunk_size);
    std::string buildPayload(int id, int thread_index, const IoStats& stats, long long elapsed_ms) const;
};
