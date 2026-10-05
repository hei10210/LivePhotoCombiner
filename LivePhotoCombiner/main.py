# -*- coding: utf-8 -*-
"""
实况照片合并器 - GUI 主程序
将静态图片和短视频合并为实况照片（Live Photo / Motion Photo）
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path

# 确保能导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from combiner import (
    pair_files, find_files, get_unpaired,
    batch_combine, OUTPUT_FORMATS,
    check_exiftool, check_ffmpeg, check_heic_support,
    IMAGE_EXTS, VIDEO_EXTS,
)


APP_TITLE = "实况照片合并器 Live Photo Combiner"
APP_VERSION = "v1.0"


class LivePhotoApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_TITLE} {APP_VERSION}")
        self.root.geometry("820x680")
        self.root.minsize(720, 560)

        # 变量
        self.image_dir = tk.StringVar()
        self.video_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.output_format = tk.StringVar(value='motion')
        self.pairs = []
        self.is_running = False

        # 样式
        self._setup_style()

        # 构建界面
        self._build_ui()

        # 检测外部工具
        self._check_tools()

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('TLabel', font=('Microsoft YaHei UI', 9))
        style.configure('TButton', font=('Microsoft YaHei UI', 9))
        style.configure('TEntry', font=('Microsoft YaHei UI', 9))
        style.configure('TCombobox', font=('Microsoft YaHei UI', 9))
        style.configure('Header.TLabel', font=('Microsoft YaHei UI', 11, 'bold'))
        style.configure('Accent.TButton', font=('Microsoft YaHei UI', 10, 'bold'))

    def _build_ui(self):
        # 主容器
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # ===== 标题 =====
        title = ttk.Label(main, text="📸 实况照片合并器", style='Header.TLabel')
        title.pack(anchor=tk.W, pady=(0, 8))

        desc = ttk.Label(main, text="将静态图片 + 短视频 合并为可在手机相册播放的实况照片",
                         foreground='#666')
        desc.pack(anchor=tk.W, pady=(0, 12))

        # ===== 文件夹选择区 =====
        dir_frame = ttk.LabelFrame(main, text="文件夹设置", padding=10)
        dir_frame.pack(fill=tk.X, pady=(0, 10))

        # 图片文件夹
        self._add_dir_row(dir_frame, "图片文件夹：", self.image_dir, 0,
                          "选择包含 JPG/PNG/HEIC 图片的文件夹")
        # 视频文件夹
        self._add_dir_row(dir_frame, "视频文件夹：", self.video_dir, 1,
                          "选择包含 MOV/MP4 视频的文件夹（可与图片相同）")
        # 输出文件夹
        self._add_dir_row(dir_frame, "输出文件夹：", self.output_dir, 2,
                          "合并后的文件保存位置")

        # ===== 格式选择 =====
        fmt_frame = ttk.Frame(dir_frame)
        fmt_frame.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(8, 0))

        ttk.Label(fmt_frame, text="输出格式：").pack(side=tk.LEFT)
        fmt_combo = ttk.Combobox(fmt_frame, textvariable=self.output_format,
                                   values=list(OUTPUT_FORMATS.keys()),
                                   state='readonly', width=12)
        fmt_combo.pack(side=tk.LEFT, padx=(4, 8))
        fmt_combo.bind('<<ComboboxSelected>>', self._on_format_change)

        self.format_desc = ttk.Label(fmt_frame, text=OUTPUT_FORMATS['motion'],
                                       foreground='#0066cc', wraplength=500)
        self.format_desc.pack(side=tk.LEFT)

        # ===== 配对列表 =====
        list_frame = ttk.LabelFrame(main, text="文件配对", padding=8)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 工具栏
        toolbar = ttk.Frame(list_frame)
        toolbar.pack(fill=tk.X, pady=(0, 6))

        self.scan_btn = ttk.Button(toolbar, text="🔍 扫描配对", command=self._scan_pairs)
        self.scan_btn.pack(side=tk.LEFT)

        self.pair_count_label = ttk.Label(toolbar, text="已配对: 0 | 未配对图片: 0 | 未配对视频: 0",
                                            foreground='#666')
        self.pair_count_label.pack(side=tk.LEFT, padx=12)

        # 列表
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        columns = ('idx', 'image', 'video', 'status')
        self.tree = ttk.Treeview(list_container, columns=columns, show='headings', height=8)
        self.tree.heading('idx', text='#')
        self.tree.heading('image', text='图片文件')
        self.tree.heading('video', text='视频文件')
        self.tree.heading('status', text='状态')
        self.tree.column('idx', width=40, anchor=tk.CENTER)
        self.tree.column('image', width=220)
        self.tree.column('video', width=220)
        self.tree.column('status', width=80, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ===== 底部操作区 =====
        bottom = ttk.Frame(main)
        bottom.pack(fill=tk.X)

        # 进度条
        self.progress = ttk.Progressbar(bottom, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(0, 6))

        # 按钮行
        btn_row = ttk.Frame(bottom)
        btn_row.pack(fill=tk.X)

        self.start_btn = ttk.Button(btn_row, text="🚀 开始合并", style='Accent.TButton',
                                      command=self._start_combine)
        self.start_btn.pack(side=tk.LEFT)

        self.open_output_btn = ttk.Button(btn_row, text="📂 打开输出文件夹",
                                            command=self._open_output_dir)
        self.open_output_btn.pack(side=tk.LEFT, padx=8)

        self.status_label = ttk.Label(btn_row, text="就绪", foreground='#333')
        self.status_label.pack(side=tk.RIGHT)

        # ===== 日志区 =====
        log_frame = ttk.LabelFrame(main, text="运行日志", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=False, pady=(10, 0))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6,
                                                     font=('Consolas', 9),
                                                     bg='#1e1e1e', fg='#d4d4d4',
                                                     insertbackground='white')
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.configure(state=tk.DISABLED)

    def _add_dir_row(self, parent, label_text, var, row, placeholder=""):
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky=tk.W, pady=3)
        entry = ttk.Entry(parent, textvariable=var, width=55)
        entry.grid(row=row, column=1, sticky=tk.EW, padx=6, pady=3)
        btn = ttk.Button(parent, text="浏览...", width=8,
                          command=lambda v=var: self._browse_dir(v))
        btn.grid(row=row, column=2, pady=3)
        parent.columnconfigure(1, weight=1)

    def _browse_dir(self, var):
        d = filedialog.askdirectory(title="选择文件夹")
        if d:
            var.set(d)

    def _on_format_change(self, event=None):
        fmt = self.output_format.get()
        self.format_desc.config(text=OUTPUT_FORMATS.get(fmt, ''))
        # Apple 格式需要额外工具
        if fmt == 'apple':
            exif = check_exiftool()
            ff = check_ffmpeg()
            if not exif or not ff:
                missing = []
                if not exif:
                    missing.append('exiftool')
                if not ff:
                    missing.append('ffmpeg')
                self._log(f"⚠️ Apple Live Photo 格式需要: {', '.join(missing)}")
                self._log("   下载地址: exiftool.org / ffmpeg.org")

    def _check_tools(self):
        exif = check_exiftool()
        ff = check_ffmpeg()
        heic = check_heic_support()
        self._log(f"系统检测: Python {sys.version.split()[0]}")
        self._log(f"图片格式: HEIC支持={'✓' if heic else '✗(需安装 pillow-heif)'}")
        self._log(f"外部工具: exiftool={'✓' if exif else '✗'}  ffmpeg={'✓' if ff else '✗'}")
        if not heic:
            self._log("提示: iPhone照片为HEIC格式，请运行: pip install pillow-heif")
        if not exif or not ff:
            self._log("提示: 安装 exiftool 和 ffmpeg 可启用 Apple Live Photo 格式")
        self._log("-" * 50)

    def _scan_pairs(self):
        img_dir = self.image_dir.get().strip()
        vid_dir = self.video_dir.get().strip()

        if not img_dir or not os.path.isdir(img_dir):
            messagebox.showwarning("提示", "请先选择有效的图片文件夹")
            return
        if not vid_dir or not os.path.isdir(vid_dir):
            messagebox.showwarning("提示", "请先选择有效的视频文件夹")
            return

        self.pairs = pair_files(img_dir, vid_dir)
        unpaired_img, unpaired_vid = get_unpaired(img_dir, vid_dir, self.pairs)

        # 更新列表
        for item in self.tree.get_children():
            self.tree.delete(item)

        for i, (img, vid) in enumerate(self.pairs, 1):
            self.tree.insert('', tk.END, values=(
                i, img.name, vid.name, '待处理'
            ))

        self.pair_count_label.config(
            text=f"已配对: {len(self.pairs)} | 未配对图片: {len(unpaired_img)} | 未配对视频: {len(unpaired_vid)}"
        )

        self._log(f"扫描完成: 找到 {len(self.pairs)} 对文件")
        if unpaired_img:
            self._log(f"  未配对图片 ({len(unpaired_img)}): {', '.join(p.name for p in unpaired_img[:5])}{'...' if len(unpaired_img) > 5 else ''}")
        if unpaired_vid:
            self._log(f"  未配对视频 ({len(unpaired_vid)}): {', '.join(p.name for p in unpaired_vid[:5])}{'...' if len(unpaired_vid) > 5 else ''}")

        if not self.pairs:
            messagebox.showinfo("提示", "未找到可配对的文件。\n\n请确保图片和视频文件名相同（不含扩展名），\n例如: IMG_001.jpg 和 IMG_001.mov")

    def _start_combine(self):
        if self.is_running:
            return

        if not self.pairs:
            # 自动扫描一次
            self._scan_pairs()
            if not self.pairs:
                return

        out_dir = self.output_dir.get().strip()
        if not out_dir:
            # 默认在图片文件夹下创建输出目录
            img_dir = self.image_dir.get().strip()
            out_dir = os.path.join(img_dir, 'LivePhoto_Output')
            self.output_dir.set(out_dir)

        os.makedirs(out_dir, exist_ok=True)

        fmt = self.output_format.get()

        # 禁用按钮
        self.is_running = True
        self.start_btn.config(state=tk.DISABLED, text="处理中...")
        self.scan_btn.config(state=tk.DISABLED)
        self.progress['value'] = 0

        self._log(f"开始批量合并: 共 {len(self.pairs)} 对, 格式={fmt}")
        self._log(f"输出目录: {out_dir}")

        # 后台线程运行
        def worker():
            success, failed = batch_combine(
                self.pairs, out_dir, fmt,
                progress_cb=self._on_progress,
                log_cb=self._log,
            )
            # 回到主线程更新UI
            self.root.after(0, lambda: self._on_finish(success, failed, out_dir))

        threading.Thread(target=worker, daemon=True).start()

    def _on_progress(self, pct, msg):
        def update():
            self.progress['value'] = pct
            self.status_label.config(text=msg)
        self.root.after(0, update)

    def _on_finish(self, success, failed, out_dir):
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL, text="🚀 开始合并")
        self.scan_btn.config(state=tk.NORMAL)
        self.progress['value'] = 100
        self.status_label.config(text=f"完成: 成功{success} 失败{failed}")

        # 更新列表状态
        for i, item in enumerate(self.tree.get_children()):
            if i < success:
                self.tree.set(item, 'status', '✓ 成功')
            else:
                self.tree.set(item, 'status', '✗ 失败')

        self._log("=" * 50)
        self._log(f"全部完成! 成功: {success}, 失败: {failed}")
        self._log(f"输出目录: {out_dir}")

        if failed > 0:
            messagebox.showwarning("完成", f"处理完成！\n\n成功: {success}\n失败: {failed}\n\n请查看日志了解失败原因。")
        else:
            messagebox.showinfo("完成", f"全部处理成功！\n\n共 {success} 个文件已保存到:\n{out_dir}")

    def _open_output_dir(self):
        out_dir = self.output_dir.get().strip()
        if out_dir and os.path.isdir(out_dir):
            os.startfile(out_dir)
        else:
            messagebox.showinfo("提示", "输出文件夹不存在或未设置")

    def _log(self, msg):
        def append():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, msg + '\n')
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        self.root.after(0, append)


def main():
    root = tk.Tk()
    # 高DPI支持
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = LivePhotoApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
