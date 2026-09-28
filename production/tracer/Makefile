# THE LAST SIGNAL tracer. `make` builds build/tracer (native CPU tuning, OpenMP).
CXX ?= g++
ARCH ?= -march=native
CXXFLAGS ?= -Ithird_party -O3 $(ARCH) -std=c++17 -fopenmp -ffp-contract=fast -Wall -Wno-unused-function
BUILD := build

all: $(BUILD)/tracer

$(BUILD)/miniz.o: third_party/miniz.c third_party/miniz.h
	@mkdir -p $(BUILD)
	$(CC) -O2 -c $< -o $@

$(BUILD)/tracer: src/render.cpp src/*.h $(BUILD)/miniz.o
	@mkdir -p $(BUILD)
	$(CXX) $(CXXFLAGS) src/render.cpp $(BUILD)/miniz.o -o $@

test: tests/test_kerr.cpp src/kerr.h
	@mkdir -p $(BUILD)
	$(CXX) -O2 -std=c++17 tests/test_kerr.cpp -o $(BUILD)/test_kerr && $(BUILD)/test_kerr

clean:
	rm -rf $(BUILD)
.PHONY: all test clean
