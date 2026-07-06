BINARY=m3u8-down
VERSION=$(shell git describe --tags 2>/dev/null || echo "dev")

all: build

build:
	go build -o $(BINARY) ./cmd/m3u8-down/

test:
	go test ./... -v

test-short:
	go test ./... -short

fmt:
	go fmt ./...

vet:
	go vet ./...

clean:
	rm -f $(BINARY) build/$(BINARY)-*

run: build
	./$(BINARY)

cross:
	GOOS=linux GOARCH=amd64 go build -o build/$(BINARY)-linux-amd64 ./cmd/m3u8-down/
	GOOS=linux GOARCH=arm64 go build -o build/$(BINARY)-linux-arm64 ./cmd/m3u8-down/

so:
	GOOS=linux GOARCH=amd64 go build -o build/libm3u8_engine.so -buildmode=c-shared ./pkg/
	GOOS=linux GOARCH=arm64 go build -o build/libm3u8_engine-arm64.so -buildmode=c-shared ./pkg/

.PHONY: all build test test-short fmt vet clean run cross so
