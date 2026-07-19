from __future__ import annotations

from pathlib import Path
from time import sleep

import requests

from .bilibili import prepare_bilibili_request


class DirectDownloadError(RuntimeError):
    """Raised when a direct media URL cannot be saved."""


def download_direct_media(
    url: str,
    output_path: Path,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    chunk_size: int = 1024 * 1024,
    cancel_callback=None,
    bilibili_compat: bool = False,
    retries: int = 3,
) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = output_path.with_name(f"{output_path.name}.part")
    request_url, request_headers = prepare_bilibili_request(url, headers, bilibili_compat)
    last_error: DirectDownloadError | None = None

    for attempt in range(max(1, retries)):
        try:
            part_size = part_path.stat().st_size if part_path.exists() else 0
            attempt_headers = dict(request_headers)
            if part_size and not _has_header(attempt_headers, "Range"):
                attempt_headers["Range"] = f"bytes={part_size}-"
            with requests.get(request_url, headers=attempt_headers, stream=True, allow_redirects=True, timeout=timeout) as response:
                if response.status_code >= 400:
                    raise DirectDownloadError(f"HTTP {response.status_code}: {request_url.split('?', 1)[0]}")
                append = part_size > 0 and response.status_code == 206
                mode = "ab" if append else "wb"
                with part_path.open(mode) as file_obj:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if cancel_callback and cancel_callback():
                            raise DirectDownloadError("download cancelled")
                        if chunk:
                            file_obj.write(chunk)
            part_path.replace(output_path)
            return True
        except DirectDownloadError as exc:
            last_error = exc
            if str(exc) == "download cancelled" or attempt + 1 >= max(1, retries):
                raise
        except requests.RequestException as exc:
            last_error = DirectDownloadError(str(exc))
            if attempt + 1 >= max(1, retries):
                raise last_error from exc
        except OSError as exc:
            last_error = DirectDownloadError(str(exc))
            if attempt + 1 >= max(1, retries):
                raise last_error from exc
        sleep(min(attempt + 1, 2))

    raise last_error or DirectDownloadError("direct download failed")


def _has_header(headers: dict[str, str], name: str) -> bool:
    return any(key.lower() == name.lower() for key in headers)
