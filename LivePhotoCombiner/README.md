# 实况照片合并器 Live Photo Combiner

将静态图片 + 短视频 合并为可在手机相册长按播放的实况照片。

## 功能特点

- 🖼️ **批量处理**：自动按文件名配对图片和视频，一键批量合并
- 🎯 **三种输出格式**：
  - **Google Motion Photo (.jpg)** — 推荐，单文件，兼容性最好（iOS相册、小红书、Google Photos、小米相册等均支持）
  - **LIVP 格式 (.livp)** — 国内安卓相册通用的容器格式（华为/小米/OPPO等）
  - **Apple Live Photo (.jpg + .mov)** — 苹果原生配对格式（需安装 exiftool + ffmpeg）
- 🖥️ **图形界面**：简单易用，无需命令行
- 📦 **零依赖核心**：Motion Photo 和 LIVP 格式纯 Python 标准库实现

## 快速开始

### 方式一：直接运行（需 Python 3.8+）

```bash
# 安装可选依赖（支持PNG/HEIC图片自动转换）
pip install Pillow

# 运行
python main.py
```

### 方式二：打包成 exe

双击运行 `build.bat`，完成后在 `dist/` 目录得到 `LivePhotoCombiner.exe`。

## 使用步骤

1. **准备文件**：将图片和视频放在文件夹中，确保同名（不含扩展名）
   - 例如：`IMG_001.jpg` + `IMG_001.mov`
2. **选择文件夹**：分别选择图片文件夹、视频文件夹、输出文件夹
3. **选择格式**：推荐使用 Google Motion Photo
4. **扫描配对**：点击"扫描配对"查看匹配结果
5. **开始合并**：点击"开始合并"，等待处理完成

## 支持的文件格式

| 类型 | 支持格式 |
|------|----------|
| 图片 | JPG, JPEG, PNG, HEIC, WebP |
| 视频 | MOV, MP4, M4V, AVI, MKV |

> 注意：非 JPG 图片会自动转换为 JPG（需安装 Pillow）。

## 格式说明

### Google Motion Photo（推荐）

- 输出为单个 `.jpg` 文件
- 原理：将 MP4 视频数据拼接在 JPEG 之后，并写入 XMP 元数据标记
- 兼容性：iOS 相册、小红书、Google Photos、小米/华为相册等主流平台均支持
- 导入手机后，在相册中长按/重按即可播放动态效果

### LIVP 格式

- 输出为单个 `.livp` 文件
- 原理：ZIP 容器封装 JPG + 视频
- 兼容性：国内安卓相册广泛支持，部分第三方应用支持

### Apple Live Photo（需额外工具）

- 输出为配对的 `.jpg` + `.mov` 两个文件
- 原理：通过相同的 MediaGroupUUID 元数据绑定
- 需要安装：
  - [exiftool](https://exiftool.org/) — 写入图片元数据
  - [ffmpeg](https://ffmpeg.org/) — 视频转码为 H.264 MOV
- 将两个文件一起导入 Apple Photos 即可识别为实况照片

## 常见问题

**Q: 为什么配对不到文件？**
A: 确保图片和视频的文件名（不含扩展名）完全相同。例如 `photo.jpg` 对应 `photo.mov`。

**Q: 生成的文件在手机上不能动？**
A: 请确认使用的是 Motion Photo 格式，并且通过正确的方式导入手机（AirDrop / 数据线 / 云盘原文件传输）。微信发送会压缩导致失效。

**Q: 视频太长可以吗？**
A: 可以，但建议控制在 3 秒以内，符合实况照片的常规时长。

## 技术原理

Apple Live Photo 的本质是一张静态图片与一段短视频的绑定组合，绑定的关键在于两个文件的元数据中写入相同的 UUID（Content Identifier / MediaGroupUUID）。

Google Motion Photo 则采用单文件方案，将视频数据直接拼接在 JPEG 数据之后，通过 XMP 元数据标记视频的位置和长度。

## 许可证

MIT License
