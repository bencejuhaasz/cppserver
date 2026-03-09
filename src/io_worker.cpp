#include "io_worker.h"

#include <boost/asio/write.hpp>
#include <boost/system/error_code.hpp>

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

IoWorker::IoWorker(int id) : WorkerBase(id) {}

void IoWorker::handleRequest(std::unique_ptr<boost::asio::ip::tcp::socket> socket, int thread_index) {
    std::cout << "Handling IO-intensive request in worker id: " << id
              << " thread index: " << thread_index << std::endl;

    auto start = std::chrono::steady_clock::now();
    IoStats stats = runDiskIoWorkload(thread_index, 200, 4096);
    auto end = std::chrono::steady_clock::now();
    long long elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

    std::string body = buildPayload(id, thread_index, stats, elapsed_ms);
    std::string header = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ";
    header += std::to_string(body.size());
    header += "\r\n\r\n";
    std::string response = header + body;

    boost::system::error_code ec;
    boost::asio::write(*socket, boost::asio::buffer(response), ec);
    if (ec) {
        std::cerr << "IoWorker " << id << " failed to send response: " << ec.message() << std::endl;
    }

    socket->close(ec);
    if (ec) {
        std::cerr << "IoWorker " << id << " failed to close socket: " << ec.message() << std::endl;
    }

    std::cout << "Finished IO-intensive request in worker id: " << id
              << " thread index: " << thread_index
              << " (took " << elapsed_ms << "ms)" << std::endl;
}

IoWorker::IoStats IoWorker::runDiskIoWorkload(int thread_index, int rounds, std::size_t chunk_size) {
    namespace fs = std::filesystem;

    fs::path temp_path = fs::temp_directory_path() /
        ("cppserver_io_worker_" + std::to_string(id) + "_" + std::to_string(thread_index) + ".dat");

    std::vector<char> chunk(chunk_size);
    for (std::size_t i = 0; i < chunk.size(); ++i) {
        chunk[i] = static_cast<char>((i + static_cast<std::size_t>(id) + static_cast<std::size_t>(thread_index)) % 251);
    }

    std::size_t bytes_written = 0;
    std::size_t bytes_read = 0;
    std::uint64_t checksum = 0;

    {
        std::ofstream out(temp_path, std::ios::binary | std::ios::trunc);
        for (int i = 0; i < rounds; ++i) {
            out.write(chunk.data(), static_cast<std::streamsize>(chunk.size()));
            bytes_written += chunk.size();
        }
    }

    {
        std::ifstream in(temp_path, std::ios::binary);
        std::vector<char> read_buf(chunk_size);
        while (in) {
            in.read(read_buf.data(), static_cast<std::streamsize>(read_buf.size()));
            std::streamsize got = in.gcount();
            if (got <= 0) {
                break;
            }
            bytes_read += static_cast<std::size_t>(got);
            for (std::streamsize i = 0; i < got; ++i) {
                checksum += static_cast<unsigned char>(read_buf[static_cast<std::size_t>(i)]);
            }
        }
    }

    std::error_code remove_ec;
    fs::remove(temp_path, remove_ec);

    return IoStats{bytes_written, bytes_read, checksum};
}

std::string IoWorker::buildPayload(int id, int thread_index, const IoStats& stats, long long elapsed_ms) const {
    std::ostringstream json;
    json << "{\n";
    json << "  \"worker_id\": " << id << ",\n";
    json << "  \"thread_index\": " << thread_index << ",\n";
    json << "  \"workload\": \"io-heavy\",\n";
    json << "  \"elapsed_ms\": " << elapsed_ms << ",\n";
    json << "  \"disk\": {\n";
    json << "    \"bytes_written\": " << stats.bytes_written << ",\n";
    json << "    \"bytes_read\": " << stats.bytes_read << ",\n";
    json << "    \"checksum\": " << stats.checksum << "\n";
    json << "  }\n";
    json << "}";
    return json.str();
}
