from __future__ import annotations

import os

from google.cloud import storage


def main() -> None:
    bucket_name = os.environ["GCS_BUCKET"]

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    blob = bucket.blob("connection-test/from-python.txt")
    blob.upload_from_string("Python ADC connection works.\n")

    print(f"Uploaded: gs://{bucket_name}/{blob.name}")

    downloaded = blob.download_as_text()
    print(f"Downloaded content: {downloaded.strip()}")


if __name__ == "__main__":
    main()
