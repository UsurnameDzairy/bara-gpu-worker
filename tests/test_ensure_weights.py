import hashlib
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ensure_weights import ensure_weights

FILES = {
    "diffusion_models/a.safetensors": b"alpha" * 1000,
    "vae/b.safetensors": b"bravo" * 500,
}


@pytest.fixture
def server():
    state = {"requests": [], "status": 200}

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
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
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
    assert not list(root.rglob("*.part"))


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
    assert not list(root.rglob("*.part"))
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
    assert not list(root.rglob("*.part"))


def test_refuses_a_path_that_leaves_the_root(tmp_path):
    p = tmp_path / "weights.json"
    p.write_text(
        json.dumps([{"path": "../evil", "url": "http://127.0.0.1:1/x", "size": 1, "sha256": "0" * 64}])
    )
    with pytest.raises(ValueError):
        ensure_weights(str(p), str(tmp_path / "models"))
    assert not os.path.exists(tmp_path / "evil")
