# Vertex AI Image & Video Generation API

A production-ready, high-performance REST API built with **FastAPI** and the **Google Gen AI SDK (`google-genai`)** that generates images and videos via Google Cloud Vertex AI (**Imagen 3** and **Veo**), secured with **GCP Service Account Authentication**.

---

## Features

- **Vertex AI Imagen 3 (`imagen-3.0-generate-002`)**: High-fidelity text-to-image generation with customizable aspect ratios (`1:1`, `16:9`, `9:16`, `4:3`, `3:4`), multiple outputs, safety filtering, and base64 response delivery.
- **Vertex AI Veo (`veo-2.0-generate-001`)**: Text-to-video generation supporting asynchronous Long Running Operations (LRO), status polling, optional synchronous waiting, configurable aspect ratio, duration, and FPS.
- **GCP Service Account Authentication**:
  - **Backend to Vertex AI**: Securely authenticates using GCP Service Account JSON keys, inline JSON string, or Application Default Credentials (ADC) with the `https://www.googleapis.com/auth/cloud-platform` scope.
  - **API Caller Authentication**: Protects endpoints by validating caller tokens (`Authorization: Bearer <token>`) against Google Cloud IAM (supporting Google OAuth2 access tokens and Google OIDC ID tokens), with support for allowed service accounts filtering (`ALLOWED_SERVICE_ACCOUNTS`) and API keys for direct testing.
- **Interactive Documentation**: Built-in Swagger UI (`/docs`) and ReDoc (`/redoc`).
- **Health & Readiness Probes**: `/healthz` and `/readyz` for Kubernetes/Cloud Run health monitoring.
- **Complete Test Suite**: Unit and integration tests with mocked Vertex AI and token verification.

---

## Architecture Overview

```
image-video-gen-api/
├── app/
│   ├── auth/
│   │   ├── dependencies.py      # FastAPI auth dependency (validates Bearer token / API key)
│   │   └── gcp_auth.py          # Service account credentials & token verification
│   ├── routers/
│   │   ├── health.py            # /healthz and /readyz endpoints
│   │   ├── images.py            # /api/v1/images/generate
│   │   └── videos.py            # /api/v1/videos/generate & /api/v1/videos/operations/{id}
│   ├── schemas/
│   │   ├── common.py            # Health, readiness, and error models
│   │   ├── image.py             # Image generation request/response schemas
│   │   └── video.py             # Video generation request/response schemas
│   ├── services/
│   │   ├── image_service.py     # Vertex AI Imagen generation logic
│   │   ├── vertex_client.py     # Vertex AI Client lifecycle manager
│   │   └── video_service.py     # Vertex AI Veo generation & LRO tracking
│   ├── config.py                # Pydantic BaseSettings environment configuration
│   └── main.py                  # FastAPI application factory & middleware
├── tests/                       # Complete pytest suite
├── .env.example                 # Environment configuration template
├── Dockerfile                   # Production container definition
├── pyproject.toml               # Project dependencies and settings
└── README.md                    # Documentation
```

---

## Prerequisites & GCP Setup

### 1. Enable Vertex AI API
In your Google Cloud Console:
```bash
gcloud services enable aiplatform.googleapis.com
```

### 2. Create a Service Account & Grant Roles
Create a service account for Vertex AI:
```bash
gcloud iam service-accounts create vertex-genai-sa \
    --display-name="Vertex AI GenAI Service Account"

# Grant Vertex AI User role
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:vertex-genai-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"
```

### 3. Generate a JSON Key File
```bash
gcloud iam service-accounts keys create ./service-account-key.json \
    --iam-account=vertex-genai-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

---

## Quick Start

### 1. Install Dependencies
Using `uv`:
```bash
uv sync
```
Or standard `pip`:
```bash
pip install -e .
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env`:
```ini
GCP_PROJECT_ID=your-gcp-project-id
GCP_LOCATION=us-central1
GCP_SERVICE_ACCOUNT_FILE=./service-account-key.json

# Security
AUTH_ENABLED=true
ALLOWED_SERVICE_ACCOUNTS=client-sa@your-gcp-project-id.iam.gserviceaccount.com
API_KEY=your-optional-dev-api-key
```

### 3. Start the API Server
Using `make`:
```bash
make run-local
```
Or directly with `uv`:
```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
Open **[http://localhost:8000/docs](http://localhost:8000/docs)** to view the interactive Swagger UI.

---

## API Usage & Examples

### 1. Generating a Bearer Token for Requests
Callers authenticate using a Google Service Account token:

**Option A: Google OAuth2 Access Token**
```bash
TOKEN=$(gcloud auth print-access-token)
```

**Option B: Google Identity (OIDC) Token**
```bash
TOKEN=$(gcloud auth print-identity-token)
```

**Option C: Using API Key (if configured in `.env`)**
Pass `X-API-Key: your-optional-dev-api-key` header.

---

### 2. Generate Images (Imagen 3)

**Endpoint:** `POST /api/v1/images/generate`

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/images/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A cinematic macro photograph of a dew drop on a spiderweb reflecting a galaxy at dawn",
    "negative_prompt": "blurry, low quality, distorted",
    "aspect_ratio": "16:9",
    "number_of_images": 1,
    "output_mime_type": "image/png"
  }'
