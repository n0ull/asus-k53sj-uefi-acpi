.PHONY: all build test vm-test
BUILD_DIR ?= $(CURDIR)/build
export BUILD_DIR

all: build

build:
	bash scripts/build.sh

test:
	bash scripts/test-host.sh

vm-test: build
	python3 tests/test_uefi.py --build-dir "$(BUILD_DIR)"
