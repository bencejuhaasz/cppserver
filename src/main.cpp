#include <iostream>
#include <csignal>
#include <thread>
#include <netinet/in.h>
#include <cstring>

const int PORT = 8080;
const int MAX_THREADS = 512;
std::thread threadList[MAX_THREADS];
static int server_fd;

void sighandler(int signal) {
    std::cout << "cppserver: received signal " << signal << std::endl;
}

void handle_request(int socket, sockaddr_in address, int thread_index) {
    std::cout << "Handling request in thread index: " << thread_index << std::endl;
    // Placeholder for request handling logic
    // For example, read from the socket, process the request, and send a response

    //reply hello
    const char* response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 13\r\n\r\nHello, World!";
    send(socket, response, strlen(response), 0);
    close(socket);
    std::cout << "Finished handling request in thread index: " << thread_index << std::endl;
}

int main() {
    std::cout << "cppserver: starting server..." << std::endl;
    std::signal(SIGINT, sighandler);
    //std::thread input_thread(input_thread_func); #start new thread for handling user input
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


    while (true)
    {
        new_socket = accept(server_fd, (sockaddr*)&address, (socklen_t*)&addrlen);
        if (new_socket < 0) {
            perror("accept");
            continue;
        }
        bool assigned = false;
        for (int i = 0; i < MAX_THREADS; i++) {
            if (!threadList[i].joinable()) {
                threadList[i] = std::thread(handle_request, new_socket, address, i);
                assigned = true;
                std::cout << "Offloading to index [" << i << "] in the thread pool\n"; 
                break;
            }
        }
        if (!assigned) {
            close(new_socket);
            std::cout << "Thread pool is full, cannot handle new request\n";
        }
    }
    
    return 0;
}
