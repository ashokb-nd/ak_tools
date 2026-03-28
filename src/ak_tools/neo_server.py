from __future__ import annotations

import json
import os
import os.path as osp
import re
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .sync_alert import parse_s3_uri


MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".mp4": "video/mp4",
}


@dataclass
class NeoServerConfig:
    data_dir: str
    static_dir: str
    markr_edge_dir: str
    s3_bucket: str | None = None
    s3_prefix: str = ""
    s3_presign_expiry: int = 3600


def _safe_join(base_dir: str, relative_path: str) -> str | None:
    base_real = osp.realpath(base_dir)
    target_real = osp.realpath(osp.join(base_real, relative_path))
    if target_real == base_real or target_real.startswith(base_real + osp.sep):
        return target_real
    return None


def _sanitize_alert_id(value: str | None) -> str | None:
    if not value:
        return None
    value = str(value).strip()
    if not value or "/" in value or "\\" in value or ".." in value:
        return None
    return value


def _range_tuple(range_header: str, total_size: int) -> tuple[int, int] | None:
    match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not match:
        return None

    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else total_size - 1
    if start >= total_size or end >= total_size or start > end:
        return None
    return start, end


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length > 1_000_000:
        raise ValueError("Request body too large")
    raw = handler.rfile.read(content_length) if content_length else b"{}"
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON") from exc


def _alert_summary(data_dir: str, alert_id: str) -> dict:
    alert_dir = osp.join(data_dir, alert_id)
    files = os.listdir(alert_dir)
    videos = sorted(
        [f for f in files if osp.isfile(osp.join(alert_dir, f)) and f.lower().endswith(".mp4")],
        key=lambda x: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", x)],
    )

    metadata_path = osp.join(alert_dir, "metadata.txt")
    has_metadata = osp.exists(metadata_path)
    metadata_preview = ""
    if has_metadata:
        with open(metadata_path, "r", encoding="utf-8", errors="ignore") as handle:
            metadata_preview = handle.read(400)

    return {
        "alertId": alert_id,
        "videos": videos,
        "hasMetadata": has_metadata,
        "metadataPreview": metadata_preview,
    }


def _empty_alert_summary(alert_id: str) -> dict:
    return {
        "alertId": alert_id,
        "videos": [],
        "hasMetadata": False,
        "metadataPreview": "",
    }


def _s3_key(prefix: str, alert_id: str, filename: str | None = None) -> str:
    parts = [p for p in [prefix.strip("/"), alert_id.strip("/")] if p]
    if filename is not None:
        parts.append(filename)
    return "/".join(parts)


def _s3_list_alert_ids(s3_client, bucket: str, prefix: str) -> list[str]:
    delimiter_prefix = prefix.rstrip("/") + "/" if prefix else ""
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=delimiter_prefix, Delimiter="/")

    alert_ids: list[str] = []
    for page in pages:
        for cp in page.get("CommonPrefixes", []):
            folder_name = cp["Prefix"].rstrip("/").split("/")[-1]
            if folder_name:
                alert_ids.append(folder_name)
    return sorted(alert_ids)


def _s3_list_alert_files(s3_client, bucket: str, prefix: str, alert_id: str) -> list[str]:
    alert_prefix = _s3_key(prefix, alert_id) + "/"
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=alert_prefix)

    files: list[str] = []
    for page in pages:
        for obj in page.get("Contents", []):
            key = obj.get("Key", "")
            if not key or key.endswith("/"):
                continue
            files.append(key.rsplit("/", 1)[-1])
    return files


def _s3_read_text_object(s3_client, bucket: str, key: str) -> str:
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode("utf-8", errors="ignore")


def _s3_alert_summary(s3_client, bucket: str, prefix: str, alert_id: str) -> dict:
    files = _s3_list_alert_files(s3_client, bucket, prefix, alert_id)
    videos = sorted(
        [f for f in files if f.lower().endswith(".mp4")],
        key=lambda x: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", x)],
    )
    has_metadata = "metadata.txt" in files
    metadata_preview = ""

    if has_metadata:
        try:
            metadata_key = _s3_key(prefix, alert_id, "metadata.txt")
            metadata_preview = _s3_read_text_object(s3_client, bucket, metadata_key)[:400]
        except (ClientError, BotoCoreError):
            has_metadata = False

    return {
        "alertId": alert_id,
        "videos": videos,
        "hasMetadata": has_metadata,
        "metadataPreview": metadata_preview,
    }


