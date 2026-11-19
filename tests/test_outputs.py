from outputs import first_mp4, returned_by_upstream_handler

# What ComfyUI 0.34.0's SaveVideo puts in the history: PreviewVideo.as_dict()
# (comfy_api/latest/_ui.py) = {"images": [SavedResult], "animated": (True,)}.
SAVE_VIDEO = {
    "58": {
        "images": [{"filename": "ComfyUI_00001_.mp4", "subfolder": "video", "type": "output"}],
        "animated": [True],
    }
}


def test_save_video_mp4_is_returned_under_images():
    got = returned_by_upstream_handler(SAVE_VIDEO)
    assert got == [{"filename": "ComfyUI_00001_.mp4", "subfolder": "video", "type": "output"}]


def test_temp_files_and_nameless_entries_are_not_returned():
    outputs = {
        "9": {
            "images": [
                {"filename": "preview.png", "subfolder": "", "type": "temp"},
                {"subfolder": "", "type": "output"},
                {"filename": "a.png", "subfolder": "", "type": "output"},
            ]
        }
    }
    assert [i["filename"] for i in returned_by_upstream_handler(outputs)] == ["a.png"]


def test_videos_and_gifs_keys_are_ignored_by_the_upstream_handler():
    outputs = {
        "1": {"videos": [{"filename": "a.mp4", "subfolder": "", "type": "output"}]},
        "2": {"gifs": [{"filename": "b.gif", "subfolder": "", "type": "output"}]},
    }
    assert returned_by_upstream_handler(outputs) == []


def test_first_mp4_reads_images():
    job = {"images": [{"filename": "a.png", "type": "base64", "data": "x"},
                      {"filename": "v.mp4", "type": "base64", "data": "y"}]}
    assert first_mp4(job)["filename"] == "v.mp4"


def test_first_mp4_reads_videos():
    job = {"videos": [{"filename": "v.mp4", "type": "base64", "data": "y"}]}
    assert first_mp4(job)["data"] == "y"


def test_first_mp4_ignores_a_png_and_a_gif():
    job = {"images": [{"filename": "a.PNG", "type": "base64", "data": "x"}],
           "videos": [{"filename": "b.gif", "type": "base64", "data": "x"}]}
    assert first_mp4(job) is None


def test_first_mp4_on_an_error_or_empty_output():
    assert first_mp4({"error": "boom", "details": ["x"]}) is None
    assert first_mp4({"status": "success_no_images", "images": []}) is None


def test_first_mp4_is_case_insensitive_on_the_extension():
    assert first_mp4({"images": [{"filename": "V.MP4", "type": "base64", "data": "y"}]}) is not None
