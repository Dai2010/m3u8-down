from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Callable
from urllib.parse import urlsplit

import requests

from .bilibili import DEFAULT_BILIBILI_REFERER, DEFAULT_BILIBILI_USER_AGENT


WEB_QR_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate?source=main-fe-header"
WEB_QR_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
LOGIN_COOKIE_KEYS = frozenset({
    "DedeUserID",
    "DedeUserID__ckMd5",
    "SESSDATA",
    "bili_jct",
    "sid",
})


class BilibiliLoginError(RuntimeError):
    pass


@dataclass(frozen=True)
class BilibiliLoginResult:
    cookie: str
    qr_code_path: Path


def login_bilibili_web_qr(
    qr_code_path: Path,
    status_callback: Callable[[str], None] | None = None,
    cancel_callback: Callable[[], bool] | None = None,
    http: requests.Session | None = None,
    poll_interval: float = 2.0,
    timeout: float = 180.0,
    show_console_qr: bool = False,
    qr_code_callback: Callable[[Path], None] | None = None,
) -> BilibiliLoginResult:
    client = http or requests.Session()
    headers = {
        "User-Agent": DEFAULT_BILIBILI_USER_AGENT,
        "Referer": DEFAULT_BILIBILI_REFERER,
    }
    payload = _request_json(client, WEB_QR_GENERATE_URL, headers=headers)
    data = payload.get("data") or {}
    login_url = str(data.get("url") or "")
    qrcode_key = str(data.get("qrcode_key") or "")
    if not login_url or not qrcode_key:
        raise BilibiliLoginError("B 站没有返回二维码登录信息")

    qr_code_path.parent.mkdir(parents=True, exist_ok=True)
    _write_qr_code(login_url, qr_code_path)
    if qr_code_callback:
        qr_code_callback(qr_code_path)
    message = f"二维码已保存到：{qr_code_path}"
    if show_console_qr:
        message += f"\n请使用手机扫描下方二维码：\n{_console_qr_code(login_url)}"
    _notify(status_callback, message)

    deadline = timeout + _monotonic_seconds()
    scanned = False
    while _monotonic_seconds() < deadline:
        if cancel_callback and cancel_callback():
            raise BilibiliLoginError("二维码登录已取消")
        payload = _request_json(
            client,
            WEB_QR_POLL_URL,
            params={"qrcode_key": qrcode_key, "source": "main-fe-header"},
            headers=headers,
        )
        data = payload.get("data") or {}
        code = int(data.get("code", -1))
        if code == 86101:
            _notify(status_callback, "等待扫描 B 站登录二维码")
        elif code == 86090:
            if not scanned:
                _notify(status_callback, "二维码已扫描，等待确认")
                scanned = True
        elif code == 0:
            cookie = _cookie_from_login_url(str(data.get("url") or ""))
            if not cookie:
                raise BilibiliLoginError("登录成功但没有获取到有效 Cookie")
            _notify(status_callback, "B 站登录成功")
            return BilibiliLoginResult(cookie, qr_code_path)
        elif code == 86038:
            raise BilibiliLoginError("B 站登录二维码已过期")
        else:
            message = str(data.get("message") or payload.get("message") or code)
            raise BilibiliLoginError(f"B 站二维码登录失败：{message}")
        sleep(max(0.2, poll_interval))
    raise BilibiliLoginError("B 站二维码登录超时")


def _write_qr_code(value: str, path: Path) -> None:
    try:
        import qrcode
        qrcode.make(value).save(path)
    except ImportError as exc:
        raise BilibiliLoginError("二维码登录需要 qrcode 依赖") from exc


def _console_qr_code(value: str) -> str:
    try:
        import qrcode
    except ImportError as exc:
        raise BilibiliLoginError("二维码登录需要 qrcode 依赖") from exc
    code = qrcode.QRCode(border=1)
    code.add_data(value)
    code.make(fit=True)
    matrix = code.get_matrix()
    return "\n".join("".join("██" if cell else "  " for cell in row) for row in matrix)


def _request_json(
    client: requests.Session,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, str] | None = None,
) -> dict:
    response = None
    try:
        response = client.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return _json_object(response, "B 站登录接口返回无效")
    except requests.RequestException as exc:
        raise BilibiliLoginError("B 站登录网络请求失败") from exc
    finally:
        if response is not None:
            response.close()


def _cookie_from_login_url(value: str) -> str:
    query = urlsplit(value).query
    parts = []
    for item in query.split("&"):
        key, separator, raw_value = item.partition("=")
        if separator and key in LOGIN_COOKIE_KEYS:
            parts.append(f"{key}={raw_value}")
    return "; ".join(parts) if "SESSDATA" in {item.split("=", 1)[0] for item in parts} else ""


def _json_object(response: requests.Response, message: str) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise BilibiliLoginError(message) from exc
    if not isinstance(payload, dict):
        raise BilibiliLoginError(message)
    return payload


def _notify(callback: Callable[[str], None] | None, message: str) -> None:
    if callback:
        callback(message)


def _monotonic_seconds() -> float:
    from time import monotonic

    return monotonic()