def make_handler(config: NeoServerConfig):
    s3_client = boto3.client("s3") if config.s3_bucket else None

    class NeoHandler(BaseHTTPRequestHandler):
        server_version = "NeoKPI-Python/1.0"

        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_file(self, file_path: str) -> None:
            ext = osp.splitext(file_path)[1].lower()
            mime = MIME_TYPES.get(ext, "application/octet-stream")
            with open(file_path, "rb") as handle:
                data = handle.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _serve_video(self, file_path: str) -> None:
            try:
                self._serve_video_inner(file_path)
            except (ConnectionResetError, BrokenPipeError):
                pass  # client cancelled (seek / tab close)

        def _serve_video_inner(self, file_path: str) -> None:
            total_size = osp.getsize(file_path)
            range_header = self.headers.get("Range")
            if not range_header:
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(total_size))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                with open(file_path, "rb") as handle:
                    self.wfile.write(handle.read())
                return

            parsed = _range_tuple(range_header, total_size)
            if parsed is None:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{total_size}")
                self.end_headers()
                return

            start, end = parsed
            chunk_size = end - start + 1
            self.send_response(206)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(chunk_size))
            self.send_header("Content-Range", f"bytes {start}-{end}/{total_size}")
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

            with open(file_path, "rb") as handle:
                handle.seek(start)
                self.wfile.write(handle.read(chunk_size))

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/data-dir":
                self._send_json(404, {"error": "Not found"})
                return

            try:
                payload = _read_json_body(self)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return

            next_dir = str(payload.get("dataDir", "")).strip()
            if not next_dir:
                self._send_json(400, {"error": "dataDir is required"})
                return

            resolved = osp.realpath(next_dir)
            if not osp.isdir(resolved):
                self._send_json(400, {"error": "Directory does not exist"})
                return

            config.data_dir = resolved
            self._send_json(200, {"ok": True, "dataDir": config.data_dir})

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path

            if path.startswith("/markrEdge/"):
                requested = unquote(path.replace("/markrEdge/", "", 1))
                file_path = _safe_join(config.markr_edge_dir, osp.normpath(requested))
                if not file_path or not osp.isfile(file_path):
                    self.send_error(404, "Not found")
                    return
                self._serve_file(file_path)
                return

            if path.startswith("/api/"):
                self._handle_api(path)
                return

            if path.startswith("/data/"):
                self._handle_data(path)
                return

            self._handle_static(path)

        def _handle_api(self, path: str) -> None:
            if path == "/api/alerts":
                if config.s3_bucket:
                    try:
                        alert_ids = _s3_list_alert_ids(s3_client, config.s3_bucket, config.s3_prefix)
                    except (ClientError, BotoCoreError) as exc:
                        self._send_json(500, {"error": f"Failed to list S3 alerts: {str(exc)}"})
                        return

                    alerts = [_empty_alert_summary(alert_id) for alert_id in alert_ids]
                    self._send_json(200, {"dataDir": config.data_dir, "count": len(alerts), "alerts": alerts})
                    return

                if not osp.isdir(config.data_dir):
                    self._send_json(200, {"dataDir": config.data_dir, "count": 0, "alerts": []})
                    return

                alerts = []
                for name in sorted(os.listdir(config.data_dir)):
                    full = osp.join(config.data_dir, name)
                    if osp.isdir(full):
                        alerts.append(_alert_summary(config.data_dir, name))

                self._send_json(200, {"dataDir": config.data_dir, "count": len(alerts), "alerts": alerts})
                return

            match = re.match(r"^/api/alerts/([^/]+)$", path)
            if match:
                alert_id = _sanitize_alert_id(unquote(match.group(1)))
                if not alert_id:
                    self._send_json(400, {"error": "Invalid alert id"})
                    return

                if config.s3_bucket:
                    try:
                        summary = _s3_alert_summary(s3_client, config.s3_bucket, config.s3_prefix, alert_id)
                    except (ClientError, BotoCoreError) as exc:
                        self._send_json(500, {"error": f"Failed to load S3 alert: {str(exc)}"})
                        return

                    if not summary["videos"] and not summary["hasMetadata"]:
                        self._send_json(404, {"error": "Alert directory not found"})
                        return

                    metadata_text = ""
                    if summary["hasMetadata"]:
                        metadata_key = _s3_key(config.s3_prefix, alert_id, "metadata.txt")
                        try:
                            metadata_text = _s3_read_text_object(s3_client, config.s3_bucket, metadata_key)
                        except (ClientError, BotoCoreError):
                            metadata_text = ""

                    video_urls = []
                    for name in summary["videos"]:
                        key = _s3_key(config.s3_prefix, alert_id, name)
                        try:
                            presigned = s3_client.generate_presigned_url(
                                "get_object",
                                Params={"Bucket": config.s3_bucket, "Key": key},
                                ExpiresIn=config.s3_presign_expiry,
                            )
                            video_urls.append(presigned)
                        except (ClientError, BotoCoreError):
                            # Keep index alignment with summary["videos"] for frontend lookup.
                            video_urls.append("")

                    self._send_json(
                        200,
                        {
                            **summary,
                            "metadataText": metadata_text,
                            "videoUrls": video_urls,
                        },
                    )
                    return

                alert_dir = osp.join(config.data_dir, alert_id)
                if not osp.isdir(alert_dir):
                    self._send_json(404, {"error": "Alert directory not found"})
                    return

                summary = _alert_summary(config.data_dir, alert_id)
                metadata_path = osp.join(alert_dir, "metadata.txt")
                metadata_text = ""
                if summary["hasMetadata"]:
                    with open(metadata_path, "r", encoding="utf-8", errors="ignore") as handle:
                        metadata_text = handle.read()

                self._send_json(
                    200,
                    {
                        **summary,
                        "metadataText": metadata_text,
                        "videoUrls": [f"/data/{alert_id}/{name}" for name in summary["videos"]],
                    },
                )
                return

            self._send_json(404, {"error": "Not found"})

        def _handle_data(self, path: str) -> None:
            match = re.match(r"^/data/([^/]+)/([^/]+)$", path)
            if not match:
                self.send_error(404, "Not found")
                return

            alert_id = _sanitize_alert_id(unquote(match.group(1)))
            file_name = unquote(match.group(2))
            if not alert_id or "/" in file_name or "\\" in file_name or ".." in file_name:
                self.send_error(400, "Invalid path")
                return

            file_path = osp.join(config.data_dir, alert_id, file_name)
            if not osp.isfile(file_path):
                self.send_error(404, "File not found")
                return

            if osp.splitext(file_path)[1].lower() == ".mp4":
                self._serve_video(file_path)
            else:
                self._serve_file(file_path)

        def _handle_static(self, path: str) -> None:
            is_alert_debug = path == "/alert-debug" or path.startswith("/alert-debug/")
            requested = "/index.html" if path == "/" or is_alert_debug else path
            safe = osp.normpath(requested).lstrip("/\\")
            file_path = _safe_join(config.static_dir, safe)
            if not file_path or not osp.isfile(file_path):
                self.send_error(404, "Not found")
                return
            self._serve_file(file_path)

        def log_message(self, format: str, *args) -> None:
            return

    return NeoHandler


