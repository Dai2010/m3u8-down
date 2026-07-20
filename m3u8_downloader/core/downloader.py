from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import sleep
from typing import Callable, Optional

import requests

from .bilibili import is_bilibili_url, prepare_bilibili_request, throttle_bilibili_request
from .parser import Segment

ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]


class DownloadError(RuntimeError):
    """Raised when one or more segments cannot be downloaded."""

    def __init__(self, message: str, status_code: int | None = None, retryable: bool = True):
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(message)


class Downloader:
    def __init__(
        self,
        threads: int = 16,
        headers: Optional[dict[str, str]] = None,
        retries: int = 3,
        timeout: int = 30,
        bilibili_compat: bool = False,
    ):
        self.threads = max(1, threads)
        self.headers = headers or {}
        self.retries = max(0, retries)
        self.timeout = timeout
        self.bilibili_compat = bilibili_compat

    def download(
        self,
        segments: list[Segment],
        output_dir: Path,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_callback: Optional[CancelCallback] = None,
    ) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        total = len(segments)
        done = 0
        results: list[Optional[Path]] = [None] * total
        failures: list[str] = []

        is_bilibili_traffic = self.bilibili_compat or any(is_bilibili_url(segment.url) for segment in segments)
        worker_count = min(self.threads, 2) if is_bilibili_traffic else self.threads
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(self._download_one, index, segment, output_dir, cancel_callback): index
                for index, segment in enumerate(segments)
            }
            for future in as_completed(futures):
                index = futures[future]
                try:
                    results[index] = future.result()
                except Exception as exc:  # noqa: BLE001 - collect all failed URLs for caller context.
                    failures.append(f"{segments[index].url}: {exc}")
                done += 1
                if progress_callback:
                    progress_callback(done, total)

        if failures:
            raise DownloadError("failed to download segments: " + "; ".join(failures))
        return [path for path in results if path is not None]

    def _download_one(self, index: int, segment: Segment, output_dir: Path, cancel_callback: Optional[CancelCallback]) -> Path:
        final_path = output_dir / f"{index:05d}.ts"
        part_path = output_dir / f"{index:05d}.ts.part"
        if final_path.exists() and final_path.stat().st_size > 0:
            return final_path

        last_error: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            if cancel_callback and cancel_callback():
                raise DownloadError("download cancelled", retryable=False)
            try:
                request_url, request_headers = prepare_bilibili_request(segment.url, self.headers, self.bilibili_compat)
                throttle_bilibili_request(request_url)
                with requests.get(request_url, headers=request_headers, stream=True, timeout=self.timeout) as response:
                    status_code = getattr(response, "status_code", 200)
                    if status_code >= 400:
                        retryable = status_code not in {401, 403, 404, 410, 429}
                        message = "B 站请求过于频繁，请暂停操作后再试" if status_code == 429 else f"HTTP {status_code}: {request_url}"
                        raise DownloadError(message, status_code=status_code, retryable=retryable)
                    with part_path.open("wb") as file_obj:
                        for chunk in response.iter_content(chunk_size=1024 * 256):
                            if cancel_callback and cancel_callback():
                                raise DownloadError("download cancelled", retryable=False)
                            if chunk:
                                file_obj.write(chunk)
                part_path.replace(final_path)
                return final_path
            except Exception as exc:  # noqa: BLE001 - retry network and filesystem failures uniformly.
                last_error = exc
                if part_path.exists():
                    part_path.unlink(missing_ok=True)
                if isinstance(exc, DownloadError) and not exc.retryable:
                    raise
                if attempt < self.retries:
                    sleep(_retry_delay(attempt))
        raise DownloadError(str(last_error) if last_error else "unknown download error")


def _retry_delay(attempt: int) -> float:
    return min(8.0, 0.75 * (2**attempt))
