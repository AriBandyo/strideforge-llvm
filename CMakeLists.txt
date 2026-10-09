cmake_minimum_required(VERSION 3.20)
project(StrideForge LANGUAGES CXX)

# Build with the LLVM dev package matching the `opt` executable used to load
# the resulting plugin. Mixing LLVM major versions is not supported.
enable_language(C)
find_package(LLVM REQUIRED CONFIG)
message(STATUS "Found LLVM ${LLVM_PACKAGE_VERSION} at ${LLVM_DIR}")

if(LLVM_VERSION_MAJOR LESS 18 OR LLVM_VERSION_MAJOR GREATER 21)
  message(FATAL_ERROR "StrideForge currently targets LLVM 18-21; found ${LLVM_PACKAGE_VERSION}")
endif()

list(APPEND CMAKE_MODULE_PATH "${LLVM_CMAKE_DIR}")
include(AddLLVM)
include(HandleLLVMOptions)

add_llvm_pass_plugin(StrideForge src/StrideForge.cpp)
target_compile_features(StrideForge PRIVATE cxx_std_17)
target_include_directories(StrideForge PRIVATE ${LLVM_INCLUDE_DIRS})

# Plugin entrypoint registration is performed in StrideForge.cpp.
