"""Public GitHub Release checks and integrity-checked installer downloads."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPOSITORY = "jinhua666/QuickBox"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MAX_INSTALLER_SIZE = 200 * 1024 * 1024
_VERSION = re.compile(r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")


class UpdateError(Exception):
    pass


@dataclass(frozen=True)
class Release:
    version: str
    notes: str
    url: str
    sha256: str
    size: int


def _version(value):
    match = _VERSION.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise UpdateError("版本号格式无效，请联系开发者。")
    return tuple(map(int, match.groups()))


def parse_release(data, current_version):
    if not isinstance(data, dict) or data.get("draft") is not False or data.get("prerelease") is not False:
        raise UpdateError("更新信息不是正式版本。")
    remote = _version(data.get("tag_name"))
    if remote <= _version(current_version):
        return None
    version = ".".join(map(str, remote))
    name = f"QuickBox-Setup-{version}.exe"
    assets = data.get("assets")
    if not isinstance(assets, list):
        raise UpdateError("更新信息缺少安装包。")
    matching = [asset for asset in assets if isinstance(asset, dict) and asset.get("name") == name and asset.get("state") == "uploaded"]
    if len(matching) != 1:
        raise UpdateError("没有找到唯一匹配的 Windows 安装包。")
    asset = matching[0]
    digest = asset.get("digest")
    size = asset.get("size")
    url = asset.get("browser_download_url")
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        raise UpdateError("安装包缺少有效的 SHA-256 校验值。")
    if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= MAX_INSTALLER_SIZE:
        raise UpdateError("安装包大小无效。")
    parsed = urlparse(url) if isinstance(url, str) else None
    tag = data["tag_name"]
    expected_path = f"/{REPOSITORY}/releases/download/{tag}/{name}"
    if not parsed or parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.path != expected_path or parsed.query or parsed.fragment:
        raise UpdateError("安装包地址不属于 QuickBox 官方仓库。")
    notes = data.get("body")
    return Release(version, notes if isinstance(notes, str) else "", url, digest[7:].lower(), size)


class _SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or parsed.hostname not in {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com", "api.github.com"} or parsed.port not in (None, 443):
            raise UpdateError("更新下载重定向到不受信任的地址。")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url, accept="application/vnd.github+json"):
    request = Request(url, headers={"Accept": accept, "User-Agent": "QuickBox-Updater", "X-GitHub-Api-Version": "2022-11-28"})
    return build_opener(_SafeRedirect()).open(request, timeout=20)


def _open_download(url):
    return _open(url, "application/octet-stream")


def check_latest(current_version):
    try:
        with _open(API_URL) as response:
            payload = response.read(1024 * 1024 + 1)
        if len(payload) > 1024 * 1024:
            raise UpdateError("更新信息过大。")
        return parse_release(json.loads(payload), current_version)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise UpdateError(f"GitHub 更新检查失败（HTTP {exc.code}）。") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise UpdateError("无法检查更新，请检查网络后重试。") from exc


def download_installer(release, directory=None):
    target_dir = Path(tempfile.mkdtemp(prefix="quickbox-update-", dir=directory))
    target = target_dir / f"QuickBox-Setup-{release.version}.exe"
    total = 0
    digest = hashlib.sha256()
    try:
        with _open_download(release.url) as response, target.open("xb") as output:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                total += len(chunk)
                if total > release.size or total > MAX_INSTALLER_SIZE:
                    raise UpdateError("下载的安装包大小不匹配。")
                digest.update(chunk)
                output.write(chunk)
        if total != release.size or digest.hexdigest() != release.sha256:
            raise UpdateError("安装包校验失败，已丢弃下载文件。")
        return target
    except Exception as exc:
        shutil.rmtree(target_dir, ignore_errors=True)
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError("下载更新失败，请检查网络或磁盘空间。") from exc
