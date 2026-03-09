#include "cpu_worker.h"
#include <iostream>
#include <chrono>
#include <cmath>
#include <vector>
#include <random>
#include <sstream>
#include <iomanip>
#include <boost/asio/write.hpp>
#include <boost/system/error_code.hpp>

CpuWorker::CpuWorker(int id) : WorkerBase(id) {}

void CpuWorker::handleRequest(std::unique_ptr<boost::asio::ip::tcp::socket> socket, int thread_index) {
	std::cout << "Handling CPU-intensive request in worker id: " << id << " thread index: " << thread_index << std::endl;

	auto start = std::chrono::high_resolution_clock::now();

	// Perform CPU-intensive computations
	double matrix_result = performMatrixMultiplication(100);
	uint64_t prime_count = computePrimes(50000);
	double pi_approx = computePi(1000000);

	auto end = std::chrono::high_resolution_clock::now();
	auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

	// Build JSON response with computation results
	std::ostringstream json;
	json << std::fixed << std::setprecision(6);
	json << "{\n";
	json << "  \"worker_id\": " << id << ",\n";
	json << "  \"thread_index\": " << thread_index << ",\n";
	json << "  \"computation_time_ms\": " << duration << ",\n";
	json << "  \"results\": {\n";
	json << "    \"matrix_multiplication_sum\": " << matrix_result << ",\n";
	json << "    \"primes_under_50000\": " << prime_count << ",\n";
	json << "    \"pi_approximation\": " << pi_approx << "\n";
	json << "  }\n";
	json << "}";

	std::string response_body = json.str();
	std::string header = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ";
	header += std::to_string(response_body.size());
	header += "\r\n\r\n";
	std::string response = header + response_body;

	// Send the response using Boost.Asio
	boost::system::error_code ec;
	boost::asio::write(*socket, boost::asio::buffer(response), ec);
	if (ec) {
		std::cerr << "CpuWorker " << id << " failed to send response: " << ec.message() << std::endl;
	}
    
	socket->close(ec);
	if (ec) {
		std::cerr << "CpuWorker " << id << " error closing socket: " << ec.message() << std::endl;
	}

	std::cout << "Finished handling CPU request in worker id: " << id << " thread index: " << thread_index 
			  << " (took " << duration << "ms)" << std::endl;
}

double CpuWorker::performMatrixMultiplication(int size) {
	// Create two random matrices and multiply them
	std::vector<std::vector<double>> A(size, std::vector<double>(size));
	std::vector<std::vector<double>> B(size, std::vector<double>(size));
	std::vector<std::vector<double>> C(size, std::vector<double>(size, 0.0));

	std::random_device rd;
	std::mt19937 gen(rd());
	std::uniform_real_distribution<> dis(0.0, 1.0);

	// Fill matrices with random values
	for (int i = 0; i < size; ++i) {
		for (int j = 0; j < size; ++j) {
			A[i][j] = dis(gen);
			B[i][j] = dis(gen);
		}
	}

	// Matrix multiplication
	for (int i = 0; i < size; ++i) {
		for (int j = 0; j < size; ++j) {
			for (int k = 0; k < size; ++k) {
				C[i][j] += A[i][k] * B[k][j];
			}
		}
	}

	// Return sum of all elements as a verification
	double sum = 0.0;
	for (int i = 0; i < size; ++i) {
		for (int j = 0; j < size; ++j) {
			sum += C[i][j];
		}
	}
	return sum;
}

bool CpuWorker::isPrime(uint64_t n) {
	if (n <= 1) return false;
	if (n <= 3) return true;
	if (n % 2 == 0 || n % 3 == 0) return false;
    
	for (uint64_t i = 5; i * i <= n; i += 6) {
		if (n % i == 0 || n % (i + 2) == 0)
			return false;
	}
	return true;
}

uint64_t CpuWorker::computePrimes(uint64_t limit) {
	// Count prime numbers up to limit using trial division
	uint64_t count = 0;
	for (uint64_t i = 2; i <= limit; ++i) {
		if (isPrime(i)) {
			++count;
		}
	}
	return count;
}

double CpuWorker::computePi(int iterations) {
	// Monte Carlo method to approximate Pi
	std::random_device rd;
	std::mt19937 gen(rd());
	std::uniform_real_distribution<> dis(0.0, 1.0);

	int inside_circle = 0;
	for (int i = 0; i < iterations; ++i) {
		double x = dis(gen);
		double y = dis(gen);
		if (x * x + y * y <= 1.0) {
			++inside_circle;
		}
	}

	return 4.0 * inside_circle / iterations;
}
