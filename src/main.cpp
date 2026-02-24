#include <iostream>
#include <csignal>
#include <thread>
#include <netinet/in.h>

const int PORT = 8080;

void sighandler(int signal) {
    std::cout << "cppserver: received signal " << signal << std::endl;
}

int main() {
    std::cout << "cppserver: starting server..." << std::endl;
    std::signal(SIGINT, sighandler);
    //std::thread input_thread(input_thread_func); #start new thread for handling user input
    int new_socket;
    sockaddr_in address{};
    int addrlen = sizeof(address);
    while (true)
    {
        int place_holder = 0;
    }
    
    return 0;
}
