# Postman Collection Guide

This folder contains the ready-to-import Postman collection and environment for the Vertex AI Image & Video Generation API.

## Files
- **`Vertex_AI_Image_Video_Gen_API.postman_collection.json`**: Complete Postman v2.1 collection containing requests for all endpoints with example payloads, headers, and automatic operation ID chaining.
- **`Vertex_AI_Local.postman_environment.json`**: Pre-configured environment file for local testing (`http://localhost:8000`).

---

## How to Import into Postman

1. Open Postman.
2. Click **Import** (top left).
3. Drag & drop or browse to select both:
   - `Vertex_AI_Image_Video_Gen_API.postman_collection.json`
   - `Vertex_AI_Local.postman_environment.json`
4. In the top right environment dropdown, select **Vertex AI API - Local**.

---

## Authentication Configuration

### Option 1: Google Service Account Token (Recommended)
1. Run either command in your terminal:
   ```bash
   # OAuth2 Access Token
   gcloud auth print-access-token
   
   # Or OIDC Identity Token
   gcloud auth print-identity-token
   ```
2. In Postman, open the **Vertex AI API - Local** environment (or collection variables) and paste the token into `bearerToken`.
3. Requests will automatically use `Authorization: Bearer {{bearerToken}}`.

### Option 2: API Key
If you set `API_KEY=your-secret-key` in your server `.env`:
1. Set `apiKey` in Postman variables.
2. Enable the `X-API-Key: {{apiKey}}` header in the request.

---

## Requests Included

### 1. Health & Monitoring
- `GET /healthz` - Liveness probe
- `GET /readyz` - Readiness probe (checks GCP project & client status)
- `POST /api/v1/storage/test-upload` - Test GCS upload connectivity and permissions without calling AI models

### 2. Image Generation (Imagen 3 & Gemini Image Models)
- `POST /api/v1/images/generate` - Default square 1:1
- `POST /api/v1/images/generate` - Widescreen 16:9 with person generation controls
- `POST /api/v1/images/generate` - Portrait 9:16
- `POST /api/v1/images/generate` - Batch generation (multiple images)
- `POST /api/v1/images/generate` - Generate & Upload directly to Google Cloud Storage (`upload_to_gcs: true`)

### 3. Video Generation (Veo)
- `POST /api/v1/videos/generate` - Asynchronous generation (returns 202 and automatically extracts and sets `operation_id` for polling)
- `GET /api/v1/videos/operations/{{operation_id}}` - Polls operation status and retrieves video URI
- `POST /api/v1/videos/generate` - Synchronous wait mode (`wait_for_completion: true`)
