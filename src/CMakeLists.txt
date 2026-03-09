add_executable(cppserver main.cpp worker.cpp cpu_worker.cpp io_worker.cpp thread_pool.cpp)

target_compile_features(cppserver PRIVATE cxx_std_20)
target_include_directories(cppserver PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

find_package(CURL REQUIRED)
find_package(Threads REQUIRED)
find_package(Boost REQUIRED COMPONENTS system)
target_link_libraries(cppserver PRIVATE CURL::libcurl Threads::Threads Boost::system)

install(TARGETS cppserver RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
