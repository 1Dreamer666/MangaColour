**English** | [中文](README_ZH.md)

# MangaColour

**FLUX.2-powered manga colorization with reference-guided palette transfer,
clean line-art preservation, and consistent batch coloring.**

MangaColour takes a black-and-white manga page (or illustration) plus one color
reference and produces a full-resolution colorized page. The diffusion model
works on a small color layer; the final image keeps the **original full-resolution
luminance** (L channel), so line art, text, screentone, and speech-bubble borders
stay sharp.

This is a minimal, standalone extraction of the FLUX.2 workflow used for a
33-page colorization run. It is not a fork of the original MangaNinja project.

![sample](examples/sample_output.png)

## Features

- Reference-guided coloring with FLUX.2 Klein 9B + manga LoRA
- Two reference latents per target page: the page itself and one shared color
  reference
- L-preserving composite: original line art/text + model-predicted LAB chroma
- Batch support with resumable outputs and fixed seed for palette consistency
- Works on a 6 GB laptop GPU at 0.5 MP color resolution (batch 2 recommended)
- Core ComfyUI `LoadImage` + `/upload/image`; no VHS custom node required
- No model weights, outputs, secrets, or absolute paths committed

## Repository layout

```text
.
├─ README.md
├─ README_ZH.md                  # Chinese version
├─ config.example.json
├─ config/
│  └─ extra_model_paths.yaml     # portable ComfyUI model path config
├─ requirements.txt
├─ scripts/
│  ├─ check_setup.py
│  ├─ colorize.py
│  ├─ download_models.ps1
│  ├─ make_contact_sheet.py
│  └─ postprocess.py
├─ workflows/
│  ├─ flux2_manga_ui.json        # official fp8 UI reference, Apache-2.0
│  └─ flux2_manga_api.example.json
├─ examples/
│  ├─ sample_page.webp
│  ├─ sample_reference.jpg
│  └─ sample_output.png
├─ models/                       # local portable bundle; gitignored
├─ input/                        # local user pages; gitignored
├─ outputs/                      # generated; gitignored
├─ THIRD_PARTY_NOTICES.md
└─ LICENSE                       # AGPL-3.0
```

`models/`, `input/`, and `outputs/` are intentionally ignored by Git. A USB
copy should include the whole working directory, including `models/`; a plain
`git clone` does not contain the weights.

## How it works

1. Upload the target page(s) and one color reference to ComfyUI.
2. Encode the target page as reference latent #1 and the color reference as
   reference latent #2.
3. Sample with FLUX.2 Klein 9B + `manga_colorization.safetensors` using the
   `mngclranm` trigger.
4. Download the low-resolution color layer.
5. Convert both images to LAB, keep the original full-resolution L, and apply
   the predicted a/b chroma with a small guided filter.
6. Optionally clean cool/cyan drift from paper and speech bubbles (disabled by
   default in order to preserve bright skin highlights).

The default color pass is **0.5 MP** because the 9B model plus the Qwen text
encoder does not fit a 6 GB GPU at full page resolution. The final output remains
the original resolution.

## Requirements

- ComfyUI **0.31.0 or newer** with FLUX.2 nodes
- [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) for `UnetLoaderGGUF`
- Python 3.10+ for the helper scripts
- A running ComfyUI server (default `http://127.0.0.1:8000`)
- 6 GB VRAM minimum for the recommended 0.5 MP / batch 2 setting; 12 GB+ is
  recommended for larger batches or 1 MP

The UI workflow uses core `LoadImage` nodes and **does not contain VHS nodes**.
The API path also uses core `LoadImage`, so ComfyUI-VideoHelperSuite is not
required.

## Models

The scripts do not download weights automatically. This working copy already
contains the four required files in the local, gitignored `models/` tree, so a
USB copy of the whole `repo` directory is self-contained. Download only on a
fresh clone or if a file is missing:

```powershell
# Default destination: .\models
.\scripts\download_models.ps1

# Or download directly into ComfyUI's model root
.\scripts\download_models.ps1 -ModelsDir "C:\path\to\ComfyUI\models"
```

| File | ComfyUI folder | Size (bytes) | SHA256 |
|---|---|---:|---|
| `flux-2-klein-base-9b-Q3_K_M.gguf` | `diffusion_models/FLUX.2/` | 4,769,503,520 | `4F5FAD20886A9F9541151E4488BC26676E5FE6090371C95F3F4141F5AEC5CE70` |
| `qwen_3_8b_fp4mixed.safetensors` | `text_encoders/Qwen/` | 6,802,593,327 | `BBF16F981D98E16D080C566134814C4E9F6AADD0D0E1383C60BC44BA939D760D` |
| `flux2-vae.safetensors` | `vae/FLUX.2/` | 336,211,292 | `868FE7B343CC8F3A19DBCFCAFBC3D5F888802BE3F89BD81B65B3621A066CE8F3` |
| `manga_colorization.safetensors` | `loras/FLUX.2/` | 165,704,456 | `1206D0E28425E7A5323231E6501A65F5B64DCF7B1108E0749E8CB9F40E1C7FF8` |