```

**Response (200 OK):**
```json
{
  "model": "imagen-3.0-generate-002",
  "prompt": "A cinematic macro photograph of a dew drop on a spiderweb reflecting a galaxy at dawn",
  "images": [
    {
      "index": 1,
      "mime_type": "image/png",
      "base64_data": "iVBORw0KGgoAAAANSUhEUgAA..."
    }
  ],
  "total_images": 1,
  "created_at": "2026-09-04T17:30:00.000Z"
}
```

---

### 3. Generate Videos (Veo)

#### Asynchronous Mode (Default)
Initiate generation and receive an operation tracking ID:

**Endpoint:** `POST /api/v1/videos/generate`

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/videos/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Cinematic aerial drone flight gliding over a tropical emerald coastline at sunset",
    "aspect_ratio": "16:9",
    "duration_seconds": 5,
    "wait_for_completion": false
  }'
```

**Response (202 Accepted):**
```json
{
  "operation_id": "projects/YOUR_PROJECT_ID/locations/us-central1/publishers/google/models/veo-2.0-generate-001/operations/1234567890",
  "status": "RUNNING",
  "model": "veo-2.0-generate-001",
  "prompt": "Cinematic aerial drone flight gliding over a tropical emerald coastline at sunset",
  "video_uri": null,
  "video_base64": null,
  "created_at": "2026-09-04T17:30:00.000Z"
}
```

#### Poll Video Operation Status
**Endpoint:** `GET /api/v1/videos/operations/{operation_id}`

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/videos/operations/projects/YOUR_PROJECT_ID/locations/us-central1/publishers/google/models/veo-2.0-generate-001/operations/1234567890" \
  -H "Authorization: Bearer $TOKEN"
```

**Response when Complete:**
```json
{
  "operation_id": "projects/YOUR_PROJECT_ID/locations/us-central1/publishers/google/models/veo-2.0-generate-001/operations/1234567890",
  "status": "COMPLETED",
  "model": "veo-2.0-generate-001",
  "video_uri": "gs://your-bucket/generated_videos/video_output.mp4",
  "mime_type": "video/mp4",
  "created_at": "2026-09-04T17:30:00.000Z",
  "updated_at": "2026-09-04T17:31:15.000Z"
}
```

---

## Health Checks

- **Liveness:** `GET /healthz` - Returns `{"status": "healthy", "version": "0.1.0", ...}`
- **Readiness:** `GET /readyz` - Reports Vertex AI configuration and connectivity readiness.

---

## Running Automated Tests

Run the complete test suite:
```bash
uv run pytest -v
```

---

## Docker Deployment

Build the container image:
```bash
docker build -t vertex-image-video-api:latest .
```

Run container:
```bash
docker run -p 8000:8000 \
  -e GCP_PROJECT_ID="your-project-id" \
  -e GCP_LOCATION="us-central1" \
  -v $(pwd)/service-account-key.json:/app/service-account-key.json \
  -e GCP_SERVICE_ACCOUNT_FILE="/app/service-account-key.json" \
  vertex-image-video-api:latest
```

---

## CI/CD & Automated Docker Hub Deployment

An automated GitHub Actions workflow is set up at [`.github/workflows/docker-publish.yml`](.github/workflows/docker-publish.yml) to run tests and push multi-architecture Docker images (`linux/amd64`, `linux/arm64`) directly to Docker Hub.

### 1. Configure GitHub Secrets

Navigate to your GitHub repository: **Settings** &rarr; **Secrets and variables** &rarr; **Actions** and add the following repository secrets:

| Secret Name | Description |
|---|---|
| `DOCKERHUB_USERNAME` | Your Docker Hub username or organization |
| `DOCKERHUB_TOKEN` | Docker Hub Personal Access Token (PAT) with `Read & Write` access |

### 2. Workflow Trigger Behavior

- **Push to `main` or `dev`**: Runs tests, builds the multi-platform image, and tags with branch name (`main`, `dev`) and `:latest` (for `main`).
- **Git Tags (`v*.*.*`)**: Builds and tags the image with the release version (e.g. `:v1.0.0`, `:1.0`, `:1`).
- **Pull Requests to `main`**: Runs the full test suite and verifies that the Docker image builds cleanly across all target architectures (without pushing).
- **Manual Trigger (`workflow_dispatch`)**: Can be manually run from the GitHub Actions tab with an optional custom tag.

