#include <iostream>
#include <csignal>
#include <thread>
#include <netinet/in.h>
#include <cstring>
#include "worker.h"
#include "thread_pool.h"
#include <curl/curl.h>

const int PORT = 8080;
const int MAX_THREADS = 512;
static int server_fd;

void sighandler(int signal) {
    std::cout << "cppserver: received signal " << signal << std::endl;
    if (signal == SIGINT) {
        std::cout << "cppserver: shutting down server..." << std::endl;
        close(server_fd);
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
    int new_socket;
    sockaddr_in address{};
    int addrlen = sizeof(address);
    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd == 0) {
        perror("socket failed");
        return 1;
    }
    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        perror("setsockopt");
        return 1;
    }
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(PORT);

    if (bind(server_fd, (sockaddr*)&address, sizeof(address)) < 0) {
        perror("bind failed");
        return 1;
    }

    if (listen(server_fd, 3) < 0) {
        return 1;
    }

    std::cout << "Listening on port: " << PORT << "...\n";

    ThreadPool pool(MAX_THREADS);
    pool.start();


    while (true)
    {
        new_socket = accept(server_fd, (sockaddr*)&address, (socklen_t*)&addrlen);
        if (new_socket < 0) {
            perror("accept");
            continue;
        }
        pool.enqueue(new_socket, address);
    }
    
    return 0;
}
