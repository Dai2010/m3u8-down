from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

import requests

from .parser import Segment

ProgressCallback = Callable[[int, int], None]


class DownloadError(RuntimeError):
    """Raised when one or more segments cannot be downloaded."""


class Downloader:
    def __init__(self, threads: int = 16, headers: Optional[dict[str, str]] = None, retries: int = 3, timeout: int = 30):
        self.threads = max(1, threads)
        self.headers = headers or {}
        self.retries = max(0, retries)
        self.timeout = timeout

    def download(
        self,
        segments: list[Segment],
        output_dir: Path,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        total = len(segments)
        done = 0
        results: list[Optional[Path]] = [None] * total
        failures: list[str] = []

        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {
                executor.submit(self._download_one, index, segment, output_dir): index
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

    def _download_one(self, index: int, segment: Segment, output_dir: Path) -> Path:
        final_path = output_dir / f"{index:05d}.ts"
        part_path = output_dir / f"{index:05d}.ts.part"
        if final_path.exists() and final_path.stat().st_size > 0:
            return final_path

        last_error: Optional[Exception] = None
        for _ in range(self.retries + 1):
            try:
                with requests.get(segment.url, headers=self.headers, stream=True, timeout=self.timeout) as response:
                    response.raise_for_status()
                    with part_path.open("wb") as file_obj:
                        for chunk in response.iter_content(chunk_size=1024 * 256):
                            if chunk:
                                file_obj.write(chunk)
                part_path.replace(final_path)
                return final_path
            except Exception as exc:  # noqa: BLE001 - retry network and filesystem failures uniformly.
                last_error = exc
                if part_path.exists():
                    part_path.unlink(missing_ok=True)
        raise DownloadError(str(last_error) if last_error else "unknown download error")
