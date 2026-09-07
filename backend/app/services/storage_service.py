"""Private local/S3 storage shared by uploads, workers and exports."""
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit
import shutil
from app.core.config import settings, BASE_DIR

ROOT = BASE_DIR / "storage"


def safe_key(key):
    path = PurePosixPath(key)
    if path.is_absolute() or ".." in path.parts or "\\" in key or not path.parts:
        raise ValueError("Invalid storage key.")
    return path.as_posix()


def s3_client():
    import boto3
    from botocore.config import Config
    return boto3.client("s3", region_name=settings.S3_REGION or settings.AWS_DEFAULT_REGION,
        endpoint_url=settings.S3_ENDPOINT_URL, aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(connect_timeout=5, read_timeout=30, retries={"max_attempts": 3}))


def local_path(reference):
    path = ROOT / safe_key(reference[8:]) if reference.startswith("local://") else Path(reference)
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT.resolve()):
        raise ValueError("Invalid storage location.")
    return resolved


def s3_parts(reference):
    parsed = urlsplit(reference)
    key = safe_key(parsed.path.lstrip("/"))
    if parsed.netloc != settings.S3_BUCKET or not key.startswith(settings.S3_PREFIX.strip("/") + "/"):
        raise ValueError("Invalid storage location.")
    return parsed.netloc, key


def put_file(path, key, content_type="application/octet-stream"):
    key = safe_key(key)
    if settings.STORAGE_BACKEND == "s3":
        from boto3.s3.transfer import TransferConfig
        full_key = safe_key(settings.S3_PREFIX.strip("/") + "/" + key)
        encryption = {"ServerSideEncryption": "AES256"}
        if settings.S3_KMS_KEY_ID:
            encryption = {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": settings.S3_KMS_KEY_ID}
        s3_client().upload_file(str(path), settings.S3_BUCKET, full_key,
            ExtraArgs={"ContentType": content_type, **encryption},
            Config=TransferConfig(max_concurrency=2, multipart_chunksize=8 * 1024 * 1024))
        return f"s3://{settings.S3_BUCKET}/{full_key}"
    destination = local_path("local://" + key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=destination.parent, delete=False) as output:
        temporary = Path(output.name)
    try:
        shutil.copyfile(path, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return "local://" + key


@contextmanager
def materialize(reference):
    if not reference.startswith("s3://"):
        yield local_path(reference)
        return
    bucket, key = s3_parts(reference)
    with NamedTemporaryFile(suffix=PurePosixPath(key).suffix, delete=False) as file:
        path = Path(file.name)
    try:
        response = s3_client().get_object(Bucket=bucket, Key=key)
        size = 0
        try:
            with path.open("wb") as output:
                for chunk in response["Body"].iter_chunks(chunk_size=1024 * 1024):
                    size += len(chunk)
                    if size > max(settings.MAX_FILE_BYTES, settings.EXPORT_MAX_BYTES):
                        raise ValueError("Stored file exceeds the configured limit.")
                    output.write(chunk)
        finally:
            response["Body"].close()
        yield path
    finally:
        path.unlink(missing_ok=True)


def delete_file(reference):
    if reference.startswith("s3://"):
        bucket, key = s3_parts(reference)
        s3_client().delete_object(Bucket=bucket, Key=key)
    else:
        local_path(reference).unlink(missing_ok=True)
