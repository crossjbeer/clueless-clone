"""
storage.py — Thin abstraction over local filesystem vs S3.

Set USE_S3=true in the environment to switch to S3.
Also requires S3_BUCKET to be set when USE_S3 is enabled.

All keys are relative paths (e.g. "cache/2026-05-21.json", "used_words.txt").
In S3 mode they become object keys directly under the bucket root.
In local mode they resolve relative to the project directory.

S3 Express One Zone buckets (name ends with --az-id--x-s3) require the
s3express:CreateSession IAM permission on the EC2 instance role in addition
to the standard s3:GetObject / s3:PutObject permissions.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_USE_S3: bool = os.getenv("USE_S3", "false").lower() == "true"
_BUCKET: str = os.getenv("S3_BUCKET", "")
_REGION: str = os.getenv("AWS_DEFAULT_REGION", "us-east-2")
_BASE_DIR: Path = Path(__file__).parent

if _USE_S3 and not _BUCKET:
    raise RuntimeError("USE_S3 is enabled but S3_BUCKET is not set.")

# Lazy boto3 client — only imported when S3 is actually needed.
_s3 = None


def _raise_s3_friendly(exc: Exception) -> None:
    """Re-raise S3 errors with actionable messages."""
    msg = str(exc)
    if "CreateSession" in msg or "AccessDenied" in msg:
        is_express = _BUCKET.endswith("--x-s3")
        hint = (
            " S3 Express One Zone buckets require the 's3express:CreateSession' "
            "IAM permission on the EC2 instance role."
            if is_express
            else " Check that the EC2 instance role has s3:GetObject/s3:PutObject on this bucket."
        )
        raise PermissionError(f"S3 access denied for bucket '{_BUCKET}'.{hint}") from exc
    raise exc


def _client():
    global _s3
    if _s3 is None:
        import boto3
        _s3 = boto3.client("s3", region_name=_REGION)
    return _s3


# ── Public API ──────────────────────────────────────────────────────────────

def read_text(key: str) -> str | None:
    """
    Read a text object by key.
    Returns None if the object/file does not exist.
    """
    if _USE_S3:
        try:
            response = _client().get_object(Bucket=_BUCKET, Key=key)
            return response["Body"].read().decode("utf-8")
        except _client().exceptions.NoSuchKey:
            return None
        except Exception:
            # Catch broader botocore ClientError for NoSuchKey
            return None
    else:
        path = _BASE_DIR / key
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")


def write_text(key: str, content: str) -> None:
    """Write a text object by key, creating it if it doesn't exist."""
    if _USE_S3:
        try:
            _client().put_object(
                Bucket=_BUCKET,
                Key=key,
                Body=content.encode("utf-8"),
                ContentType="application/json",
            )
        except Exception as exc:
            _raise_s3_friendly(exc)
    else:
        path = _BASE_DIR / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def read_json(key: str) -> dict | None:
    """Convenience wrapper — returns parsed JSON or None."""
    text = read_text(key)
    if text is None:
        return None
    return json.loads(text)


def write_json(key: str, data: dict) -> None:
    """Convenience wrapper — serialises dict and writes."""
    write_text(key, json.dumps(data, ensure_ascii=False))
