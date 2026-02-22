#pragma once

#include <string>
#include <vector>
#include <ctime>
#include <cstddef>

class Clients {
    private:
    struct ClientInfo {
        std::string ip_addr;
        int port;
        size_t lastConnected[25];
        int connections;
        int infractions;
        time_t bannedUntil;
        time_t firstInf;
    };
    std::vector<ClientInfo> clients;
    public:
    void addClient(std::string ip_addr, int port);
    void removeClient(std::string ip_addr, int port);
    void updateClient(std::string ip_addr, int port);
    bool isBanned(std::string ip_addr, int port);
    void banClient(std::string ip_addr, int port, time_t durationSeconds);
    int searchClient(const std::string &ip_addr, int port) const;
};