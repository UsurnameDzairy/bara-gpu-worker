FROM runpod/worker-comfyui:5.10.0-base

LABEL org.opencontainers.image.source="https://github.com/UsurnameDzairy/bara-gpu-worker" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

# The Wan 2.2 files live on the customer's network volume, not in the image.
# Replaces the base image's file: adds diffusion_models and text_encoders.
COPY src/extra_model_paths.yaml /comfyui/extra_model_paths.yaml
COPY weights.json /weights.json
COPY src/ /src/
RUN chmod +x /src/start.sh

CMD ["/src/start.sh"]
