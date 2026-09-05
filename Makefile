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
PORT           ?= 8000

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

.PHONY: all build push push-latest run stop logs clean login help

# Default target
all: build push

## help: Display this help message
help:
	@echo "========================================================================"
	@echo " Docker Automation Makefile for $(IMAGE_NAME)"
	@echo "========================================================================"
	@echo "Usage:"
	@echo "  make build [DOCKER_USER=username] [TAG=version]"
	@echo "  make push  [DOCKER_USER=username] [TAG=version]"
	@echo "  make all   [DOCKER_USER=username] [TAG=version]  # build then push"
	@echo "  make run   [PORT=8000]                           # run container locally"
	@echo "  make stop                                        # stop running container"
	@echo ""
	@echo "Targets:"
	@echo "  build       Build the Docker image locally"
	@echo "  push        Push image to Docker Hub / Registry (requires DOCKER_USER or REGISTRY)"
	@echo "  push-latest Push both $(TAG) and :latest tags"
	@echo "  run         Run the container with .env file mounted"
	@echo "  stop        Stop and remove the local container"
	@echo "  logs        Follow container logs"
	@echo "  login       Log into Docker Hub or custom registry"
	@echo "  clean       Remove local built images"
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
