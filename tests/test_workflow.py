import json
import os

ROOT = os.path.dirname(os.path.dirname(__file__))


def load(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return json.load(f)


def test_workflow_links_point_to_existing_nodes():
    wf = load("workflows/wan22_ti2v_5b.json")
    for node in wf.values():
        assert node["class_type"]
        for value in node["inputs"].values():
            if isinstance(value, list):
                assert value[0] in wf, value


def test_workflow_loads_only_files_listed_in_weights_json():
    wf = load("workflows/wan22_ti2v_5b.json")
    listed = {os.path.basename(e["path"]) for e in load("weights.json")}
    used = {
        wf["37"]["inputs"]["unet_name"],
        wf["38"]["inputs"]["clip_name"],
        wf["39"]["inputs"]["vae_name"],
    }
    assert used == listed


def test_workflow_makes_a_121_frame_24_fps_mp4():
    wf = load("workflows/wan22_ti2v_5b.json")
    latent, video, save = wf["55"]["inputs"], wf["57"]["inputs"], wf["58"]["inputs"]
    assert (latent["width"], latent["height"], latent["length"]) == (1280, 704, 121)
    assert video["fps"] == 24
    assert wf["58"]["class_type"] == "SaveVideo" and save["format"] == "mp4"


def test_weights_manifest_is_complete():
    for e in load("weights.json"):
        assert e["url"].startswith("https://huggingface.co/Comfy-Org/Wan-2.2/resolve/main/split_files/" + e["path"])
        assert len(e["sha256"]) == 64 and e["size"] > 0
