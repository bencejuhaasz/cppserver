#include "worker.h"
#include <iostream>
#include <cstring>
#include <unistd.h>

Worker::Worker(int id) : id(id) {}

int Worker::getId() const {
    return id;
}

void Worker::handleRequest(int socket, sockaddr_in address, int thread_index) {
    std::cout << "Handling request in worker id: " << id << " thread index: " << thread_index << std::endl;

    const char* response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 13\r\n\r\nHello, World!";
    send(socket, response, strlen(response), 0);
    close(socket);

    std::cout << "Finished handling request in worker id: " << id << " thread index: " << thread_index << std::endl;
}
