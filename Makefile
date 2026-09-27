# ==============================================================================
# Docker Build & Push Makefile for Vertex AI Image & Video Generation API
# ==============================================================================

# Variables (can be overridden via CLI arguments or environment variables)
# Examples:
#   make build DOCKER_USER=myusername TAG=v1.0.0
#   make push DOCKER_USER=myusername TAG=v1.0.0
#   make all DOCKER_USER=myusername TAG=v1.0.0
#   make push REGISTRY=us-central1-docker.pkg.dev/my-project/my-repo

IMAGE_NAME     ?= image-video-gen-api
TAG            ?= latest
DOCKER_USER    ?=
REGISTRY       ?=
CONTAINER_NAME ?= image-video-gen-api-app
HOST           ?= 0.0.0.0
PORT           ?= 8000

# Base64 decoder options
INPUT          ?=
IN             ?= $(INPUT)
OUTPUT         ?=
OUT            ?= $(OUTPUT)
DATA           ?=

# Determine full target image name
ifneq ($(REGISTRY),)
    FULL_IMAGE := $(REGISTRY)/$(IMAGE_NAME):$(TAG)
    LATEST_IMAGE := $(REGISTRY)/$(IMAGE_NAME):latest
else ifneq ($(DOCKER_USER),)
    FULL_IMAGE := $(DOCKER_USER)/$(IMAGE_NAME):$(TAG)
    LATEST_IMAGE := $(DOCKER_USER)/$(IMAGE_NAME):latest
else
    FULL_IMAGE := $(IMAGE_NAME):$(TAG)
    LATEST_IMAGE := $(IMAGE_NAME):latest
endif

# Build base64-to-file arguments
B64_ARGS :=
ifneq ($(strip $(DATA)),)
    B64_ARGS += -d "$(DATA)"
else ifneq ($(strip $(IN)),)
    B64_ARGS += -i "$(IN)"
endif
ifneq ($(strip $(OUT)),)
    B64_ARGS += -o "$(OUT)"
endif

.PHONY: all build push push-latest run run-local stop logs clean login help decode-base64 base64-to-file

# Default target
all: build push

## help: Display this help message
help:
	@echo "========================================================================"
	@echo " Docker & Local Dev Automation Makefile for $(IMAGE_NAME)"
	@echo "========================================================================"
	@echo "Usage:"
	@echo "  make build         [DOCKER_USER=username] [TAG=version]"
	@echo "  make push          [DOCKER_USER=username] [TAG=version]"
	@echo "  make all           [DOCKER_USER=username] [TAG=version]  # build then push"
	@echo "  make run           [PORT=8000]                           # run container locally"
	@echo "  make run-local     [HOST=0.0.0.0] [PORT=8000]            # run FastAPI dev server locally"
	@echo "  make decode-base64 [INPUT=file] [OUTPUT=out.mp4]         # decode base64 file to media"
	@echo "  make decode-base64 [DATA=b64] [OUTPUT=out.mp4]           # decode direct base64 string"
	@echo "  make stop                                                # stop running container"
	@echo ""
	@echo "Targets:"
	@echo "  build          Build the Docker image locally"
	@echo "  push           Push image to Docker Hub / Registry (requires DOCKER_USER or REGISTRY)"
	@echo "  push-latest    Push both $(TAG) and :latest tags"
	@echo "  run            Run the container with .env file mounted"
	@echo "  run-local      Run FastAPI dev server locally via uv and uvicorn with hot reload"
	@echo "  decode-base64  Decode base64 input file or string to video/image (alias: base64-to-file)"
	@echo "  base64-to-file Alias for decode-base64"
	@echo "  stop           Stop and remove the local container"
	@echo "  logs           Follow container logs"
	@echo "  login          Log into Docker Hub or custom registry"
	@echo "  clean          Remove local built images"
	@echo "========================================================================"

## login: Authenticate with Docker Registry
login:
ifdef REGISTRY
	@echo "Logging into registry $(REGISTRY)..."
	docker login $(REGISTRY)
else
	@echo "Logging into Docker Hub..."
	docker login
endif

## build: Build Docker image locally
build:
	@echo "==> Building Docker image: $(FULL_IMAGE)"
	docker build -t $(FULL_IMAGE) -t $(IMAGE_NAME):latest .
ifneq ($(FULL_IMAGE),$(LATEST_IMAGE))
	docker tag $(FULL_IMAGE) $(LATEST_IMAGE)
endif
	@echo "==> Build completed: $(FULL_IMAGE)"

## push: Push Docker image to registry
push:
ifeq ($(strip $(DOCKER_USER)$(REGISTRY)),)
	$(error Error: DOCKER_USER or REGISTRY must be set to push. Example: make push DOCKER_USER=myusername)
endif
	@echo "==> Pushing Docker image: $(FULL_IMAGE)"
	docker push $(FULL_IMAGE)
	@echo "==> Successfully pushed $(FULL_IMAGE)"

## push-latest: Push both tagged version and :latest tag
push-latest: push
ifneq ($(TAG),latest)
	@echo "==> Pushing latest tag: $(LATEST_IMAGE)"
	docker push $(LATEST_IMAGE)
	@echo "==> Successfully pushed $(LATEST_IMAGE)"
endif

## run-local: Run FastAPI dev server locally via uv and uvicorn with hot reload
run-local:
	@echo "==> Starting local development server on $(HOST):$(PORT)..."
	uv run uvicorn main:app --host $(HOST) --port $(PORT) --reload

## run: Run container locally with .env mounted and port forwarded
run:
	@echo "==> Running container $(CONTAINER_NAME) on port $(PORT)..."
	docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(PORT):8080 \
		--env-file .env \
		-v "$(CURDIR)/service-account.json:/app/service-account.json:ro" \
		$(FULL_IMAGE)
	@echo "==> Container running. Access API at http://localhost:$(PORT)/docs"

## stop: Stop and remove running container
stop:
	@echo "==> Stopping container $(CONTAINER_NAME)..."
	-docker stop $(CONTAINER_NAME)
	-docker rm $(CONTAINER_NAME)
	@echo "==> Container stopped."

## logs: View container output logs
logs:
	docker logs -f $(CONTAINER_NAME)

## clean: Remove built docker images
clean:
	@echo "==> Cleaning up images..."
	-docker rmi $(FULL_IMAGE)
	-docker rmi $(LATEST_IMAGE)
	@echo "==> Clean complete."

## decode-base64: Convert base64 data or input file to binary file (video, image, etc.)
decode-base64:
	@echo "==> Decoding base64 to file..."
	uv run python base64-to-file.py $(B64_ARGS)

## base64-to-file: Alias for decode-base64
base64-to-file: decode-base64

