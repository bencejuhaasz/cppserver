#pragma once

#include "worker_base.h"
#include <boost/asio/ip/tcp.hpp>
#include <memory>

class CpuWorker : public WorkerBase {
public:
	explicit CpuWorker(int id);
	void handleRequest(std::unique_ptr<boost::asio::ip::tcp::socket> socket, int thread_index) override;

private:
	// CPU-intensive operations
	double performMatrixMultiplication(int size);
	bool isPrime(uint64_t n);
	uint64_t computePrimes(uint64_t limit);
	double computePi(int iterations);
};
