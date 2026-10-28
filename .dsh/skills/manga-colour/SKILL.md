---
name: manga-colour
description: "Use when the user requests 漫画上色, Flux.2 上色, 参考图配色迁移, 批量上色, manga colorization, reference-guided palette transfer, or batch coloring with this repository's ComfyUI/FLUX.2 workflow; load this skill before running any colorization command."
---

## 1. Prerequisites

Run from the repository root. Do not queue a colorization job until every gate passes.

1. Install the helper dependencies:
   `python -m pip install -r requirements.txt`
2. The portable copy should already contain the four model files under `models/`. Start ComfyUI with the repo-local path config, or merge its `mangacolour` entry into ComfyUI's existing config:
   `python main.py --extra-model-paths-config "<path-to-repo>/config/extra_model_paths.yaml"`
   The config uses `base_path: ../models`, so it remains valid after the repo is moved.
3. Check ComfyUI, ComfyUI-GGUF, the core FLUX.2 nodes, and the four configured model names:
   `python scripts/check_setup.py --config config.example.json`
   Add `--comfyui-url <url>` if ComfyUI is not on the configured URL, and use that same URL for the run.
4. If `scripts/check_setup.py` cannot connect, stop and report that ComfyUI is unavailable. If it reports a missing model, ask the user to run:
   `.\scripts\download_models.ps1`
   or, to write into a ComfyUI-visible model root:
   `.\scripts\download_models.ps1 -ModelsDir <ComfyUI-model-root>`
   The downloader verifies size and SHA256. Make sure ComfyUI can see that directory, restart ComfyUI, then rerun `scripts/check_setup.py`. If `UnetLoaderGGUF` is missing, install or update ComfyUI-GGUF and restart ComfyUI; do not substitute a different loader. Do not fabricate model files or begin a run before the check prints `Setup check passed.`
5. A plain `git clone` has no model weights. A USB copy must include the gitignored `models/` directory as well as the tracked files; do not “clean” it out of the portable copy.
6. Use the Q3 GGUF API path for 6 GB VRAM. Treat `workflows/flux2_manga_ui.json` as the official fp8 UI reference only; it is not the 6 GB execution path.
7. Confirm the demo inputs exist before using a demo command: `examples/sample_page.webp` and `examples/sample_reference.jpg`. For real pages, use the paths supplied by the user and do not add them to the repository.

## 2. Single-page colorization

Use the checked-in sample for a smoke test:

```powershell
python scripts/colorize.py --config config.example.json --pages examples/sample_page.webp --reference examples/sample_reference.jpg --output-dir outputs/single
```

That command performs the pipeline in order:

1. **Upload:** `scripts/colorize.py` uploads the page and reference to ComfyUI `/upload/image`.
2. **API workflow:** The same script builds the FLUX.2 API graph from `config.example.json`. `workflows/flux2_manga_api.example.json` is a generated reference graph only, and its `LoadImage` names are server-side uploaded names; do not treat them as local files or use the UI JSON for this API run.
3. **Submit and poll:** The script posts the graph to `/prompt` and polls `/history/<prompt_id>` with the configured `timeout`.
4. **Download:** The raw color layer is downloaded via `/view` to `outputs/single/raw/sample_page.png`.
5. **Composite:** The script uses the `composite` function from `scripts/postprocess.py` for the L-preserving composite. It writes the full-resolution page to `outputs/single/sample_page.png`, the QA image to `outputs/single/qa/sample_page_compare.jpg`, and the log/summary to `outputs/single/run.log` and `outputs/single/summary.json`.
6. **Verify:** Confirm `outputs/single/sample_page.png` exists and has the original page dimensions. If a previous run already produced it, the script skips it; add `--force` to reprocess.

For a manual recomposition from the downloaded raw layer only:

```powershell
python scripts/postprocess.py --original examples/sample_page.webp --color outputs/single/raw/sample_page.png --output outputs/single/sample_page_manual.png --radius 2 --sat 1.0 --white-threshold 256
```

Do not run `scripts/postprocess.py` on the already composited final image; it expects the raw model color layer.

## 3. Batch colorization

Use one shared reference and one fixed seed for every page. Do not create a separate reference per page.

```powershell
python scripts/colorize.py --config config.example.json --input-dir examples --glob "*.webp" --reference examples/sample_reference.jpg --output-dir outputs/batch --batch-size 2
```

The checked-in `examples/` directory contains one `.webp`, so this command is a smoke test of the batch path. For a real batch, replace `--input-dir examples` with the user's page directory while keeping the same `--reference` and the fixed `seed` from `config.example.json` (default `1234`).

- On 6 GB VRAM, keep `--batch-size 2`; do not increase it to 8.
- Final pages go directly under `outputs/batch/`; raw layers go under `outputs/batch/raw/`, QA images under `outputs/batch/qa/`, and logs/summary under `outputs/batch/`.
- Existing final pages are skipped; use `--force` to reprocess them.
- If a batch fails, rerun the same command. Inspect `outputs/batch/run.log` and `outputs/batch/summary.json` before claiming success.

Build the final contact sheet after the batch:

```powershell
python scripts/make_contact_sheet.py --input-dir outputs/batch --output outputs/batch/contact_sheet.jpg
```

`scripts/make_contact_sheet.py` reads `*.png` directly in the input directory; point it at the directory containing final pages, not at the `raw/` or `qa/` subdirectories.

## 4. Hard constraints

- Never commit `outputs/`, `input/`, or `models/`; all three are ignored. Keep generated finals, raw layers, QA images, logs, and summaries under `outputs/`.
- Use only the checked-in demo assets under `examples/` for repository examples: `examples/sample_page.webp`, `examples/sample_reference.jpg`, and `examples/sample_output.png`. Do not add external manga pages or references to `examples/` or to a commit.
- Do not commit or upload model weights or LoRA files. They live in the gitignored local `models/` tree and must be copied with the portable USB bundle; do not publish them. Use `scripts/download_models.ps1` on a fresh clone or when a file is missing.
- Do not commit secrets, tokens, or absolute paths. Prefer `config.example.json` and command-line overrides.
- Do not modify `workflows/flux2_manga_ui.json`; it is the official Apache-2.0 fp8 reference. The 6 GB execution path is the Q3 GGUF API script.
- Do not claim a successful run if `scripts/check_setup.py` fails, ComfyUI is offline, or the expected final and QA files are missing. Report the blocker and list the static checks that were completed.

**中文摘要**

- 先运行 `scripts/check_setup.py`；ComfyUI 或模型不可用就停止，并提示 `scripts/download_models.ps1`。
- 单页使用 `scripts/colorize.py`；批量复用同一参考图和固定 seed，结束后运行 `scripts/make_contact_sheet.py`。
- 生成物只写入 `outputs/`；不要提交 `outputs/`、`models/` 或 `examples/` 之外的素材。
- 6GB 显存保持 batch 2；不要把官方 UI fp8 参考流程当成已验证的 6GB 执行路径。
