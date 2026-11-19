"""Download the model weights listed in a manifest onto the network volume.

Usage: python ensure_weights.py <manifest.json> <root>

The manifest is a JSON list of {"path", "url", "size", "sha256"}. A file is
(re)downloaded when it is missing or its SHA-256 differs. Downloads go to
<root>/<path>.part, are hashed while streaming, and are renamed only when the
hash matches. A verified file gets a marker <path>.sha256 holding its digest:
on later starts a file with the right size and a matching marker is trusted
without re-hashing (the customer's GPU is billed while a cold start hashes 18 GB).
"""
import hashlib
import json
import os
import sys
import urllib.request

CHUNK = 8 * 1024 * 1024  # 8 MiB


def _sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _marker_path(dest):
    return dest + ".sha256"


def _write_marker(dest, digest):
    with open(_marker_path(dest), "w", encoding="utf-8") as f:
        f.write(digest + "\n")


def _has_marker(dest, digest):
    try:
        with open(_marker_path(dest), encoding="utf-8") as f:
            return f.read().strip() == digest
    except OSError:
        return False


def _is_current(dest, entry):
    # A size mismatch is already a wrong file: skip hashing 10 GB to find out.
    if not os.path.isfile(dest) or os.path.getsize(dest) != entry["size"]:
        return False
    if _has_marker(dest, entry["sha256"]):
        return True
    if _sha256_of(dest) != entry["sha256"]:
        return False
    _write_marker(dest, entry["sha256"])
    return True


def _download(entry, dest):
    part = dest + ".part"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(_marker_path(dest)):
        os.remove(_marker_path(dest))  # stale: it vouched for the file being replaced
    h = hashlib.sha256()
    try:
        with urllib.request.urlopen(entry["url"], timeout=60) as resp, open(part, "wb") as out:
            for chunk in iter(lambda: resp.read(CHUNK), b""):
                h.update(chunk)
                out.write(chunk)
        if h.hexdigest() != entry["sha256"]:
            raise ValueError("SHA-256 mismatch for %s" % entry["path"])
        os.replace(part, dest)
        _write_marker(dest, entry["sha256"])  # only once the rename succeeded
    except BaseException:
        if os.path.exists(part):
            os.remove(part)
        raise


def ensure_weights(manifest, root):
    """Make every file of the manifest present under root; return the paths downloaded."""
    with open(manifest, encoding="utf-8") as f:
        entries = json.load(f)
    root = os.path.realpath(root)
    downloaded = []
    for entry in entries:
        dest = os.path.realpath(os.path.join(root, entry["path"]))
        if os.path.commonpath([root, dest]) != root:
            raise ValueError("manifest path leaves the root: %s" % entry["path"])
        if _is_current(dest, entry):
            continue
        print("ensure_weights: downloading %s (%d bytes)" % (entry["path"], entry["size"]), flush=True)
        _download(entry, dest)
        downloaded.append(entry["path"])
    return downloaded


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: ensure_weights.py <manifest.json> <root>")
    done = ensure_weights(sys.argv[1], sys.argv[2])
    print("ensure_weights: %d file(s) downloaded, the rest already in place" % len(done), flush=True)
