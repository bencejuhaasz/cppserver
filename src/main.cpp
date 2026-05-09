#include <iostream>
#include <csignal>
#include <thread>
#include <cstring>
#include <boost/asio.hpp>
#include <curl/curl.h>
#include "worker.h"
#include "cpu_worker.h"
#include "io_worker.h"
#include "thread_pool.h"

const int PORT = 1234;
const int DEFAULT_MAX_THREADS = 4;
const size_t DEFAULT_MAX_QUEUE = 1024;

// ÚJ: default upstream URL
const std::string DEFAULT_UPSTREAM_URL = "https://time.now/developer/api/timezone/Europe/London";

static boost::asio::io_context* io_context_ptr = nullptr;

enum class WorkerType {
    DEFAULT_WORKER,
    IO_WORKER,
    CPU_WORKER
};

void sighandler(int signal) {
    std::cout << "cppserver: received signal " << signal << std::endl;
    if (signal == SIGINT) {
        std::cout << "cppserver: shutting down server..." << std::endl;
        if (io_context_ptr) {
            io_context_ptr->stop();
        }
        exit(0);
    }
}


void printUsage(const char* program) {
    std::cout << "Usage: " << program << " [--cpu | --io-heavy] [--max-queue N] [--max-threads N] [--upstream URL]\n";
    std::cout << "  --cpu            Use CPU-intensive worker\n";
    std::cout << "  --io-heavy       Use IO-intensive test worker\n";
    std::cout << "  --max-queue N    Set maximum queued connections per thread pool (default " << DEFAULT_MAX_QUEUE << ")\n";
    std::cout << "  --max-threads N  Set worker thread pool size (default " << DEFAULT_MAX_THREADS << ")\n";
    std::cout << "  --upstream URL   Set upstream URL for default network proxy worker\n";
    std::cout << "                   (default: " << DEFAULT_UPSTREAM_URL << ")\n";
    std::cout << "  default          Use existing network worker\n";
}

int main(int argc, char* argv[]) {
    WorkerType worker_type = WorkerType::DEFAULT_WORKER;
    size_t max_queue = DEFAULT_MAX_QUEUE;
    int max_threads = DEFAULT_MAX_THREADS;
    std::string upstream_url = DEFAULT_UPSTREAM_URL;  // ÚJ

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--cpu") {
            worker_type = WorkerType::CPU_WORKER;
        } else if (arg == "--max-queue") {
            if (i + 1 >= argc) {
                std::cerr << "Error: --max-queue requires a numeric argument\n";
                printUsage(argv[0]);
                return 1;
            }
            std::string val = argv[++i];
            try {
                max_queue = std::stoul(val);
            } catch (const std::exception& e) {
                std::cerr << "Error: invalid number for --max-queue: " << val << "\n";
                return 1;
            }
        } else if (arg == "--max-threads") {
            if (i + 1 >= argc) {
                std::cerr << "Error: --max-threads requires a numeric argument\n";
                printUsage(argv[0]);
                return 1;
            }
            std::string val = argv[++i];
            try {
                int parsed = std::stoi(val);
                if (parsed <= 0) {
                    std::cerr << "Error: --max-threads must be positive: " << val << "\n";
                    return 1;
                }
                max_threads = parsed;
            } catch (const std::exception& e) {
                std::cerr << "Error: invalid number for --max-threads: " << val << "\n";
                return 1;
            }
        } else if (arg == "--upstream") {  // ÚJ blokk
            if (i + 1 >= argc) {
                std::cerr << "Error: --upstream requires a URL argument\n";
                printUsage(argv[0]);
                return 1;
            }
            upstream_url = argv[++i];
        } else if (arg == "--io-heavy") {
            worker_type = WorkerType::IO_WORKER;
        } else if (arg == "--help" || arg == "-h") {
            printUsage(argv[0]);
            return 0;
        } else {
            // support --max-queue=NN form
            const std::string queue_prefix = "--max-queue=";
            if (arg.rfind(queue_prefix, 0) == 0) {
                std::string val = arg.substr(queue_prefix.size());
                try {
                    max_queue = std::stoul(val);
                    continue;
                } catch (const std::exception& e) {
                    std::cerr << "Error: invalid number for --max-queue: " << val << "\n";
                    return 1;
                }
            }
            // support --max-threads=NN form
            const std::string threads_prefix = "--max-threads=";
            if (arg.rfind(threads_prefix, 0) == 0) {
                std::string val = arg.substr(threads_prefix.size());
                try {
                    int parsed = std::stoi(val);
                    if (parsed <= 0) {
                        std::cerr << "Error: --max-threads must be positive: " << val << "\n";
                        return 1;
                    }
                    max_threads = parsed;
                    continue;
                } catch (const std::exception& e) {
                    std::cerr << "Error: invalid number for --max-threads: " << val << "\n";
                    return 1;
                }
            }
            // support --upstream=URL form (ÚJ)
            const std::string upstream_prefix = "--upstream=";
            if (arg.rfind(upstream_prefix, 0) == 0) {
                upstream_url = arg.substr(upstream_prefix.size());
                continue;
            }
            std::cerr << "Unknown option: " << arg << std::endl;
            printUsage(argv[0]);
            return 1;
        }
    }

    const char* worker_type_name = "default";
    if (worker_type == WorkerType::CPU_WORKER) {
        worker_type_name = "cpu";
    } else if (worker_type == WorkerType::IO_WORKER) {
        worker_type_name = "io-heavy";
    }
    std::cout << "cppserver: starting server with " << worker_type_name
              << " worker, threads=" << max_threads
              << ", max_queue=" << max_queue;
    if (worker_type == WorkerType::DEFAULT_WORKER) {
        std::cout << ", upstream=" << upstream_url;  // ÚJ
    }
    std::cout << std::endl;

    std::signal(SIGINT, sighandler);
    if (curl_global_init(CURL_GLOBAL_ALL) != 0) {
        std::cerr << "cppserver: curl_global_init failed" << std::endl;
        return 1;
    }
    atexit(curl_global_cleanup);

    try {
        boost::asio::io_context io_context;
        io_context_ptr = &io_context;

        boost::asio::ip::tcp::acceptor acceptor(
            io_context,
            boost::asio::ip::tcp::endpoint(boost::asio::ip::tcp::v4(), PORT)
        );

        acceptor.set_option(boost::asio::socket_base::reuse_address(true));

        std::cout << "Listening on port: " << PORT << "...\n";

        // MÓDOSÍTVA: a factory most kapja az upstream_url-t és átadja a Workernek
        ThreadPool pool(max_threads, [worker_type, upstream_url](int id) -> std::unique_ptr<WorkerBase> {
            if (worker_type == WorkerType::CPU_WORKER) {
                return std::make_unique<CpuWorker>(id);
            } else if (worker_type == WorkerType::IO_WORKER) {
                return std::make_unique<IoWorker>(id);
            } else {
                return std::make_unique<Worker>(id, upstream_url);
            }
        }, max_queue);
        pool.start();

        while (true) {
            auto socket = std::make_unique<boost::asio::ip::tcp::socket>(io_context);
            boost::system::error_code ec;
            acceptor.accept(*socket, ec);

            if (ec) {
                std::cerr << "accept error: " << ec.message() << std::endl;
                continue;
            }

            pool.enqueue(std::move(socket));
        }
    } catch (std::exception& e) {
        std::cerr << "Exception: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}