# bara-gpu-worker

A Runpod Serverless worker that generates video with Wan 2.2 TI2V-5B (text or
image to video, 1280x704 or 704x1280, 121 frames at 24 fps) through ComfyUI.
It is the image behind "Mon GPU" in Bara: each customer
deploys it on their own Runpod account, with their own network volume.

It is `runpod/worker-comfyui:5.10.0-base` (ComfyUI 0.34.0, upstream handler
unchanged) plus a start script that puts the model files on the volume first.

## Job contract

Input (the upstream worker's):

```json
{ "input": { "workflow": { "...": "ComfyUI workflow in API format" },
             "images": [{ "name": "start.png", "image": "<base64>" }] } }
```

`images` is optional: each entry is uploaded to ComfyUI's input folder so a
`LoadImage` node can use it by `name`.

Output:

```json
{ "images": [{ "filename": "ComfyUI_00001_.mp4", "type": "base64", "data": "<base64>" }],
  "videos": [{ "filename": "...", "type": "base64", "data": "<base64>" }],
  "errors": ["..."] }
```

A `SaveVideo` node's MP4 comes back under `images` (ComfyUI reports it as an
image-type output; the upstream handler returns that key only). `videos` is
accepted by the contract but not produced today. Consumers take the first item
whose `filename` ends in `.mp4`, under either key (`src/outputs.py`).
`workflows/wan22_ti2v_5b.json` is the text-to-video reference workflow; for
image-to-video add a `LoadImage` node and set the latent node's `start_image`
to its output.

## Weights

Nothing heavy is in the image. `src/start.sh` runs, before ComfyUI starts:

```
python /src/ensure_weights.py /weights.json /runpod-volume/models
```

For each file of `weights.json` (Hugging Face `Comfy-Org/Wan-2.2`, 18.1 GB in
total), it checks size and SHA-256, downloads what is missing or wrong to
`<path>.part`, verifies the hash while streaming, then renames. The first start
on an empty volume therefore downloads 18 GB; the next ones skip every file
whose size matches and whose `<path>.sha256` marker (written once the hash was
verified) holds the expected digest, so a cold start does not re-hash 18 GB.
Without a mounted `/runpod-volume` the container stops with a clear
message.

`src/extra_model_paths.yaml` replaces the base image's file so ComfyUI also
searches `models/diffusion_models` and `models/text_encoders` on the volume.

## Develop

```
python3 -m pytest -q
```

The image is built and published by CI on tags (no local `docker build` needed).

## Licences

AGPL-3.0 (this repository, like the base worker), GPL-3.0 (ComfyUI), Apache-2.0
(Wan 2.2 weights). Details and links in `NOTICE.md`.
