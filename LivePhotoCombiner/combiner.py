# -*- coding: utf-8 -*-
"""
实况照片合并器 - 核心模块
支持三种输出格式：
1. Google Motion Photo (单文件 .jpg) - 兼容性最好，iOS相册/小红书/Google Photos均支持
2. LIVP 格式 (.livp) - 国内安卓相册常用的容器格式（ZIP封装 JPG+MOV）
3. Apple Live Photo (配对 .jpg + .mov) - 需要 exiftool 和 ffmpeg
"""

import os
import io
import uuid
import zipfile
import struct
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional, Callable


# 支持的图片和视频扩展名
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp'}
VIDEO_EXTS = {'.mov', '.mp4', '.m4v', '.avi', '.mkv'}

# 尝试注册 HEIC/HEIF 支持（需要 pillow-heif 库）
_HEIF_REGISTERED = False
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    _HEIF_REGISTERED = True
except ImportError:
    pass


def check_heic_support() -> bool:
    """检查是否支持 HEIC 格式"""
    return _HEIF_REGISTERED


def _convert_image_to_jpeg(image_path: str) -> bytes:
    """
    将图片转换为 JPEG 字节数据。
    支持 JPG/PNG/WebP/HEIC（需 pillow-heif）等格式。
    """
    img_ext = Path(image_path).suffix.lower()

    # 已经是 JPEG，直接读取
    if img_ext in ('.jpg', '.jpeg'):
        with open(image_path, 'rb') as f:
            return f.read()

    # 需要转换
    try:
        from PIL import Image
    except ImportError:
        raise ValueError(
            f"图片格式 {img_ext} 需要安装 Pillow: pip install Pillow"
        )

    # HEIC 特殊提示
    if img_ext in ('.heic', '.heif') and not _HEIF_REGISTERED:
        raise ValueError(
            "HEIC 格式需要安装 pillow-heif: pip install pillow-heif"
        )

    try:
        img = Image.open(image_path)
        # 处理透明通道
        if img.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        return buf.getvalue()
    except Exception as e:
        raise ValueError(f"图片转换失败 ({img_ext}): {e}")


def find_files(directory: str, exts: set) -> List[Path]:
    """扫描目录下指定扩展名的文件（不递归子目录）"""
    result = []
    if not os.path.isdir(directory):
        return result
    for f in os.listdir(directory):
        p = os.path.join(directory, f)
        if os.path.isfile(p) and Path(f).suffix.lower() in exts:
            result.append(Path(p))
    return sorted(result)


def pair_files(image_dir: str, video_dir: str) -> List[Tuple[Path, Path]]:
    """
    按文件名（不含扩展名）配对图片和视频。
    支持：IMG_001.jpg + IMG_001.mov
    也支持：IMG_001.jpg + IMG_001 (2).mov 等近似匹配
    返回 [(image_path, video_path), ...]
    """
    images = find_files(image_dir, IMAGE_EXTS)
    videos = find_files(video_dir, VIDEO_EXTS)

    # 建立视频文件名索引
    video_map = {}
    for v in videos:
        stem = v.stem.lower()
        video_map[stem] = v

    pairs = []
    used_videos = set()

    for img in images:
        stem = img.stem.lower()
        # 精确匹配
        if stem in video_map and video_map[stem] not in used_videos:
            pairs.append((img, video_map[stem]))
            used_videos.add(video_map[stem])
            continue

        # 模糊匹配：去除括号、空格等后匹配
        def normalize(s):
            for ch in '()（）[]【】 _-':
                s = s.replace(ch, '')
            return s

        norm_stem = normalize(stem)
        matched = None
        for v in videos:
            if v in used_videos:
                continue
            if normalize(v.stem.lower()) == norm_stem:
                matched = v
                break
        if matched:
            pairs.append((img, matched))
            used_videos.add(matched)

    return pairs


def get_unpaired(image_dir: str, video_dir: str, pairs: List[Tuple[Path, Path]]) -> Tuple[List[Path], List[Path]]:
    """获取未配对的文件"""
    paired_images = {p[0] for p in pairs}
    paired_videos = {p[1] for p in pairs}
    all_images = set(find_files(image_dir, IMAGE_EXTS))
    all_videos = set(find_files(video_dir, VIDEO_EXTS))
    return sorted(all_images - paired_images), sorted(all_videos - paired_videos)


# ============================================================
# 格式一：Google Motion Photo (单文件)
# ============================================================

