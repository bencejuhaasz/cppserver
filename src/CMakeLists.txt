add_executable(cppserver main.cpp worker.cpp thread_pool.cpp)

target_compile_features(cppserver PRIVATE cxx_std_20)
target_include_directories(cppserver PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

find_package(Threads REQUIRED)
target_link_libraries(cppserver PRIVATE Threads::Threads)

install(TARGETS cppserver RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
