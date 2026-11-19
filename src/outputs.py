"""Pure helpers for the video contract (no runpod / websocket imports).

The worker runs the unmodified upstream handler of runpod/worker-comfyui 5.10.0.
Its output collection (handler.py, "for node_id, node_output in outputs.items()")
returns only entries under a node's "images" key, skips type "temp" and entries
without a filename, and ignores every other key ("videos", "gifs", ...).
ComfyUI 0.34.0's SaveVideo reports its file under "images", so the MP4 comes
back under "images". `returned_by_upstream_handler` models that rule so the
tests pin it; `first_mp4` is the rule Bara applies to the job output.
"""


def returned_by_upstream_handler(history_outputs):
    """The history entries the upstream handler turns into job output items."""
    return [
        info
        for node_output in history_outputs.values()
        for info in node_output.get("images", [])
        if info.get("filename") and info.get("type") != "temp"
    ]


def first_mp4(job_output):
    """First item whose filename ends in .mp4, under "images" or "videos"."""
    for key in ("images", "videos"):
        for item in job_output.get(key) or []:
            if str(item.get("filename", "")).lower().endswith(".mp4"):
                return item
    return None
