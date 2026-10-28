#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reference-guided manga colorization with FLUX.2 Klein 9B.

The script talks to a running ComfyUI server over HTTP, uploads the target
page(s) and one color reference, queues a FLUX.2 manga-colorization workflow,
downloads the low-resolution color layers, and composites them with the
original full-resolution luminance (line art, text, screentone).

Run `python scripts/colorize.py --help` for all options.
"""
import argparse
import copy
import hashlib
import json
import mimetypes
import re
import sys
import time
import uuid
from pathlib import Path

import requests

from postprocess import composite

DEFAULT_CONFIG = {
    "comfyui_url": "http://127.0.0.1:8000",
    "models": {
        "unet": "flux-2-klein-base-9b-Q3_K_M.gguf",
        "clip": "qwen_3_8b_fp4mixed.safetensors",
        "vae": "flux2-vae.safetensors",
        "lora": "manga_colorization.safetensors",
    },
    "pages": [],
    "input_dir": None,
    "glob": "*.webp",
    "reference": None,
    "output_dir": "outputs/colorized",
    "batch_size": 1,
    "megapixels": 0.5,
    "resolution_steps": 16,
    "steps": 20,
    "cfg": 4.0,
    "seed": 1234,
    "lora_strength": 1.0,
    "prompt": "mngclranm",
    "negative": "",
    "timeout": 3600,
    "postprocess": {"radius": 2, "sat": 1.0, "white_threshold": 256.0,
                    "neutral_mask": False},
}


class SetupError(RuntimeError):
    pass


def deep_merge(base, override):
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path):
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if path:
        p = Path(path)
        if not p.exists():
            raise SetupError(f"config not found: {p}")
        cfg = deep_merge(cfg, json.loads(p.read_text(encoding="utf-8")))
    return cfg


def pick(cli_value, cfg_value, default=None):
    if cli_value is not None:
        return cli_value
    if cfg_value is not None:
        return cfg_value
    return default


class ComfyClient:
    def __init__(self, base_url, timeout=60):
        self.base = str(base_url).rstrip("/")
        self.timeout = timeout
        self._object_info = None

    def _get(self, path, **kwargs):
        response = requests.get(self.base + path, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response.json()

    def object_info(self):
        if self._object_info is None:
            self._object_info = self._get("/object_info")
        return self._object_info

    def choices(self, node, field):
        try:
            spec = self.object_info()[node]["input"]["required"][field]
        except KeyError as exc:
            raise SetupError(f"ComfyUI node/input missing: {node}.{field}") from exc
        options = spec[0]
        if isinstance(options, dict):
            options = options.get("options", [])
        if not isinstance(options, list):
            raise SetupError(f"cannot read choices for {node}.{field}")
        return options

    def resolve(self, node, field, wanted):
        options = self.choices(node, field)
        wanted = str(wanted)
        if wanted in options:
            return wanted
        basename = wanted.replace("\\", "/").split("/")[-1]
        matches = [opt for opt in options
                   if opt.replace("\\", "/").split("/")[-1] == basename]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            shown = ", ".join(options[:12])
            raise SetupError(
                f"{node}.{field}: '{wanted}' not found. Installed examples: {shown}")
        raise SetupError(
            f"{node}.{field}: '{wanted}' is ambiguous: {matches}")

    def upload(self, path):
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)
        data = path.read_bytes()
        digest = hashlib.sha1(data).hexdigest()[:12]
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem)[:40]
        name = f"mangacolour_{digest}_{stem}{path.suffix.lower() or '.png'}"
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        response = requests.post(
            self.base + "/upload/image",
            files={"image": (name, data, mime)},
            data={"overwrite": "true", "type": "input"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()
        subfolder = result.get("subfolder", "") or ""
        returned = result.get("name", name)
        return f"{subfolder}/{returned}" if subfolder else returned

    def queue(self, prompt):
        response = requests.post(
            self.base + "/prompt",
            json={"prompt": prompt, "client_id": uuid.uuid4().hex},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("error") or data.get("node_errors"):
            raise SetupError(json.dumps(data, ensure_ascii=False))
        return data["prompt_id"]

    def wait(self, prompt_id, timeout=None):
        timeout = timeout or self.timeout
        started = time.time()
        while time.time() - started < timeout:
            history = self._get(f"/history/{prompt_id}")
            item = history.get(prompt_id)
            if item:
                status = item.get("status", {})
                if status.get("status_str") == "success":
                    return item
                if status.get("status_str") == "error":
                    raise RuntimeError(json.dumps(status, ensure_ascii=False))
            time.sleep(2)
        raise TimeoutError(f"ComfyUI prompt timed out: {prompt_id}")

    def download(self, image_info, output_path):
        response = requests.get(
            self.base + "/view",
            params={
                "filename": image_info["filename"],
                "subfolder": image_info.get("subfolder", ""),
                "type": image_info.get("type", "output"),
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return output_path


def output_images(item):
    return item.get("outputs", {}).get("94", {}).get("images", [])


def build_prompt(page_names, reference_name, models, prefix, cfg):
    """Build a flat ComfyUI API graph for one or more target pages."""
    n = len(page_names)
    resolution_steps = int(cfg["resolution_steps"])
    p = {
        "70": {"class_type": "UnetLoaderGGUF",
               "inputs": {"unet_name": models["unet"]}},
        "88": {"class_type": "LoraLoaderModelOnly",
               "inputs": {"model": ["70", 0], "lora_name": models["lora"],
                          "strength_model": float(cfg["lora_strength"])}},
        "71": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": models["clip"], "type": "flux2",
                          "device": "default"}},
        "72": {"class_type": "VAELoader",
               "inputs": {"vae_name": models["vae"]}},
        "81": {"class_type": "LoadImage",
               "inputs": {"image": reference_name}},
        "85": {"class_type": "ImageScaleToTotalPixels",
               "inputs": {"image": ["81", 0], "upscale_method": "nearest-exact",
                          "megapixels": float(cfg["megapixels"]),
                          "resolution_steps": resolution_steps}},
        "220": {"class_type": "RepeatImageBatch",
                "inputs": {"image": ["85", 0], "amount": n}},
        "106": {"class_type": "VAEEncode",
                "inputs": {"pixels": ["220", 0], "vae": ["72", 0]}},
        "74": {"class_type": "CLIPTextEncode",
               "inputs": {"text": cfg["prompt"], "clip": ["71", 0]}},
        "87": {"class_type": "CLIPTextEncode",
               "inputs": {"text": cfg["negative"], "clip": ["71", 0]}},
        "107": {"class_type": "ReferenceLatent",
                "inputs": {"conditioning": ["77", 0], "latent": ["106", 0]}},
        "105": {"class_type": "ReferenceLatent",
                "inputs": {"conditioning": ["104", 0], "latent": ["106", 0]}},
        "63": {"class_type": "CFGGuider",
               "inputs": {"model": ["88", 0], "positive": ["107", 0],
                          "negative": ["105", 0], "cfg": float(cfg["cfg"])}},
        "73": {"class_type": "RandomNoise",
               "inputs": {"noise_seed": int(cfg["seed"])}},
        "61": {"class_type": "KSamplerSelect",
               "inputs": {"sampler_name": "euler"}},
        "64": {"class_type": "SamplerCustomAdvanced",
               "inputs": {"noise": ["73", 0], "guider": ["63", 0],
                          "sampler": ["61", 0], "sigmas": ["62", 0],
                          "latent_image": ["66", 0]}},
        "65": {"class_type": "VAEDecode",
               "inputs": {"samples": ["64", 0], "vae": ["72", 0]}},
        "94": {"class_type": "SaveImage",
               "inputs": {"images": ["65", 0], "filename_prefix": prefix}},
    }

    load_ids = []
    for i, image_name in enumerate(page_names):
        node_id = str(201 + i)
        load_ids.append(node_id)
        p[node_id] = {"class_type": "LoadImage",
                      "inputs": {"image": image_name}}

    current = load_ids
    next_id = 221
    while len(current) > 1:
        merged = []
        for i in range(0, len(current), 2):
            if i + 1 == len(current):
                merged.append(current[i])
                continue
            node_id = str(next_id)
            next_id += 1
            p[node_id] = {"class_type": "ImageBatch",
                          "inputs": {"image1": [current[i], 0],
                                     "image2": [current[i + 1], 0]}}
            merged.append(node_id)
        current = merged

    p["80"] = {"class_type": "ImageScaleToTotalPixels",
               "inputs": {"image": [current[0], 0],
                          "upscale_method": "nearest-exact",
                          "megapixels": float(cfg["megapixels"]),
                          "resolution_steps": resolution_steps}}
    p["103"] = {"class_type": "GetImageSize", "inputs": {"image": ["80", 0]}}
    p["66"] = {"class_type": "EmptyFlux2LatentImage",
               "inputs": {"width": ["103", 0], "height": ["103", 1],
                          "batch_size": n}}
    p["62"] = {"class_type": "Flux2Scheduler",
               "inputs": {"steps": int(cfg["steps"]), "width": ["103", 0],
                          "height": ["103", 1]}}
    p["78"] = {"class_type": "VAEEncode",
               "inputs": {"pixels": ["80", 0], "vae": ["72", 0]}}
    p["77"] = {"class_type": "ReferenceLatent",
               "inputs": {"conditioning": ["74", 0], "latent": ["78", 0]}}
    p["104"] = {"class_type": "ReferenceLatent",
                "inputs": {"conditioning": ["87", 0], "latent": ["78", 0]}}
    return p


def collect_pages(args, cfg):
    if args.pages:
        pages = [Path(p) for p in args.pages]
    elif args.input_dir or cfg.get("input_dir"):
        directory = Path(args.input_dir or cfg["input_dir"])
        pattern = args.glob or cfg.get("glob", "*.webp")
        pages = sorted(directory.glob(pattern))
    else:
        pages = [Path(p) for p in (cfg.get("pages") or [])]
    if not pages:
        raise SetupError("no input pages; use --pages or --input-dir")
    missing = [str(p) for p in pages if not p.exists()]
    if missing:
        raise SetupError("missing input pages: " + ", ".join(missing))
    return pages


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=None,
                    help="JSON config (see config.example.json)")
    ap.add_argument("--comfyui-url", default=None)
    ap.add_argument("--pages", nargs="+", default=None)
    ap.add_argument("--input-dir", default=None)
    ap.add_argument("--glob", default=None)
    ap.add_argument("--reference", default=None)
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--batch-size", type=int, default=None)
    ap.add_argument("--megapixels", type=float, default=None)
    ap.add_argument("--resolution-steps", type=int, default=None)
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--cfg", type=float, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--lora-strength", type=float, default=None)
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--negative", default=None)
    ap.add_argument("--timeout", type=int, default=None)
    ap.add_argument("--postprocess-radius", type=int, default=None)
    ap.add_argument("--postprocess-sat", type=float, default=None)
    ap.add_argument("--postprocess-white-threshold", type=float, default=None)
    ap.add_argument("--neutral-mask", action="store_true", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--save-api-json", default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    cfg["comfyui_url"] = pick(args.comfyui_url, cfg["comfyui_url"])
    cfg["reference"] = pick(args.reference, cfg.get("reference"))
    cfg["output_dir"] = pick(args.output_dir, cfg["output_dir"])
    cfg["batch_size"] = int(pick(args.batch_size, cfg["batch_size"]))
    cfg["megapixels"] = float(pick(args.megapixels, cfg["megapixels"]))
    cfg["resolution_steps"] = int(pick(args.resolution_steps, cfg["resolution_steps"]))
    cfg["steps"] = int(pick(args.steps, cfg["steps"]))
    cfg["cfg"] = float(pick(args.cfg, cfg["cfg"]))
    cfg["seed"] = int(pick(args.seed, cfg["seed"]))
    cfg["lora_strength"] = float(pick(args.lora_strength, cfg["lora_strength"]))
    cfg["prompt"] = pick(args.prompt, cfg["prompt"])
    cfg["negative"] = pick(args.negative, cfg["negative"])
    cfg["timeout"] = int(pick(args.timeout, cfg["timeout"]))
    if args.postprocess_radius is not None:
        cfg["postprocess"]["radius"] = args.postprocess_radius
    if args.postprocess_sat is not None:
        cfg["postprocess"]["sat"] = args.postprocess_sat
    if args.postprocess_white_threshold is not None:
        cfg["postprocess"]["white_threshold"] = args.postprocess_white_threshold
    if args.neutral_mask is not None:
        cfg["postprocess"]["neutral_mask"] = args.neutral_mask

    if not cfg.get("reference"):
        raise SetupError("a color reference is required: --reference or config.reference")

    pages = collect_pages(args, cfg)
    reference = Path(cfg["reference"])
    if not reference.exists():
        raise FileNotFoundError(reference)

    output_dir = Path(cfg["output_dir"])
    raw_dir = output_dir / "raw"
    qa_dir = output_dir / "qa"
    for directory in (output_dir, raw_dir, qa_dir):
        directory.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run.log"

    def log(message):
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        print(line, flush=True)
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    client = ComfyClient(cfg["comfyui_url"], timeout=cfg["timeout"])
    models = {
        "unet": client.resolve("UnetLoaderGGUF", "unet_name",
                               cfg["models"]["unet"]),
        "clip": client.resolve("CLIPLoader", "clip_name",
                               cfg["models"]["clip"]),
        "vae": client.resolve("VAELoader", "vae_name",
                              cfg["models"]["vae"]),
        "lora": client.resolve("LoraLoaderModelOnly", "lora_name",
                               cfg["models"]["lora"]),
    }
    log(f"ComfyUI: {cfg['comfyui_url']}")
    log(f"models: {models}")
    log(f"pages: {len(pages)}  batch={cfg['batch_size']}  "
        f"mp={cfg['megapixels']}  steps={cfg['steps']}  cfg={cfg['cfg']}")

    batches = [pages[i:i + cfg["batch_size"]]
               for i in range(0, len(pages), cfg["batch_size"])]
    summary = []
    for index, batch in enumerate(batches, 1):
        pending = [p for p in batch
                   if args.force or not (output_dir / f"{p.stem}.png").exists()]
        if not pending:
            log(f"batch {index}/{len(batches)} already complete")
            continue
        log(f"batch {index}/{len(batches)}: "
            + ", ".join(p.stem for p in pending))
        started = time.time()
        try:
            page_names = [client.upload(p) for p in pending]
            reference_name = client.upload(reference)
            prompt = build_prompt(page_names, reference_name, models,
                                  f"mangacolour_{index:03d}", cfg)
            if args.save_api_json:
                api_path = Path(args.save_api_json)
                api_path.parent.mkdir(parents=True, exist_ok=True)
                api_path.write_text(
                    json.dumps(prompt, ensure_ascii=False, indent=2),
                    encoding="utf-8")
            prompt_id = client.queue(prompt)
            item = client.wait(prompt_id, timeout=cfg["timeout"])
            images = output_images(item)
            if len(images) != len(pending):
                raise RuntimeError(
                    f"expected {len(pending)} images, got {len(images)}")
            for page, image in zip(pending, images):
                raw_path = raw_dir / f"{page.stem}.png"
                client.download(image, raw_path)
                final_path = output_dir / f"{page.stem}.png"
                compare_path = qa_dir / f"{page.stem}_compare.jpg"
                composite(
                    page, raw_path, final_path,
                    radius=cfg["postprocess"]["radius"],
                    sat=cfg["postprocess"]["sat"],
                    white_threshold=cfg["postprocess"]["white_threshold"],
                    neutral_mask=cfg["postprocess"].get("neutral_mask", False),
                    save_compare=compare_path,
                )
                log(f"  {page.stem} -> {final_path} "
                    f"({final_path.stat().st_size / 1e6:.2f} MB)")
            seconds = time.time() - started
            summary.append({"batch": index, "pages": [p.stem for p in pending],
                            "seconds": round(seconds, 1), "status": "success"})
            log(f"batch {index} done in {seconds / 60:.1f} min")
        except Exception as exc:
            seconds = time.time() - started
            summary.append({"batch": index, "pages": [p.stem for p in pending],
                            "seconds": round(seconds, 1),
                            "status": f"error: {exc}"})
            log(f"batch {index} FAILED: {exc}")
            break

    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log("DONE")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SetupError, FileNotFoundError, requests.RequestException) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
