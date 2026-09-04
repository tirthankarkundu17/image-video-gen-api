"""
Standalone test script to verify Google Cloud Storage bucket connectivity and permissions.
Usage:
    python test_storage_upload.py [optional-bucket-name]
"""
import sys
from datetime import datetime, timezone

from app.config import get_settings
from app.services.storage_service import upload_image_bytes

TINY_TEST_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xbf"
    b"\x1e\x00\x05\xfe\x02\xfe\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
)


def main():
    settings = get_settings()

    bucket_name = sys.argv[1] if len(sys.argv) > 1 else settings.GCS_IMAGE_BUCKET

    if not bucket_name:
        print("[ERROR] No GCS bucket provided.")
        print("Set GCS_IMAGE_BUCKET in your .env or run: python test_storage_upload.py <bucket-name>")
        sys.exit(1)

    prefix = settings.GCS_PATH_PREFIX or "test-uploads"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    blob_name = f"{prefix}/ping_{timestamp}.png"

    print(f"Testing Google Cloud Storage upload...")
    print(f"Target Bucket : {bucket_name}")
    print(f"Destination   : gs://{bucket_name}/{blob_name}")

    try:
        gcs_uri, gcs_url = upload_image_bytes(
            image_bytes=TINY_TEST_PNG_BYTES,
            bucket_name=bucket_name,
            destination_blob_name=blob_name,
            content_type="image/png",
        )
        print("\n[SUCCESS] Image uploaded successfully!")
        print(f"  GCS URI : {gcs_uri}")
        print(f"  GCS URL : {gcs_url}")
    except Exception as e:
        print(f"\n[FAILED] Upload error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
