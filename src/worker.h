#pragma once

#include <netinet/in.h>

class Worker {
public:
    explicit Worker(int id);
    int getId() const;
    void handleRequest(int socket, sockaddr_in address, int thread_index);
private:
    int id;
};