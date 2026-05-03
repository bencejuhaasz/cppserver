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
#include <fcntl.h>      // posix_fadvise
#include <unistd.h>     // fsync, close
#include <sys/stat.h>   // open

IoWorker::IoWorker(int id) : WorkerBase(id) {}

void IoWorker::handleRequest(std::unique_ptr<boost::asio::ip::tcp::socket> socket, int thread_index) {
    std::cout << "Handling IO-intensive request in worker id: " << id
              << " thread index: " << thread_index << std::endl;

    if (!readRequestHeader(*socket)) {
        boost::system::error_code close_ec;
        socket->close(close_ec);
        return;
    }

    auto start = std::chrono::steady_clock::now();
    IoStats stats = runDiskIoWorkload(thread_index, 2048, 4096);
    auto end = std::chrono::steady_clock::now();
    long long elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

    std::string body = buildPayload(id, thread_index, stats, elapsed_ms);
    std::string header = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: ";
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

    // FONTOS: NEM a /tmp-t használjuk, mert az tmpfs (RAM)!
    // /var/tmp általában valódi diszk-en van.
    fs::path temp_dir("/var/tmp");
    fs::path temp_path = temp_dir /
        ("cppserver_io_worker_" + std::to_string(id) + "_" + std::to_string(thread_index) + ".dat");

    std::vector<char> chunk(chunk_size);
    for (std::size_t i = 0; i < chunk.size(); ++i) {
        chunk[i] = static_cast<char>((i + static_cast<std::size_t>(id) + static_cast<std::size_t>(thread_index)) % 251);
    }

    std::size_t bytes_written = 0;
    std::size_t bytes_read = 0;
    std::uint64_t checksum = 0;

    // === ÍRÁSI FÁZIS — fsync-cel kényszerített disk flush ===
    {
        int fd = ::open(temp_path.c_str(),
                        O_WRONLY | O_CREAT | O_TRUNC,
                        S_IRUSR | S_IWUSR);
        if (fd < 0) {
            std::cerr << "IoWorker " << id << " failed to open temp file for writing: "
                      << temp_path << std::endl;
            return IoStats{0, 0, 0};
        }

        for (int i = 0; i < rounds; ++i) {
            ssize_t written = ::write(fd, chunk.data(), chunk.size());
            if (written < 0) {
                std::cerr << "IoWorker " << id << " write failed\n";
                break;
            }
            bytes_written += static_cast<std::size_t>(written);
        }

        // Kényszerített disk flush — itt blokkolódik valódi IO-ig
        if (::fsync(fd) != 0) {
            std::cerr << "IoWorker " << id << " fsync failed\n";
        }

        // Page cache eldobása — a következő olvasás biztosan diszkről jön
        ::posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED);

        ::close(fd);
    }

    // === OLVASÁSI FÁZIS — page cache megkerülésével ===
    {
        int fd = ::open(temp_path.c_str(), O_RDONLY);
        if (fd < 0) {
            std::cerr << "IoWorker " << id << " failed to open temp file for reading\n";
            return IoStats{bytes_written, 0, 0};
        }

        // Hint a kernelnek: ne cache-elje, kérjük a diszkről
        ::posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED);

        std::vector<char> read_buf(chunk_size);
        while (true) {
            ssize_t got = ::read(fd, read_buf.data(), read_buf.size());
            if (got <= 0) {
                break;
            }
            bytes_read += static_cast<std::size_t>(got);
            for (ssize_t i = 0; i < got; ++i) {
                checksum += static_cast<unsigned char>(read_buf[static_cast<std::size_t>(i)]);
            }
        }

        ::close(fd);
    }

    // Takarítás
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
