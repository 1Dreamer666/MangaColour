#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check ComfyUI, custom nodes, and model names before running colorize.py."""
import argparse
import sys

import requests

from colorize import ComfyClient, SetupError, load_config


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=None)
    ap.add_argument("--comfyui-url", default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    url = args.comfyui_url or cfg["comfyui_url"]
    client = ComfyClient(url)

    stats = client._get("/system_stats")
    system = stats.get("system", {})
    print(f"ComfyUI: {url}")
    print(f"version: {system.get('comfyui_version', 'unknown')}")
    print(f"python:  {system.get('python_version', 'unknown')}")

    checks = [
        ("UnetLoaderGGUF", "unet_name", cfg["models"]["unet"]),
        ("CLIPLoader", "clip_name", cfg["models"]["clip"]),
        ("VAELoader", "vae_name", cfg["models"]["vae"]),
        ("LoraLoaderModelOnly", "lora_name", cfg["models"]["lora"]),
    ]
    for node, field, wanted in checks:
        resolved = client.resolve(node, field, wanted)
        print(f"OK {node}.{field}: {resolved}")

    info = client.object_info()
    for node in ("EmptyFlux2LatentImage", "Flux2Scheduler", "ReferenceLatent"):
        if node not in info:
            raise SetupError(f"ComfyUI is missing core node: {node}")
        print(f"OK core node: {node}")

    print("Setup check passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SetupError, FileNotFoundError, requests.RequestException) as exc:
        print(f"SETUP ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
