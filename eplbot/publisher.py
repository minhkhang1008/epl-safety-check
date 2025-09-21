from __future__ import annotations
import os, json
from typing import Optional
import requests

try:
    import boto3
    _HAS_BOTO3 = True
except Exception:
    _HAS_BOTO3 = False


def _fd_headers() -> dict:
    token = os.environ.get("FOOTBALL_DATA_API_KEY")
    if not token:
        raise RuntimeError("FOOTBALL_DATA_API_KEY not set")
    return {"X-Auth-Token": token}

def detect_current_season_year() -> int:
    """Trả về năm bắt đầu mùa hiện tại (vd 2025) bằng standings football-data."""
    r = requests.get(
        "https://api.football-data.org/v4/competitions/PL/standings",
        headers=_fd_headers(), timeout=25
    )
    r.raise_for_status()
    data = r.json()
    season = data.get("season") or {}
    start = season.get("startDate")
    if start and len(start) >= 4:
        return int(start[:4])
    return int(os.environ.get("EPL_DEFAULT_SEASON", "2025"))


def publish_file(snapshot_path: str, dest_path: str) -> str:
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    with open(snapshot_path, "rb") as src, open(dest_path, "wb") as dst:
        dst.write(src.read())
    return f"file://{os.path.abspath(dest_path)}"

def publish_gist(snapshot_path: str, gist_id: str, token: Optional[str] = None, filename: str = "snapshot.json") -> str:
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not set for gist publish")

    with open(snapshot_path, "r", encoding="utf-8") as f:
        content = f.read()

    url = f"https://api.github.com/gists/{gist_id}"
    payload = {"files": {filename: {"content": content}}}
    r = requests.patch(
        url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    raw_url = data["files"][filename]["raw_url"]
    return raw_url

def publish_s3(snapshot_path: str, bucket: str, key: str, region: Optional[str] = None, public: bool = True) -> str:
    if not _HAS_BOTO3:
        raise RuntimeError("boto3 not installed. pip install boto3")
    s3 = boto3.client("s3", region_name=region)
    extra = {"ContentType": "application/json"}
    if public:
        extra["ACL"] = "public-read"
    s3.upload_file(snapshot_path, bucket, key, ExtraArgs=extra)
    if region in (None, "", "us-east-1"):
        return f"https://{bucket}.s3.amazonaws.com/{key}"
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