def start_neo_server(
    host: str = "localhost",
    port: int = 8090,
    data_dir: str | None = None,
    app_dir: str | None = None,
    s3_uri: str | None = None,
    s3_presign_expiry: int = 3600,
) -> None:
    if app_dir is None:
        raise ValueError("app_dir is required")

    resolved_app_dir = osp.realpath(osp.expanduser(app_dir))
    resolved_data_dir = osp.realpath(osp.expanduser(data_dir or osp.join(osp.expanduser("~"), "neokpi")))
    static_dir = resolved_app_dir
    markr_edge_dir = osp.join(resolved_app_dir, "markrEdge")

    if not osp.isdir(static_dir):
        raise ValueError(f"NeoKPI app directory not found: {static_dir}")
    if not osp.isdir(markr_edge_dir):
        raise ValueError(f"markrEdge directory not found: {markr_edge_dir}")

    config = NeoServerConfig(
        data_dir=resolved_data_dir,
        static_dir=static_dir,
        markr_edge_dir=markr_edge_dir,
    )

    if s3_uri:
        bucket, prefix = parse_s3_uri(s3_uri)
        config.s3_bucket = bucket
        config.s3_prefix = prefix
        config.s3_presign_expiry = int(s3_presign_expiry)

    handler = make_handler(config)
    server = ThreadingHTTPServer((host, port), handler)

    print(f"Mock alert site running at http://{host}:{port}")
    print(f"Loading alert data from: {config.data_dir}")
    if config.s3_bucket:
        print(
            f"Using S3 direct video mode from s3://{config.s3_bucket}/{config.s3_prefix} "
            f"(presign expiry: {config.s3_presign_expiry}s)"
        )
    server.serve_forever()