def _build_xmp_motion_photo(video_offset: int, video_length: int, timestamp_us: int = 0) -> bytes:
    """
    构建包含 Motion Photo 标记的 XMP 元数据（APP1段）。
    参考 Google Camera Motion Photo 格式。
    """
    xmp_content = f'''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
        xmlns:GCamera="http://ns.google.com/photos/1.0/camera/"
        xmlns:Container="http://ns.google.com/photos/1.0/container/"
        xmlns:Item="http://ns.google.com/photos/1.0/container/item/"
        GCamera:MotionPhoto="1"
        GCamera:MotionPhotoVersion="1"
        GCamera:MotionPhotoPresentationTimestampUs="{timestamp_us}">
      <Container:Directory>
        <rdf:Seq>
          <rdf:li rdf:parseType="Resource">
            <Container:Item
              Item:Mime="image/jpeg"
              Item:Semantic="Primary"
              Item:Length="0"
              Item:Padding="0"/>
          </rdf:li>
          <rdf:li rdf:parseType="Resource">
            <Container:Item
              Item:Mime="video/mp4"
              Item:Semantic="MotionPhoto"
              Item:Length="{video_length}"
              Item:Padding="0"/>
          </rdf:li>
        </rdf:Seq>
      </Container:Directory>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''

    xmp_bytes = xmp_content.encode('utf-8')
    # XMP 标识
    xmp_header = b'http://ns.adobe.com/xap/1.0/\x00'
    payload = xmp_header + xmp_bytes
    # APP1 段：FF E1 + 长度(2字节大端) + payload
    length = len(payload) + 2
    app1 = b'\xff\xe1' + struct.pack('>H', length) + payload
    return app1


def create_motion_photo(image_path: str, video_path: str, output_path: str,
                        progress_cb: Optional[Callable] = None) -> bool:
    """
    创建 Google Motion Photo 单文件。
    将 JPEG 图片和 MP4 视频拼接为一个 .jpg 文件，并写入 XMP 元数据。
    输出文件兼容：iOS相册、小红书、Google Photos、小米相册等。
    """
    try:
        # 读取视频数据
        with open(video_path, 'rb') as f:
            vid_data = f.read()

        if progress_cb:
            progress_cb(15, "读取视频完成")

        # 转换图片为 JPEG（自动处理 HEIC/PNG/WebP 等格式）
        img_data = _convert_image_to_jpeg(image_path)

        if progress_cb:
            progress_cb(35, "图片处理完成")

        # 确保图片以 FFD8 开头
        if not img_data.startswith(b'\xff\xd8'):
            raise ValueError("图片不是有效的JPEG格式")

        # 找到 JPEG 的 SOI (FFD8) 之后，插入 XMP APP1 段
        # 简单做法：在 FFD8 之后直接插入我们的 APP1
        # 但如果已有 APP1（EXIF），我们应该在它之后插入
        # 为了简单且兼容，我们在 SOI 之后插入

        # 计算视频偏移量（最终文件中视频开始的位置）
        xmp_app1 = _build_xmp_motion_photo(0, len(vid_data))
        final_img_data = img_data[:2] + xmp_app1 + img_data[2:]
        video_offset = len(final_img_data)

        if progress_cb:
            progress_cb(60, "元数据注入完成")

        # 写入最终文件
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(final_img_data)
            f.write(vid_data)

        if progress_cb:
            progress_cb(100, f"完成: {os.path.basename(output_path)}")

        return True

    except Exception as e:
        if progress_cb:
            progress_cb(-1, f"失败: {e}")
        return False


# ============================================================
# 格式二：LIVP 格式 (ZIP 容器)
# ============================================================

def create_livp(image_path: str, video_path: str, output_path: str,
                 progress_cb: Optional[Callable] = None) -> bool:
    """
    创建 LIVP 格式实况照片。
    LIVP 本质是 ZIP 容器，内含一张 JPG 和一段 MOV/MP4。
    国内安卓相册（华为、小米、OPPO等）和部分第三方应用支持。
    """
    try:
        vid_ext = Path(video_path).suffix.lower()

        # 读取视频
        with open(video_path, 'rb') as f:
            vid_data = f.read()

        if progress_cb:
            progress_cb(20, "读取视频完成")

        # 转换图片为 JPEG（自动处理 HEIC/PNG/WebP 等格式）
        img_data = _convert_image_to_jpeg(image_path)
        img_ext = '.jpg'

        if progress_cb:
            progress_cb(50, "图片处理完成")

        # 写入 ZIP
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_STORED) as zf:
            zf.writestr(f'live{img_ext}', img_data)
            zf.writestr(f'live{vid_ext}', vid_data)

        if progress_cb:
            progress_cb(100, f"完成: {os.path.basename(output_path)}")

        return True

    except Exception as e:
        if progress_cb:
            progress_cb(-1, f"失败: {e}")
        return False


# ============================================================
# 格式三：Apple Live Photo (配对文件，需要 exiftool + ffmpeg)
# ============================================================

def check_exiftool() -> Optional[str]:
    """检查 exiftool 是否可用，返回路径或 None"""
    try:
        result = subprocess.run(['exiftool', '-ver'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return 'exiftool'
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # 检查常见安装路径
    for p in [r'C:\exiftool\exiftool.exe', r'C:\Program Files\ExifTool\exiftool.exe']:
        if os.path.exists(p):
            return p
    return None


def check_ffmpeg() -> Optional[str]:
    """检查 ffmpeg 是否可用"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return 'ffmpeg'
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def create_apple_live_photo(image_path: str, video_path: str, output_dir: str,
                             progress_cb: Optional[Callable] = None) -> bool:
    """
    创建 Apple Live Photo 配对文件（.jpg + .mov）。
    通过写入相同的 MediaGroupUUID 让 Apple Photos 识别为实况照片。
    需要系统安装 exiftool 和 ffmpeg。
    """
    exiftool = check_exiftool()
    ffmpeg = check_ffmpeg()

    if not exiftool:
        if progress_cb:
            progress_cb(-1, "失败: 未检测到 exiftool，请先安装并加入PATH")
        return False
    if not ffmpeg:
        if progress_cb:
            progress_cb(-1, "失败: 未检测到 ffmpeg，请先安装并加入PATH")
        return False

    try:
        # 生成 UUID
        live_uuid = str(uuid.uuid4()).upper()

        os.makedirs(output_dir, exist_ok=True)
        base_name = Path(image_path).stem
        out_img = os.path.join(output_dir, f'{base_name}.jpg')
        out_vid = os.path.join(output_dir, f'{base_name}.mov')

        if progress_cb:
            progress_cb(10, f"生成UUID: {live_uuid}")

        # 1. 转换图片为 JPEG（自动处理 HEIC/PNG/WebP 等格式）
        img_data = _convert_image_to_jpeg(image_path)
        with open(out_img, 'wb') as f:
            f.write(img_data)

        if progress_cb:
            progress_cb(30, "图片处理完成")

        # 2. 用 exiftool 写入 MediaGroupUUID 到图片
        cmd_img = [
            exiftool, '-overwrite_original',
            f'-MediaGroupUUID={live_uuid}',
            f'-ImageUUID={live_uuid}',
            out_img
        ]
        r = subprocess.run(cmd_img, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            if progress_cb:
                progress_cb(-1, f"图片元数据写入失败: {r.stderr}")
            return False

        if progress_cb:
            progress_cb(50, "图片元数据写入完成")

        # 3. 用 ffmpeg 将视频转码为 H.264 MOV 并写入元数据
        cmd_vid = [
            ffmpeg, '-y', '-i', video_path,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            '-metadata', f'com.apple.quicktime.content.identifier={live_uuid}',
            '-metadata', f'media_group_uuid={live_uuid}',
            out_vid
        ]
        r = subprocess.run(cmd_vid, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            if progress_cb:
                progress_cb(-1, f"视频转码失败: {r.stderr[-500:] if r.stderr else '未知错误'}")
            return False

        if progress_cb:
            progress_cb(100, f"完成: {base_name}.jpg + {base_name}.mov")

        return True

    except Exception as e:
        if progress_cb:
            progress_cb(-1, f"失败: {e}")
        return False


# ============================================================
# 批量处理
# ============================================================

OUTPUT_FORMATS = {
    'motion': 'Google Motion Photo (.jpg) - 推荐，兼容性最好',
    'livp': 'LIVP 格式 (.livp) - 安卓相册通用',
    'apple': 'Apple Live Photo (.jpg+.mov) - 需exiftool+ffmpeg',
}


def batch_combine(pairs: List[Tuple[Path, Path]], output_dir: str,
                  fmt: str = 'motion',
                  progress_cb: Optional[Callable] = None,
                  log_cb: Optional[Callable] = None) -> Tuple[int, int]:
    """
    批量合并。
    返回 (成功数, 失败数)
    """
    success = 0
    failed = 0
    total = len(pairs)

    for i, (img, vid) in enumerate(pairs):
        base = img.stem
        if log_cb:
            log_cb(f"[{i+1}/{total}] 处理: {base}")

        def item_progress(pct, msg):
            if progress_cb:
                overall = int((i + pct / 100) / total * 100)
                progress_cb(overall, msg)

        if fmt == 'motion':
            out = os.path.join(output_dir, f'{base}.jpg')
            ok = create_motion_photo(str(img), str(vid), out, item_progress)
        elif fmt == 'livp':
            out = os.path.join(output_dir, f'{base}.livp')
            ok = create_livp(str(img), str(vid), out, item_progress)
        elif fmt == 'apple':
            ok = create_apple_live_photo(str(img), str(vid), output_dir, item_progress)
        else:
            ok = False

        if ok:
            success += 1
        else:
            failed += 1

    return success, failed
