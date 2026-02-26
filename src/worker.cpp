#include "worker.h"
#include <iostream>
#include <cstring>
#include <unistd.h>
#include <curl/curl.h>

static size_t WriteCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    size_t total = size * nmemb;
    std::string* str = static_cast<std::string*>(userp);
    str->append(static_cast<char*>(contents), total);
    return total;
}

Worker::Worker(int id) : id(id) {}

int Worker::getId() const {
    return id;
}

void Worker::handleRequest(int socket, sockaddr_in address, int thread_index) {
    std::cout << "Handling request in worker id: " << id << " thread index: " << thread_index << std::endl;

    // Build the API URL per client (example fixed timezone as requested)
    const char* api_url = "https://time.now/developer/api/timezone/Europe/London";

    std::string api_response;
    CURL* curl = curl_easy_init();
    if (curl) {
        curl_easy_setopt(curl, CURLOPT_URL, api_url);
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &api_response);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);
        CURLcode res = curl_easy_perform(curl);
        if (res != CURLE_OK) {
            std::cerr << "Worker " << id << " curl error: " << curl_easy_strerror(res) << std::endl;
        }
        curl_easy_cleanup(curl);
    } else {
        std::cerr << "Worker " << id << " failed to init curl" << std::endl;
    }

    // Prepare HTTP response for the client. Keep responses separate per-thread.
    std::string response_body = api_response.empty() ? std::string("{\"error\":\"upstream failed\"}") : api_response;
    std::string header = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ";
    header += std::to_string(response_body.size());
    header += "\r\n\r\n";
    std::string response = header + response_body;

    // Send the response and close the socket. Each worker thread handles its own socket only.
    ssize_t sent = send(socket, response.c_str(), response.size(), 0);
    if (sent < 0) {
        std::cerr << "Worker " << id << " failed to send response" << std::endl;
    }
    close(socket);

    std::cout << "Finished handling request in worker id: " << id << " thread index: " << thread_index << std::endl;
}
