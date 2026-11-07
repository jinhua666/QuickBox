import hashlib
import io
import pytest

from quickbox.updates import parse_release, download_installer, UpdateError, _SafeRedirect


def release(version="0.2.0", body=b"installer"):
    return {"tag_name": "v" + version, "draft": False, "prerelease": False, "body": "New features",
            "assets": [{"name": f"QuickBox-Setup-{version}.exe", "state": "uploaded", "size": len(body),
                        "digest": "sha256:" + hashlib.sha256(body).hexdigest(),
                        "browser_download_url": f"https://github.com/jinhua666/QuickBox/releases/download/v{version}/QuickBox-Setup-{version}.exe"}]}


def test_latest_release_version_and_asset_are_checked():
    info = parse_release(release(), "0.1.0")
    assert info.version == "0.2.0" and info.notes == "New features"
    assert parse_release(release("0.1.0"), "0.1.0") is None
    data = release()
    data["assets"][0]["browser_download_url"] = "https://evil.example/update.exe"
    with pytest.raises(UpdateError):
        parse_release(data, "0.1.0")


def test_download_checks_hash_and_removes_invalid_file(tmp_path, monkeypatch):
    info = parse_release(release(), "0.1.0")
    monkeypatch.setattr("quickbox.updates._open_download", lambda url: io.BytesIO(b"tampered"))
    with pytest.raises(UpdateError):
        download_installer(info, directory=tmp_path)
    assert not list(tmp_path.rglob("*.exe"))
    monkeypatch.setattr("quickbox.updates._open_download", lambda url: io.BytesIO(b"installer"))
    path = download_installer(info, directory=tmp_path)
    assert path.read_bytes() == b"installer"


def test_rejects_prerelease_missing_hash_and_mismatched_asset():
    data = release()
    data["prerelease"] = True
    with pytest.raises(UpdateError):
        parse_release(data, "0.1.0")
    data = release()
    data["assets"][0]["digest"] = None
    with pytest.raises(UpdateError):
        parse_release(data, "0.1.0")


def test_rejects_insecure_or_untrusted_redirects():
    handler = _SafeRedirect()
    for url in ("http://github.com/foo", "https://attacker.example/file.exe"):
        with pytest.raises(UpdateError):
            handler.redirect_request(None, None, 302, "Found", {}, url)
