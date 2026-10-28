# Third-Party Notices

This repository contains original orchestration/postprocessing code and a copy
of an official ComfyUI workflow. Model weights are **not** included.

## FLUX.2 Klein 9B base model

- Project: FLUX.2 Klein 9B
- Provider: Black Forest Labs
- Model card: https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9B
- License: see the model card and the license shipped with the model.

## Manga colorization LoRA

- Project: FLUX.2 Klein 9B - Manga Colorization LoRA by reference
- Author: thedeoxen
- Model card and workflow source:
  https://huggingface.co/thedeoxen/FLUX.2-klein-9B-manga-colorization-by-reference-LORA
- License: Apache-2.0 (as stated on the model card).
- The workflow file `workflows/flux2_manga_ui.json` is the upstream workflow from
  that model card, retained as the official fp8 reference. It is **not** covered
  by this repository's AGPL-3.0 license; it remains under Apache-2.0.

## Quantized FLUX.2 GGUF

- Project: FLUX.2-klein-base-9B-GGUF
- Provider: unsloth
- Model card: https://huggingface.co/unsloth/FLUX.2-klein-base-9B-GGUF
- License: see the model card.

## Text encoder and VAE

- Comfy-Org FLUX.2 Klein 9B files:
  https://huggingface.co/Comfy-Org/flux2-klein-9B
- Qwen text encoder: see the model card and the upstream Qwen license.
- FLUX.2 VAE: see the model card.

## ComfyUI

- Project: ComfyUI
- Source: https://github.com/comfyanonymous/ComfyUI
- License: GPL-3.0 (see upstream).

## ComfyUI-GGUF

- Project: ComfyUI-GGUF
- Source: https://github.com/city96/ComfyUI-GGUF
- License: see upstream.

## Sample assets

`examples/sample_page.webp`, `examples/sample_reference.jpg`, and
`examples/sample_output.png` are demonstration assets supplied for this project.
Character and artwork rights remain with their original rights holders. These
assets are not relicensed under AGPL-3.0; replace them before redistributing the
repository for a different purpose.
