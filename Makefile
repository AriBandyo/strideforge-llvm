LLVM_VERSION ?= 18
LLVM_DIR ?= /usr/lib/llvm-$(LLVM_VERSION)/lib/cmake/llvm
OPT ?= /usr/lib/llvm-$(LLVM_VERSION)/bin/opt
CLANG ?= clang-$(LLVM_VERSION)
PLUGIN = $(shell find build -name '*StrideForge*.so' -o -name '*StrideForge*.dylib' 2>/dev/null | head -1)

.PHONY: build test benchmark clean
build:
	cmake -S . -B build -G Ninja -DLLVM_DIR=$(LLVM_DIR) -DCMAKE_BUILD_TYPE=Release
	cmake --build build

test: build
	python3 tools/test_ir.py --opt $(OPT) --clang $(CLANG) --plugin $(PLUGIN)

benchmark: build
	python3 tools/benchmark.py --opt $(OPT) --clang $(CLANG) --plugin $(PLUGIN) --json results/bench.json

clean:
	rm -rf build results
