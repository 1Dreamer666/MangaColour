param(
    [string]$ModelsDir = (Join-Path $PSScriptRoot "..\models"),
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ModelsDir = [System.IO.Path]::GetFullPath($ModelsDir)

$files = @(
    @{
        Name   = "flux-2-klein-base-9b-Q3_K_M.gguf"
        Url    = "https://huggingface.co/unsloth/FLUX.2-klein-base-9B-GGUF/resolve/main/flux-2-klein-base-9b-Q3_K_M.gguf"
        Out    = "diffusion_models/FLUX.2/flux-2-klein-base-9b-Q3_K_M.gguf"
        Size   = 4769503520
        Sha256 = "4F5FAD20886A9F9541151E4488BC26676E5FE6090371C95F3F4141F5AEC5CE70"
    },
    @{
        Name   = "qwen_3_8b_fp4mixed.safetensors"
        Url    = "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp4mixed.safetensors"
        Out    = "text_encoders/Qwen/qwen_3_8b_fp4mixed.safetensors"
        Size   = 6802593327
        Sha256 = "BBF16F981D98E16D080C566134814C4E9F6AADD0D0E1383C60BC44BA939D760D"
    },
    @{
        Name   = "flux2-vae.safetensors"
        Url    = "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/vae/flux2-vae.safetensors"
        Out    = "vae/FLUX.2/flux2-vae.safetensors"
        Size   = 336211292
        Sha256 = "868FE7B343CC8F3A19DBCFCAFBC3D5F888802BE3F89BD81B65B3621A066CE8F3"
    },
    @{
        Name   = "manga_colorization.safetensors"
        Url    = "https://huggingface.co/thedeoxen/FLUX.2-klein-9B-manga-colorization-by-reference-LORA/resolve/main/manga_colorization.safetensors"
        Out    = "loras/FLUX.2/manga_colorization.safetensors"
        Size   = 165704456
        Sha256 = "1206D0E28425E7A5323231E6501A65F5B64DCF7B1108E0749E8CB9F40E1C7FF8"
    }
)

function Get-Sha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToUpperInvariant()
}

Write-Host "Model directory: $ModelsDir"
foreach ($file in $files) {
    $out = Join-Path $ModelsDir $file.Out
    $outDir = Split-Path -Parent $out
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null

    if (Test-Path $out) {
        $item = Get-Item $out
        if (-not $Force -and $item.Length -eq $file.Size) {
            $hash = Get-Sha256 $out
            if ($hash -eq $file.Sha256) {
                Write-Host "OK $($file.Name) (already complete)"
                continue
            }
            throw "$($file.Name) exists but SHA256 is $hash (expected $($file.Sha256)). Use -Force to replace it."
        }
        if ($item.Length -gt $file.Size) {
            throw "$($file.Name) is larger than expected ($($item.Length) > $($file.Size)). Use -Force to replace it."
        }
    }

    if ($Force -and (Test-Path $out)) {
        Remove-Item -Force $out
    }

    Write-Host "Downloading $($file.Name)"
    & curl.exe -L --fail --http1.1 --retry 30 --retry-all-errors --retry-delay 5 `
        --connect-timeout 30 -C - -o $out $file.Url
    if ($LASTEXITCODE -ne 0) {
        throw "curl failed for $($file.Name) with exit code $LASTEXITCODE"
    }

    $actualSize = (Get-Item $out).Length
    if ($actualSize -ne $file.Size) {
        throw "$($file.Name) size mismatch: $actualSize / $($file.Size)"
    }
    $actualHash = Get-Sha256 $out
    if ($actualHash -ne $file.Sha256) {
        throw "$($file.Name) SHA256 mismatch: $actualHash (expected $($file.Sha256))"
    }
    Write-Host "DONE $($file.Name) ($actualSize bytes)"
}

Write-Host "All model files are present and verified."