Exact URLs are in `scripts/download_models.ps1` and
`THIRD_PARTY_NOTICES.md`.

Local portable layout:

```text
models/
├─ diffusion_models/FLUX.2/flux-2-klein-base-9b-Q3_K_M.gguf
├─ text_encoders/Qwen/qwen_3_8b_fp4mixed.safetensors
├─ vae/FLUX.2/flux2-vae.safetensors
└─ loras/FLUX.2/manga_colorization.safetensors
```

### Making models visible to ComfyUI

The repo includes `config/extra_model_paths.yaml`. Its `base_path` is
`../models`, relative to the config file, so it stays valid after the whole
folder is moved or copied to a USB drive:

```yaml
mangacolour:
  base_path: ../models
  diffusion_models: diffusion_models
  text_encoders: text_encoders
  vae: vae
  loras: loras
```

Launch ComfyUI with that extra config, or merge the same entry into ComfyUI's
existing model-path config:

```powershell
python main.py --extra-model-paths-config "<path-to-repo>/config/extra_model_paths.yaml"
```

If ComfyUI is already running, add the entry to its `extra_model_paths.yaml` and
restart. `check_setup.py` must list all four models before colorizing.

The model resolver in `colorize.py` accepts basenames, so it finds files even
when ComfyUI lists them with a subfolder such as `FLUX.2\...`. If a model is
missing, `check_setup.py` prints the available ComfyUI choices.

### Portable USB run

1. Copy the **entire** `repo` directory, including ignored `models/` (about
   11.2 GB); a `git clone` alone does not include weights.
2. On the target PC, make sure ComfyUI, ComfyUI-GGUF, and Python dependencies
   are installed.
3. Launch ComfyUI with `config/extra_model_paths.yaml`, then run:
   `python scripts/check_setup.py --config config.example.json`
4. Run the sample or your own pages. Keep `outputs/` local; it is ignored.

## Quick start

```powershell
python -m pip install -r requirements.txt

# 1. Verify ComfyUI, GGUF node, and the four models
python scripts/check_setup.py --config config.example.json

# 2. Colorize the bundled sample
python scripts/colorize.py --config config.example.json
```

Outputs:

```text
outputs/sample/
├─ sample_page.png       # full-resolution composite
├─ raw/sample_page.png   # raw low-resolution model color layer
├─ qa/sample_page_compare.jpg
├─ run.log
└─ summary.json
```

The committed `examples/sample_output.png` was generated with the command above.

> If ComfyUI is not running or any model is missing, `check_setup.py` exits with
> an explicit error. Do not treat the static checks as a successful end-to-end
> test.

## Single page and batch usage

Single page:

```powershell
python scripts/colorize.py `
  --config config.example.json `
  --pages examples/sample_page.webp `
  --reference examples/sample_reference.jpg `
  --output-dir outputs/single
```

Batch, with the same reference:

```powershell
python scripts/colorize.py `
  --config config.example.json `
  --input-dir pages `
  --glob "*.webp" `
  --reference examples/sample_reference.jpg `
  --output-dir outputs/pages `
  --batch-size 2
```

Pages already present in the output directory are skipped; use `--force` to
reprocess. Batch outputs are named after the input stems.

Contact sheet:

```powershell
python scripts/make_contact_sheet.py `
  --input-dir outputs/pages `
  --output outputs/pages/contact_sheet.jpg
```

Standalone L-composite (for an already generated raw color layer):

```powershell
python scripts/postprocess.py `
  --original page.webp `
  --color raw.png `
  --output final.png `
  --radius 2 --sat 1.0 --white-threshold 256
```

## Configuration and parameters

`config.example.json` contains the defaults. Command-line options override the
config file:

| Parameter | Default | Meaning |
|---|---:|---|
| `comfyui_url` / `--comfyui-url` | `http://127.0.0.1:8000` | ComfyUI server |
| `pages` / `--pages` | sample | Input page paths |
| `input_dir` / `--input-dir` | unset | Batch directory |
| `reference` / `--reference` | sample | One shared color reference |
| `output_dir` / `--output-dir` | `outputs/colorized` | Output root |
| `batch_size` / `--batch-size` | `1` (example) | Pages per diffusion batch |
| `megapixels` / `--megapixels` | `0.5` | Color-layer target size |
| `resolution_steps` / `--resolution-steps` | `16` | Size rounding for FLUX.2 |
| `steps` / `--steps` | `20` | Sampler steps |
| `cfg` / `--cfg` | `4.0` | CFG guidance |
| `seed` / `--seed` | `1234` | Fixed seed for palette consistency |
| `lora_strength` / `--lora-strength` | `1.0` | Manga LoRA strength |
| `prompt` / `--prompt` | `mngclranm` | LoRA trigger |
| `timeout` / `--timeout` | `3600` | Per-batch wait timeout, seconds |
| `postprocess.radius` | `2` | Guided-filter radius |
| `postprocess.sat` | `1.0` | Chroma saturation |
| `postprocess.white_threshold` | `256.0` | `256` disables paper/bubble cleanup |
| `postprocess.neutral_mask` | `false` | Optional neutral-pixel cleanup |

