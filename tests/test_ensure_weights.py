import hashlib
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import ensure_weights as ew
from ensure_weights import ensure_weights

FILES = {
    "diffusion_models/a.safetensors": b"alpha" * 1000,
    "vae/b.safetensors": b"bravo" * 500,
}


@pytest.fixture
def server():
    state = {"requests": [], "status": 200, "delay": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["requests"].append(self.path)
            if state["status"] != 200:
                self.send_response(state["status"])
                self.end_headers()
                return
            body = FILES[self.path.lstrip("/")]
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body[: len(body) // 2])
            self.wfile.flush()
            time.sleep(state["delay"])  # keeps two racing downloads overlapped
            self.wfile.write(body[len(body) // 2 :])

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    state["base"] = "http://127.0.0.1:%d" % httpd.server_port
    yield state
    httpd.shutdown()


@pytest.fixture
def manifest(server, tmp_path):
    entries = [
        {
            "path": path,
            "url": server["base"] + "/" + path,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        for path, data in FILES.items()
    ]
    p = tmp_path / "weights.json"
    p.write_text(json.dumps(entries))
    return str(p)


def test_downloads_missing_files(manifest, tmp_path):
    root = tmp_path / "models"
    got = ensure_weights(manifest, str(root))
    assert sorted(got) == sorted(FILES)
    for path, data in FILES.items():
        assert (root / path).read_bytes() == data
    assert not list(root.rglob("*.part*"))


def test_skips_files_with_the_right_hash(manifest, server, tmp_path):
    root = tmp_path / "models"
    ensure_weights(manifest, str(root))
    server["requests"].clear()
    assert ensure_weights(manifest, str(root)) == []
    assert server["requests"] == []


def test_replaces_a_file_with_the_wrong_hash(manifest, tmp_path):
    root = tmp_path / "models"
    target = root / "vae/b.safetensors"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x" * len(FILES["vae/b.safetensors"]))  # same size, other bytes
    assert ensure_weights(manifest, str(root)) == [
        "diffusion_models/a.safetensors",
        "vae/b.safetensors",
    ]
    assert target.read_bytes() == FILES["vae/b.safetensors"]


def test_leaves_no_part_file_after_a_failed_download(manifest, server, tmp_path):
    root = tmp_path / "models"
    target = root / "vae/b.safetensors"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    server["status"] = 500
    with pytest.raises(Exception):
        ensure_weights(manifest, str(root))
    assert not list(root.rglob("*.part*"))
    assert target.read_bytes() == b"old"


def test_refuses_a_download_whose_hash_does_not_match(server, tmp_path):
    path = "vae/b.safetensors"
    p = tmp_path / "weights.json"
    p.write_text(
        json.dumps(
            [{"path": path, "url": server["base"] + "/" + path, "size": 1, "sha256": "0" * 64}]
        )
    )
    root = tmp_path / "models"
    with pytest.raises(ValueError):
        ensure_weights(str(p), str(root))
    assert not (root / path).exists()
    assert not list(root.rglob("*.part*"))


def test_refuses_a_path_that_leaves_the_root(tmp_path):
    p = tmp_path / "weights.json"
    p.write_text(
        json.dumps([{"path": "../evil", "url": "http://127.0.0.1:1/x", "size": 1, "sha256": "0" * 64}])
    )
    with pytest.raises(ValueError):
        ensure_weights(str(p), str(tmp_path / "models"))
    assert not os.path.exists(tmp_path / "evil")


def _marker(root, path):
    return root / (path + ".sha256")


def _digest(path):
    return hashlib.sha256(FILES[path]).hexdigest()


def test_writes_the_marker_after_a_download(manifest, tmp_path):
    root = tmp_path / "models"
    ensure_weights(manifest, str(root))
    for path in FILES:
        assert _marker(root, path).read_text().strip() == _digest(path)


def test_trusts_a_verified_file_without_hashing(manifest, tmp_path, monkeypatch):
    root = tmp_path / "models"
    ensure_weights(manifest, str(root))

    def boom(path):
        raise AssertionError("hashed a verified file")

    monkeypatch.setattr(ew, "_sha256_of", boom)
    assert ensure_weights(manifest, str(root)) == []


def test_rehashes_when_the_size_changed(manifest, tmp_path):
    root = tmp_path / "models"
    ensure_weights(manifest, str(root))
    path = "vae/b.safetensors"
    (root / path).write_bytes(b"short")  # the marker still names the right digest
    assert ensure_weights(manifest, str(root)) == [path]
    assert (root / path).read_bytes() == FILES[path]


def test_rehashes_when_the_marker_names_another_digest(manifest, tmp_path, monkeypatch):
    root = tmp_path / "models"
    ensure_weights(manifest, str(root))
    path = "vae/b.safetensors"
    _marker(root, path).write_text("0" * 64)
    calls = []
    real = ew._sha256_of
    monkeypatch.setattr(ew, "_sha256_of", lambda p: calls.append(p) or real(p))
    assert ensure_weights(manifest, str(root)) == []  # the bytes are right: kept
    assert len(calls) == 1
    assert _marker(root, path).read_text().strip() == _digest(path)


def test_removes_a_stale_marker_before_redownloading(manifest, server, tmp_path):
    root = tmp_path / "models"
    ensure_weights(manifest, str(root))
    path = "vae/b.safetensors"
    (root / path).write_bytes(b"short")
    server["status"] = 500
    with pytest.raises(Exception):
        ensure_weights(manifest, str(root))
    assert not _marker(root, path).exists()


def _race(manifest, root, server, n=2):
    server["delay"] = 0.3
    results, errors = [], []

    def run():
        try:
            results.append(ensure_weights(manifest, str(root)))
        except BaseException as e:  # noqa: BLE001 - the test reports any failure
            errors.append(e)

    threads = [threading.Thread(target=run) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results, errors


def _assert_done_and_clean(root):
    for path, data in FILES.items():
        assert (root / path).read_bytes() == data
    assert not list(root.rglob("*.part*"))


def test_two_workers_racing_download_each_file_once(manifest, server, tmp_path):
    root = tmp_path / "models"
    results, errors = _race(manifest, root, server)
    assert errors == []
    # locks are per file, so the two may split the files, but none is downloaded twice
    assert sorted(path for r in results for path in r) == sorted(FILES)
    assert sorted(server["requests"]) == sorted("/" + p for p in FILES)
    _assert_done_and_clean(root)


def test_two_workers_racing_without_a_working_lock_do_not_corrupt_each_other(
    manifest, server, tmp_path, monkeypatch
):
    def no_flock(fd, op):
        raise OSError("flock not supported on this filesystem")

    monkeypatch.setattr(ew.fcntl, "flock", no_flock)
    root = tmp_path / "models"
    results, errors = _race(manifest, root, server)
    assert errors == []
    _assert_done_and_clean(root)


def _plant_part(root, path, name, age_s=0):
    part = root / (path + ".part." + name)
    part.parent.mkdir(parents=True, exist_ok=True)
    part.write_bytes(b"leftover of a killed worker")
    if age_s:
        t = time.time() - age_s
        os.utime(part, (t, t))
    return part


def test_removes_the_parts_a_crashed_worker_left_behind_under_the_lock(manifest, tmp_path):
    root = tmp_path / "models"
    stale = _plant_part(root, "vae/b.safetensors", "999.deadbeef")
    ensure_weights(manifest, str(root))
    assert not stale.exists()
    # also when the file itself is already in place
    again = _plant_part(root, "vae/b.safetensors", "1000.cafebabe")
    assert ensure_weights(manifest, str(root)) == []
    assert not again.exists()
    _assert_done_and_clean(root)


def test_without_a_lock_only_old_parts_are_removed(manifest, tmp_path, monkeypatch):
    def no_flock(fd, op):
        raise OSError("flock not supported on this filesystem")

    monkeypatch.setattr(ew.fcntl, "flock", no_flock)
    root = tmp_path / "models"
    fresh = _plant_part(root, "vae/b.safetensors", "1.fresh")  # maybe a live writer's
    old = _plant_part(root, "vae/b.safetensors", "2.old", age_s=7 * 3600)
    ensure_weights(manifest, str(root))
    assert fresh.exists()
    assert not old.exists()
