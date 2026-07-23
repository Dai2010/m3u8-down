from __future__ import annotations

from pathlib import Path

import requests


class DirectDownloadError(RuntimeError):
    """Raised when a direct media URL cannot be saved."""


def download_direct_media(
    url: str,
    output_path: Path,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    chunk_size: int = 1024 * 1024,
    cancel_callback=None,
) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = output_path.with_name(f"{output_path.name}.part")
    request_headers = {key: value for key, value in (headers or {}).items() if value}

    try:
        with requests.get(url, headers=request_headers, stream=True, allow_redirects=True, timeout=timeout) as response:
            if response.status_code >= 400:
                raise DirectDownloadError(f"HTTP {response.status_code}: {url}")
            with part_path.open("wb") as file_obj:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if cancel_callback and cancel_callback():
                        raise DirectDownloadError("download cancelled")
                    if chunk:
                        file_obj.write(chunk)
        part_path.replace(output_path)
    except DirectDownloadError:
        part_path.unlink(missing_ok=True)
        raise
    except requests.RequestException as exc:
        part_path.unlink(missing_ok=True)
        raise DirectDownloadError(str(exc)) from exc
    except OSError as exc:
        part_path.unlink(missing_ok=True)
        raise DirectDownloadError(str(exc)) from exc
    return True
