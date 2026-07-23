from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from time import sleep
from collections.abc import Iterable
import re
from urllib.parse import urlsplit

import requests

from .bilibili import bilibili_media_url_variants, prepare_bilibili_request, throttle_bilibili_request


class DirectDownloadError(RuntimeError):
    """Raised when a direct media URL cannot be saved."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retryable: bool = True,
        category: str = "download",
        content_type: str = "",
        expected_bytes: int | None = None,
        actual_bytes: int | None = None,
        resumed: bool = False,
        attempts: tuple["DirectDownloadAttempt", ...] = (),
    ):
        self.status_code = status_code
        self.retryable = retryable
        self.category = category
        self.content_type = content_type
        self.expected_bytes = expected_bytes
        self.actual_bytes = actual_bytes
        self.resumed = resumed
        self.attempts = attempts
        super().__init__(message)

    def with_attempts(self, attempts: list["DirectDownloadAttempt"]) -> "DirectDownloadError":
        return DirectDownloadError(
            str(self),
            status_code=self.status_code,
            retryable=self.retryable,
            category=self.category,
            content_type=self.content_type,
            expected_bytes=self.expected_bytes,
            actual_bytes=self.actual_bytes,
            resumed=self.resumed,
            attempts=tuple(attempts),
        )


@dataclass(frozen=True)
class DirectDownloadAttempt:
    index: int
    scheme: str
    host: str
    port: int | None
    status_code: int | None
    content_type: str
    expected_bytes: int | None
    actual_bytes: int | None
    content_range: str
    resumed: bool
    has_cookie: bool
    has_range: bool
    response_sha256: str

    def redacted_description(self) -> str:
        endpoint = f"{self.scheme or '?'}://{self.host or '?'}"
        if self.port is not None:
            endpoint += f":{self.port}"
        return (
            f"#{self.index} {endpoint} status={self.status_code or 'unknown'} "
            f"type={self.content_type or 'unknown'} length={self.expected_bytes if self.expected_bytes is not None else 'unknown'} "
            f"actual={self.actual_bytes if self.actual_bytes is not None else 'unknown'} "
            f"range={self.content_range or 'none'} resumed={'yes' if self.resumed else 'no'} "
            f"cookie={'yes' if self.has_cookie else 'no'} request_range={'yes' if self.has_range else 'no'} "
            f"sha256={self.response_sha256 or 'unknown'}"
        )


def download_direct_media(
    url: str,
    output_path: Path,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    chunk_size: int = 1024 * 1024,
    cancel_callback=None,
    bilibili_compat: bool = False,
    retries: int = 3,
    backup_urls: Iterable[str] = (),
    progress_callback=None,
    preserve_bilibili_media_url: bool = False,
) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = output_path.with_name(f"{output_path.name}.part")
    source_urls = tuple(dict.fromkeys(source for source in (url, *backup_urls) if source))
    if preserve_bilibili_media_url:
        source_urls = tuple(dict.fromkeys(variant for source in source_urls for variant in bilibili_media_url_variants(source)))
    request_url, request_headers = prepare_bilibili_request(source_urls[0], headers, bilibili_compat)
    last_error: DirectDownloadError | None = None
    attempts: list[DirectDownloadAttempt] = []

    for attempt in range(max(1, retries)):
        attempt_has_retryable_error = False
        for source_index, source_url in enumerate(source_urls, start=1):
            try:
                request_url, request_headers = prepare_bilibili_request(source_url, headers, bilibili_compat)
                part_size = part_path.stat().st_size if part_path.exists() else 0
                attempt_headers = dict(request_headers)
                if part_size and not _has_header(attempt_headers, "Range"):
                    attempt_headers["Range"] = f"bytes={part_size}-"
                throttle_bilibili_request(request_url)
                if preserve_bilibili_media_url and _is_bilibili_media_url(source_url):
                    request_url = source_url
                clean_retry_used = False
                while True:
                    with requests.get(request_url, headers=attempt_headers, stream=True, allow_redirects=True, timeout=timeout) as response:
                        response_headers = getattr(response, "headers", {}) or {}
                        if response.status_code == 416 and part_size > 0 and not clean_retry_used:
                            summary = _summarize_response(response)
                            attempts.append(
                                _build_attempt(
                                    source_index,
                                    request_url,
                                    response,
                                    part_size,
                                    attempt_headers,
                                    summary,
                                )
                            )
                            part_path.unlink(missing_ok=True)
                            part_size = 0
                            attempt_headers.pop("Range", None)
                            clean_retry_used = True
                            continue
                        if response.status_code >= 400:
                            retryable = response.status_code not in {401, 403, 404, 410, 429}
                            summary = _summarize_response(response)
                            attempts.append(
                                _build_attempt(
                                    source_index,
                                    request_url,
                                    response,
                                    part_size,
                                    attempt_headers,
                                    summary,
                                )
                            )
                            raise DirectDownloadError(
                                f"HTTP {response.status_code}: {_safe_url(request_url)}",
                                status_code=response.status_code,
                                retryable=retryable,
                                category="download_http",
                                content_type=_header(response_headers, "Content-Type"),
                                expected_bytes=_content_length(response_headers),
                                actual_bytes=summary[0],
                                resumed=part_size > 0,
                            )
                        content_type = _header(response_headers, "Content-Type")
                        _validate_content_type(content_type, request_url, response.status_code, part_size > 0)
                        chunk_path = part_path.with_name(f"{part_path.name}.chunk")
                        try:
                            chunk_path.unlink(missing_ok=True)
                            actual_bytes = 0
                            digest = sha256()
                            with chunk_path.open("wb") as chunk_file:
                                for chunk in response.iter_content(chunk_size=chunk_size):
                                    if cancel_callback and cancel_callback():
                                        raise DirectDownloadError("download cancelled")
                                    if chunk:
                                        chunk_file.write(chunk)
                                        digest.update(chunk)
                                        actual_bytes += len(chunk)
                            summary = (actual_bytes, digest.hexdigest())
                            attempts.append(
                                _build_attempt(
                                    source_index,
                                    request_url,
                                    response,
                                    part_size,
                                    attempt_headers,
                                    summary,
                                )
                            )
                            _validate_response(response, response.status_code, actual_bytes, part_size, request_url, content_type)
                            _validate_body_prefix(chunk_path, request_url, response.status_code, part_size > 0)
                            append = part_size > 0 and response.status_code == 206
                            if append:
                                with part_path.open("ab") as part_file, chunk_path.open("rb") as chunk_file:
                                    while True:
                                        data = chunk_file.read(chunk_size)
                                        if not data:
                                            break
                                        part_file.write(data)
                            else:
                                chunk_path.replace(part_path)
                            if part_path.stat().st_size <= 0:
                                raise DirectDownloadError(
                                    f"empty media response: {_safe_url(request_url)}",
                                    status_code=response.status_code,
                                    category="download_body",
                                    content_type=content_type,
                                    actual_bytes=actual_bytes,
                                    resumed=part_size > 0,
                                )
                            if progress_callback:
                                progress_callback(part_path.stat().st_size)
                        finally:
                            chunk_path.unlink(missing_ok=True)
                    break
                part_path.replace(output_path)
                return True
            except DirectDownloadError as exc:
                last_error = exc.with_attempts(attempts)
                if str(exc) == "download cancelled":
                    raise
                if exc.status_code == 429:
                    raise
                attempt_has_retryable_error = attempt_has_retryable_error or exc.retryable
            except requests.RequestException as exc:
                last_error = DirectDownloadError(str(exc))
                attempt_has_retryable_error = True
            except OSError as exc:
                last_error = DirectDownloadError(str(exc))
                attempt_has_retryable_error = True
        if last_error and not attempt_has_retryable_error:
            raise last_error
        if attempt + 1 >= max(1, retries):
            raise last_error or DirectDownloadError("direct download failed")
        sleep(_retry_delay(attempt))

    raise last_error or DirectDownloadError("direct download failed")


def _validate_content_type(content_type: str, url: str, status_code: int, resumed: bool) -> None:
    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized in {"text/html", "text/plain", "application/json", "application/xml", "text/xml"}:
        raise DirectDownloadError(
            f"non-media response ({normalized}): {_safe_url(url)}",
            status_code=status_code,
            retryable=False,
            category="download_body",
            content_type=normalized,
            resumed=resumed,
        )


def _validate_response(response, status_code: int, actual_bytes: int, part_size: int, url: str, content_type: str) -> None:
    expected_bytes = _content_length(getattr(response, "headers", {}) or {})
    if expected_bytes is not None and expected_bytes != actual_bytes:
        raise DirectDownloadError(
            f"response length mismatch ({expected_bytes}!={actual_bytes}): {_safe_url(url)}",
            status_code=status_code,
            category="download_body",
            content_type=content_type,
            expected_bytes=expected_bytes,
            actual_bytes=actual_bytes,
            resumed=part_size > 0,
        )
    if status_code != 206:
        return
    content_range = _header(getattr(response, "headers", {}) or {}, "Content-Range")
    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", content_range.strip(), re.IGNORECASE)
    if not match:
        raise DirectDownloadError(
            f"invalid Content-Range: {_safe_url(url)}",
            status_code=status_code,
            category="download_body",
            content_type=content_type,
            actual_bytes=actual_bytes,
            resumed=part_size > 0,
        )
    start, end = int(match.group(1)), int(match.group(2))
    total = None if match.group(3) == "*" else int(match.group(3))
    if start != part_size or end < start or end - start + 1 != actual_bytes or (total is not None and end >= total):
        raise DirectDownloadError(
            f"Content-Range does not match partial file: {_safe_url(url)}",
            status_code=status_code,
            category="download_body",
            content_type=content_type,
            expected_bytes=end - start + 1,
            actual_bytes=actual_bytes,
            resumed=part_size > 0,
        )
    if total is not None and part_size + actual_bytes != total:
        raise DirectDownloadError(
            f"partial response is incomplete: {_safe_url(url)}",
            status_code=status_code,
            category="download_body",
            content_type=content_type,
            expected_bytes=total - part_size,
            actual_bytes=actual_bytes,
            resumed=part_size > 0,
        )


def _validate_body_prefix(path: Path, url: str, status_code: int, resumed: bool) -> None:
    prefix = path.read_bytes()[:256].decode("utf-8", errors="ignore").lstrip().lower()
    if prefix.startswith(("<html", "<!doctype", "{", "[")):
        raise DirectDownloadError(
            f"response body looks like an error page: {_safe_url(url)}",
            status_code=status_code,
            retryable=False,
            category="download_body",
            resumed=resumed,
        )


def _content_length(headers) -> int | None:
    value = _header(headers, "Content-Length")
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _summarize_response(response) -> tuple[int, str]:
    digest = sha256()
    actual_bytes = 0
    try:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if chunk:
                digest.update(chunk)
                actual_bytes += len(chunk)
    except Exception:
        return actual_bytes, ""
    return actual_bytes, digest.hexdigest()


def _build_attempt(index: int, url: str, response, part_size: int, request_headers: dict[str, str], summary: tuple[int, str]) -> DirectDownloadAttempt:
    parsed = urlsplit(url)
    content_type = _header(getattr(response, "headers", {}) or {}, "Content-Type").split(";", 1)[0].strip().lower()
    port = parsed.port
    return DirectDownloadAttempt(
        index=index,
        scheme=parsed.scheme,
        host=parsed.hostname or "",
        port=port,
        status_code=getattr(response, "status_code", None),
        content_type=content_type,
        expected_bytes=_content_length(getattr(response, "headers", {}) or {}),
        actual_bytes=summary[0],
        content_range=_header(getattr(response, "headers", {}) or {}, "Content-Range"),
        resumed=part_size > 0,
        has_cookie=_has_header(request_headers, "Cookie"),
        has_range=_has_header(request_headers, "Range"),
        response_sha256=summary[1],
    )


def _header(headers, name: str) -> str:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return str(value)
    return ""


def _is_bilibili_media_url(url: str) -> bool:
    return ".m4s" in url.split("?", 1)[0].lower() and "bilivideo" in url.lower()


def _safe_url(url: str) -> str:
    return url.split("?", 1)[0]


def _has_header(headers: dict[str, str], name: str) -> bool:
    return any(key.lower() == name.lower() for key in headers)


def _retry_delay(attempt: int) -> float:
    return min(8.0, 0.75 * (2**attempt))
