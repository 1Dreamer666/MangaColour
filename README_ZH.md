[English](README.md) | **中文**

# MangaColour

**基于 FLUX.2 的漫画上色：参考图配色迁移、线稿保持与批量一致性。**

MangaColour 接收一张黑白漫画页（或插画）和一张彩色参考图，输出原图分辨率的彩色页。扩散模型只负责低分辨率色度层；最终结果保留原始全分辨率 **L 通道**（线稿、文字、网点、气泡边框），所以线条不会被模型重绘糊掉。

这是从一次 33 页漫画上色任务中抽出的最小独立版本，不是 MangaNinja 项目的分支。

![样例](examples/sample_output.png)

## 特性

- 使用 FLUX.2 Klein 9B + manga LoRA 做参考图引导上色
- 每页使用两个 reference latent：页面本身 + 同一张颜色参考
- L 保留合成：原始线稿/文字 + 模型生成的 LAB 色度
- 批量处理、断点续跑、固定 seed，保持整批配色一致
- 6 GB 笔记本显存可在 0.5 MP 颜色层下运行（建议 batch 2）
- API 路径使用 ComfyUI 核心 `LoadImage` 和 `/upload/image`，不需要 VHS 节点
- 模型权重、`outputs/`、`input/` 和绝对路径默认都不上传 Git

## 仓库结构

```text
.
├─ README.md
├─ README_ZH.md                  # 中文说明
├─ config.example.json
├─ config/
│  └─ extra_model_paths.yaml     # ComfyUI 可移动模型路径配置
├─ requirements.txt
├─ scripts/
│  ├─ check_setup.py
│  ├─ colorize.py
│  ├─ download_models.ps1
│  ├─ make_contact_sheet.py
│  └─ postprocess.py
├─ workflows/
│  ├─ flux2_manga_ui.json        # 官方 fp8 UI 参考，Apache-2.0
│  └─ flux2_manga_api.example.json
├─ examples/
│  ├─ sample_page.webp
│  ├─ sample_reference.jpg
│  └─ sample_output.png
├─ models/                       # 本地模型包；Git 忽略
├─ input/                        # 本地输入页；Git 忽略
├─ outputs/                      # 运行输出；Git 忽略
├─ THIRD_PARTY_NOTICES.md
└─ LICENSE                       # AGPL-3.0
```

`models/`、`input/`、`outputs/` 不会上传 GitHub。把 `repo` 用 U 盘搬到另一台电脑时，必须复制整个目录，尤其是被 Git 忽略的 `models/`；只执行 `git clone` 不会得到模型权重。

## 工作流程

1. 将目标页和一张彩色参考图上传到 ComfyUI。
2. 将目标页编码为 reference latent #1，将参考图编码为 reference latent #2。
3. 使用 FLUX.2 Klein 9B + `manga_colorization.safetensors`（触发词 `mngclranm`）采样。
4. 下载低分辨率颜色层。
5. 转为 LAB，保留原图全分辨率 L，把模型预测的 a/b 色度通过 guided filter 合成回去。
6. 可选清理纸张/气泡的冷色漂移；默认关闭，避免把明亮肤色也误清掉。

默认颜色层是 **0.5 MP**，因为 9B 模型加 Qwen 文本编码器无法在 6 GB 显存下以整页分辨率运行。最终输出仍是原图分辨率。

## 环境要求

- ComfyUI **0.31.0 或更新版本**，并带有 FLUX.2 节点
- [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF)，用于 `UnetLoaderGGUF`
- Python 3.10+，用于运行仓库脚本
- 正在运行的 ComfyUI 服务（默认 `http://127.0.0.1:8000`）
- 6 GB 显存可跑推荐的 0.5 MP / batch 2；更大 batch 或 1 MP 建议 12 GB 以上

UI 工作流使用核心 `LoadImage`，不含 VHS 节点；API 路径同样不需要 ComfyUI-VideoHelperSuite。

## 模型

脚本不会自动下载权重。当前工作副本已经把四个必需模型放在本地 `models/` 目录中，因此整个 `repo` 目录复制到 U 盘后是自包含的；只有全新 clone 或文件缺失时才需要重新下载。

```powershell
# 默认下载到 .\models
.\scripts\download_models.ps1

# 或直接下载到 ComfyUI 的模型目录
.\scripts\download_models.ps1 -ModelsDir "C:\path\to\ComfyUI\models"
```

| 文件 | ComfyUI 目录 | 大小 (bytes) | SHA256 |
|---|---|---:|---|
| `flux-2-klein-base-9b-Q3_K_M.gguf` | `diffusion_models/FLUX.2/` | 4,769,503,520 | `4F5FAD20886A9F9541151E4488BC26676E5FE6090371C95F3F4141F5AEC5CE70` |
| `qwen_3_8b_fp4mixed.safetensors` | `text_encoders/Qwen/` | 6,802,593,327 | `BBF16F981D98E16D080C566134814C4E9F6AADD0D0E1383C60BC44BA939D760D` |
| `flux2-vae.safetensors` | `vae/FLUX.2/` | 336,211,292 | `868FE7B343CC8F3A19DBCFCAFBC3D5F888802BE3F89BD81B65B3621A066CE8F3` |
| `manga_colorization.safetensors` | `loras/FLUX.2/` | 165,704,456 | `1206D0E28425E7A5323231E6501A65F5B64DCF7B1108E0749E8CB9F40E1C7FF8` |

