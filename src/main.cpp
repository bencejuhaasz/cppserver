#include <iostream>
#include <csignal>
#include <thread>
#include <cstring>
#include <boost/asio.hpp>
#include <curl/curl.h>
#include "worker.h"
#include "thread_pool.h"

const int PORT = 1234;
const int MAX_THREADS = 4;
static boost::asio::io_context* io_context_ptr = nullptr;

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


int main() {
    std::cout << "cppserver: starting server..." << std::endl;
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
        
        // Set SO_REUSEADDR option
        acceptor.set_option(boost::asio::socket_base::reuse_address(true));
        
        std::cout << "Listening on port: " << PORT << "...\n";

        ThreadPool pool(MAX_THREADS);
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
