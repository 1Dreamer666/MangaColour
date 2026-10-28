# Sample Assets

- `sample_page.webp` - grayscale demonstration input (1081 x 1600)
- `sample_reference.jpg` - color reference sheet (763 x 1005)
- `sample_output.png` - full-resolution composite produced by this repository

The sample character artwork is supplied for demonstration only. Character and
artwork rights remain with their original rights holders. The sample assets are
not covered by the repository's AGPL-3.0 license; see `THIRD_PARTY_NOTICES.md`.

Regenerate the output:

```powershell
python scripts/colorize.py --config config.example.json
copy outputs/sample/sample_page.png examples/sample_output.png
```

For the interactive UI workflow, copy `sample_page.webp` and
`sample_reference.jpg` into the ComfyUI `input/` directory, then select them in
the two `LoadImage` nodes.
