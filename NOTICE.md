# Notice

This repository is licensed under the GNU Affero General Public License v3.0
(see `LICENSE`). It builds on third-party software and models:

| Component | Used as | Licence | Source |
|---|---|---|---|
| `runpod/worker-comfyui` 5.10.0 | base image (handler, start script, `extra_model_paths.yaml`, which `src/extra_model_paths.yaml` copies with two added lines) | AGPL-3.0 | https://github.com/runpod-workers/worker-comfyui/tree/5.10.0 |
| ComfyUI 0.34.0 | the engine inside the base image | GPL-3.0 | https://github.com/comfyanonymous/ComfyUI |
| Wan 2.2 TI2V-5B, its VAE and the UMT5-XXL text encoder (repackaged by Comfy-Org) | weights downloaded at first start onto the customer's network volume, never baked into the image | Apache-2.0 | https://huggingface.co/Comfy-Org/Wan-2.2 |
| Wan 2.2 (original model) | | Apache-2.0 | https://github.com/Wan-Video/Wan2.2 |

`workflows/wan22_ti2v_5b.json` is written from ComfyUI's built-in "Wan 2.2 5B
text/image to video" template (`comfyui-workflow-templates`), GPL-3.0 like
ComfyUI.

The Dockerfile is a thin layer: it adds `weights.json`, `src/` and one
`extra_model_paths.yaml`. The upstream handler is used unmodified.