完整下载 URL 在 `scripts/download_models.ps1` 和
`THIRD_PARTY_NOTICES.md` 中。

本地模型目录结构：

```text
models/
├─ diffusion_models/FLUX.2/flux-2-klein-base-9b-Q3_K_M.gguf
├─ text_encoders/Qwen/qwen_3_8b_fp4mixed.safetensors
├─ vae/FLUX.2/flux2-vae.safetensors
└─ loras/FLUX.2/manga_colorization.safetensors
```

### 让 ComfyUI 识别仓库内模型

仓库自带 `config/extra_model_paths.yaml`。它的 `base_path` 是相对路径
`../models`，相对于配置文件所在目录解析，所以整个 `repo` 移动到 U 盘或另一台电脑后仍然有效：

```yaml
mangacolour:
  base_path: ../models
  diffusion_models: diffusion_models
  text_encoders: text_encoders
  vae: vae
  loras: loras
```

启动 ComfyUI 时加载这个配置：

```powershell
python main.py --extra-model-paths-config "<path-to-repo>/config/extra_model_paths.yaml"
```

如果 ComfyUI 已经在运行，把同样的 `mangacolour` 配置合并到它现有的
`extra_model_paths.yaml`，重启后再运行 `check_setup.py`。只有四个模型都出现在检查结果里，才继续上色。

`colorize.py` 的模型解析使用 basename，所以 ComfyUI 显示成
`FLUX.2\...` 这样的子目录也能找到。模型缺失时，`check_setup.py` 会打印 ComfyUI 实际可用的模型列表。

### U 盘移动到另一台电脑

1. 复制**整个 `repo` 目录**，包括被 Git 忽略的 `models/`（约 11.2 GB）。只 clone GitHub 仓库不会带权重。
2. 目标电脑需要已经安装 ComfyUI、ComfyUI-GGUF 和 Python 依赖。
3. 用 `config/extra_model_paths.yaml` 启动 ComfyUI，然后运行：
   `python scripts/check_setup.py --config config.example.json`
4. 跑示例或用户自己的页面。`outputs/` 保持在本地即可，不要提交。

## 快速开始

```powershell
python -m pip install -r requirements.txt

# 1. 检查 ComfyUI、GGUF 节点和四个模型
python scripts/check_setup.py --config config.example.json

# 2. 给自带样例上色
python scripts/colorize.py --config config.example.json
```

输出结构：

```text
outputs/sample/
├─ sample_page.png       # 原图分辨率合成结果
├─ raw/sample_page.png   # 模型原始低分辨率颜色层
├─ qa/sample_page_compare.jpg
├─ run.log
└─ summary.json
```

仓库里的 `examples/sample_output.png` 就是上述命令生成的。
如果 ComfyUI 没启动或模型缺失，`check_setup.py` 会直接报错；不要把静态检查当成端到端成功。

## 单页与批量

单页：

```powershell
python scripts/colorize.py `
  --config config.example.json `
  --pages examples/sample_page.webp `
  --reference examples/sample_reference.jpg `
  --output-dir outputs/single
```

批量（整批复用同一参考图）：

```powershell
python scripts/colorize.py `
  --config config.example.json `
  --input-dir pages `
  --glob "*.webp" `
  --reference examples/sample_reference.jpg `
  --output-dir outputs/pages `
  --batch-size 2
```

输出目录中已存在的同名最终页会跳过；加 `--force` 可重新处理。批量结果按输入文件名命名。

生成联系表：

```powershell
python scripts/make_contact_sheet.py `
  --input-dir outputs/pages `
  --output outputs/pages/contact_sheet.jpg
```

只对已下载的 raw 颜色层单独做 L 合成：

```powershell
python scripts/postprocess.py `
  --original page.webp `
  --color raw.png `
  --output final.png `
  --radius 2 --sat 1.0 --white-threshold 256
```

## 配置与参数

`config.example.json` 提供默认值；命令行参数覆盖配置文件：

| 参数 | 默认值 | 含义 |
|---|---:|---|
| `comfyui_url` / `--comfyui-url` | `http://127.0.0.1:8000` | ComfyUI 服务地址 |
| `pages` / `--pages` | sample | 输入页面路径 |
| `input_dir` / `--input-dir` | 未设置 | 批量目录 |
| `reference` / `--reference` | sample | 整批共用的一张参考图 |
| `output_dir` / `--output-dir` | `outputs/colorized` | 输出根目录 |
| `batch_size` / `--batch-size` | `1`（示例） | 每个扩散 batch 的页数 |
| `megapixels` / `--megapixels` | `0.5` | 颜色层目标像素 |
| `resolution_steps` / `--resolution-steps` | `16` | FLUX.2 尺寸取整 |
| `steps` / `--steps` | `20` | 采样步数 |
| `cfg` / `--cfg` | `4.0` | CFG 引导 |
| `seed` / `--seed` | `1234` | 固定 seed，保持批量配色 |
| `lora_strength` / `--lora-strength` | `1.0` | manga LoRA 强度 |
| `prompt` / `--prompt` | `mngclranm` | LoRA 触发词 |
| `timeout` / `--timeout` | `3600` | 单个 batch 等待超时（秒） |
| `postprocess.radius` | `2` | guided filter 半径 |
| `postprocess.sat` | `1.0` | 色度饱和度 |
| `postprocess.white_threshold` | `256.0` | `256` 表示关闭纸张/气泡清理 |
| `postprocess.neutral_mask` | `false` | 可选的中性像素清理 |