`--save-api-json path.json` saves the generated flat API graph for inspection.

## UI workflow

`workflows/flux2_manga_ui.json` is the **official fp8 workflow** from the LoRA
author, retained as a reference. It uses `UNETLoader` with
`flux-2-klein-base-9b-fp8.safetensors` and `qwen_3_8b_fp8mixed.safetensors`.
It is not the Q3 GGUF path used by the 6 GB scripts.

- For 6 GB VRAM, use the API scripts with the Q3 GGUF model.
- For a larger GPU, open the UI workflow and select the fp8 models.
- The UI workflow uses core `LoadImage`; it does **not** require VHS.
- Copy `examples/sample_page.webp` and `examples/sample_reference.jpg` into the
  ComfyUI `input/` directory before opening the UI workflow.

Source and license: see `THIRD_PARTY_NOTICES.md`. The UI workflow remains
Apache-2.0; the repository's AGPL-3.0 does not override it.

`workflows/flux2_manga_api.example.json` is a generated flat API graph for
inspection. Its `LoadImage` names are server-side uploaded names and will differ
on another machine; regenerate it with
`python scripts/colorize.py ... --save-api-json workflows/my_api.json`.

## Performance notes

Tested on an RTX 3060 Laptop (6 GB), ComfyUI 0.31.0, Q3 GGUF, 0.5 MP, 20 steps:

- batch 2: **8.4–9.4 min / 2 pages**, about **4.2–4.7 min/page**
- single page: about 5–6 min including model load; final single batch 5.3 min
- 1 MP single page: about 11.6 min
- 8-page batch: did not crash, but after about 41 minutes it had no output;
  ComfyUI reported `0.00 MB usable, 0.00 MB loaded, 4740.54 MB offloaded` and
  was thrashing weights from CPU. The test was aborted. Batch 2 is the practical
  setting on 6 GB.
- Larger batches may fit on 12 GB+ cards and can reduce fixed overhead, but the
  compute still scales with page count.

## Troubleshooting

**`check_setup.py` cannot connect**
Start ComfyUI and verify `comfyui_url`. The server must be reachable at
`/system_stats`.

**`UnetLoaderGGUF` not found**
Install/update [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF), restart
ComfyUI, then rerun `check_setup.py`.

**Model not found**
Run `python scripts/check_setup.py --config ...`; it prints installed choices.
The config uses basenames, but ComfyUI must see the files in its model paths.

**Upload errors**
The script posts to ComfyUI `/upload/image`. Check that ComfyUI's input directory
is writable.

**OOM or extremely slow sampling**
Use `--batch-size 1` or `2`, keep `--megapixels 0.5`, close other GPU programs,
and restart ComfyUI between long runs if VRAM becomes fragmented.

**Text or bubbles are tinted**
The default composite has paper/bubble cleanup disabled. Try
`--postprocess-white-threshold 94` (cool cleanup) or `--neutral-mask`, but
inspect bright skin highlights: aggressive masking can leave white holes.

## Licensing

- **Python scripts in this repository** (`scripts/*.py`): AGPL-3.0. See
  `LICENSE`.
- **`workflows/flux2_manga_ui.json`**: Apache-2.0, from the official LoRA
  repository at
  https://huggingface.co/thedeoxen/FLUX.2-klein-9B-manga-colorization-by-reference-LORA.
  It is not relicensed under AGPL-3.0.
- **`manga_colorization.safetensors` LoRA**: Apache-2.0 according to its model
  card; weights are not included in this repository.
- **FLUX.2, Qwen, VAE, and other model weights**: subject to their own model
  licenses; weights are not included.
- **Sample assets under `examples/`**: demonstration assets provided by the
  repository owner; character/artwork rights remain with their original rights
  holders. They are not AGPL-3.0 and should be replaced before any redistribution
  outside this demo.

This README does not give legal advice; verify model licenses before commercial
use.

## Acknowledgements

- Black Forest Labs for FLUX.2 Klein 9B
- thedeoxen for the manga colorization LoRA and official workflow
- unsloth for the Q3 GGUF quantization
- Comfy-Org for the ComfyUI-format text encoder/VAE files
- city96 for ComfyUI-GGUF
- The ComfyUI project

## 中文摘要

本项目把一次 Flux.2 漫画上色的最小流程独立出来：

- 输入一张黑白页和一张彩色参考图，使用 FLUX.2 Klein 9B + manga LoRA 上色
- 色度层默认在 0.5MP 生成，最终仍输出原图分辨率
- 用原图 L 通道保留线稿、文字、气泡和网点
- 支持单页、批量和断点续跑；6GB 显存建议 batch 2
- 模型权重不提交；按 README 下载并放入 ComfyUI 模型目录
- UI `workflows/flux2_manga_ui.json` 是官方 fp8 参考；6GB 实际运行使用
  API + Q3 GGUF 脚本

运行：

```powershell
python scripts/check_setup.py --config config.example.json
python scripts/colorize.py --config config.example.json
```
