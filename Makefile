# Makefile for cross-compiling the Go project

# Binary name
BINARY_NAME=bs

# Source file
SRC=main.go

# Default target: build for the current OS
.PHONY: all
all: build

# Build for current OS
.PHONY: build
build:
	go build -o $(BINARY_NAME) $(SRC)

# Cross-compile for Linux (amd64)
.PHONY: linux
linux:
	GOOS=linux GOARCH=amd64 go build -o $(BINARY_NAME)-linux-amd64 $(SRC)

# Cross-compile for Windows (amd64)
.PHONY: windows
windows:
	GOOS=windows GOARCH=amd64 go build -o $(BINARY_NAME)-windows-amd64.exe $(SRC)

# Cross-compile for macOS (Darwin amd64 - Intel)
.PHONY: macos-intel
macos-intel:
	GOOS=darwin GOARCH=amd64 go build -o $(BINARY_NAME)-darwin-amd64 $(SRC)

# Cross-compile for macOS (Darwin arm64 - Apple Silicon)
.PHONY: macos-arm
macos-arm:
	GOOS=darwin GOARCH=arm64 go build -o $(BINARY_NAME)-darwin-arm64 $(SRC)

# Build for all supported platforms
.PHONY: release
release: linux windows macos-intel macos-arm

# Clean up build artifacts
.PHONY: clean
clean:
	rm -f $(BINARY_NAME)
	rm -f $(BINARY_NAME)-linux-amd64
	rm -f $(BINARY_NAME)-windows-amd64.exe
	rm -f $(BINARY_NAME)-darwin-amd64
	rm -f $(BINARY_NAME)-darwin-arm64
