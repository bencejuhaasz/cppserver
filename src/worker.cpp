#include "worker.h"
#include <iostream>
#include <cstring>
#include <curl/curl.h>
#include <boost/asio/write.hpp>
#include <boost/system/error_code.hpp>

static size_t WriteCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    size_t total = size * nmemb;
    std::string* str = static_cast<std::string*>(userp);
    str->append(static_cast<char*>(contents), total);
    return total;
}

Worker::Worker(int id) : WorkerBase(id) {}

void Worker::handleRequest(std::unique_ptr<boost::asio::ip::tcp::socket> socket, int thread_index) {
    std::cout << "Handling request in worker id: " << id << " thread index: " << thread_index << std::endl;

    if (!readRequestHeader(*socket)) {
        boost::system::error_code close_ec;
        socket->close(close_ec);
        return;
    }

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
    std::string header = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: ";
    header += std::to_string(response_body.size());
    header += "\r\n\r\n";
    std::string response = header + response_body;

    // Send the response using Boost.Asio and close the socket
    boost::system::error_code ec;
    boost::asio::write(*socket, boost::asio::buffer(response), ec);
    if (ec) {
        std::cerr << "Worker " << id << " failed to send response: " << ec.message() << std::endl;
    }
    
    socket->close(ec);
    if (ec) {
        std::cerr << "Worker " << id << " error closing socket: " << ec.message() << std::endl;
    }

    std::cout << "Finished handling request in worker id: " << id << " thread index: " << thread_index << std::endl;
}