`--save-api-json path.json` 可以保存生成的 API 图，便于检查。

## UI 工作流

`workflows/flux2_manga_ui.json` 是 LoRA 作者提供的**官方 fp8 工作流**，作为参考保留。它使用 `UNETLoader` + `flux-2-klein-base-9b-fp8.safetensors` 和 `qwen_3_8b_fp8mixed.safetensors`，不是 6 GB 显存使用的 Q3 GGUF 路径。

- 6 GB 显存：使用 API 脚本 + Q3 GGUF 模型。
- 更大显存：打开 UI 工作流，手动选择 fp8 模型。
- UI 工作流使用核心 `LoadImage`，不需要 VHS。
- 打开 UI 前，把 `examples/sample_page.webp` 和 `examples/sample_reference.jpg` 复制到 ComfyUI 的 `input/` 目录。

来源和许可证见 `THIRD_PARTY_NOTICES.md`。UI 工作流仍是 Apache-2.0，不受仓库脚本 AGPL-3.0 覆盖。

`workflows/flux2_manga_api.example.json` 是生成的 flat API 图，仅用于检查；其中的 `LoadImage` 是服务器端上传名，换一台机器会不同。需要时用
`python scripts/colorize.py ... --save-api-json workflows/my_api.json` 重新生成。

## 性能记录

测试环境：RTX 3060 Laptop 6 GB、ComfyUI 0.31.0、Q3 GGUF、0.5 MP、20 steps：

- batch 2：**8.4–9.4 分钟 / 2 页**，约 **4.2–4.7 分钟/页**
- 单页：约 5–6 分钟（含模型加载）；最后一次单页 5.3 分钟
- 1 MP 单页：约 11.6 分钟
- 8 页 batch：没有崩溃，但 41 分钟后仍无输出；日志显示
  `0.00 MB usable, 0.00 MB loaded, 4740.54 MB offloaded`，权重在 CPU/GPU 之间抖动，已中止。6 GB 显存建议 batch 2。
- 12 GB 以上可以尝试更大 batch，但计算量仍按页数增长。

## 故障排查

**`check_setup.py` 连不上 ComfyUI**
启动 ComfyUI，确认 `comfyui_url`，服务必须能访问 `/system_stats`。

**找不到 `UnetLoaderGGUF`**
安装或更新 [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF)，重启 ComfyUI，再运行
`check_setup.py`。

**找不到模型**
运行 `python scripts/check_setup.py --config ...`，它会打印 ComfyUI 实际可用的模型。确认已经用
`config/extra_model_paths.yaml` 启动或合并配置，并重启 ComfyUI。

**上传失败**
脚本会调用 ComfyUI `/upload/image`；确认 ComfyUI 的 `input/` 目录可写。

**显存不足或采样极慢**
使用 `--batch-size 1` 或 `2`，保持 `--megapixels 0.5`，关闭其他 GPU 程序；长时间运行后可重启 ComfyUI 释放碎片化显存。

**文字或气泡被染色**
默认关闭纸张/气泡清理。可以尝试
`--postprocess-white-threshold 94` 或 `--neutral-mask`，但要检查明亮肤色，过度清理会留下白洞。

## 许可证

- **本仓库 Python 脚本**（`scripts/*.py`）：AGPL-3.0，见 `LICENSE`。
- **`workflows/flux2_manga_ui.json`**：Apache-2.0，来自官方 LoRA 仓库：
  https://huggingface.co/thedeoxen/FLUX.2-klein-9B-manga-colorization-by-reference-LORA
  不由 AGPL-3.0 重新授权。
- **`manga_colorization.safetensors` LoRA**：按其模型卡为 Apache-2.0；权重不随 Git 仓库上传。
- **FLUX.2、Qwen、VAE 及其他模型权重**：分别遵守各自模型许可证；权重不随 Git 仓库上传。
- **`examples/` 下的示例素材**：仅作演示；角色和美术权利归原权利人。它们不属于 AGPL-3.0，正式再分发前请替换。

本 README 不构成法律意见；商业使用前请自行核对模型许可证。

## 致谢

- Black Forest Labs：FLUX.2 Klein 9B
- thedeoxen：漫画上色 LoRA 和官方工作流
- unsloth：Q3 GGUF 量化
- Comfy-Org：ComfyUI 格式的文本编码器/VAE 文件
- city96：ComfyUI-GGUF
- ComfyUI 项目
