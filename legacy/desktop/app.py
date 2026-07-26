import io
import json
import os
import queue
import shutil
import sys
import threading
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import customtkinter as ctk
from tkinter import filedialog, messagebox

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR / "huawei-inspection-platform"
LOGS_BASE = SCRIPT_DIR / "Logs_待处理"
OUTPUT_BASE = SCRIPT_DIR / "巡检报告"
TEMP_DIR = SCRIPT_DIR / ".temp_extracted"
SETTINGS_PATH = SCRIPT_DIR / ".app_settings.json"

sys.path.insert(0, str(PROJECT_DIR))
from core import generate_reports
from core.report_service import ReportPaths

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

KNOWN_SYS = ["TOC", "TOB", "GPRS", "Softswitch", "SMS", "IntelligentNet", "NM1", "NM2", "NM3"]

TEMP_KEEP_DAYS = 7
SELECTED_ROW_COLOR = ("gray80", "gray30")

with open(PROJECT_DIR / "config" / "report.json", "r", encoding="utf-8") as _f:
    FULL_CONFIG = json.load(_f)


# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------
def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_settings(data: dict) -> None:
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def extract_zip(zip_path: Path) -> Path:
    dest = TEMP_DIR / zip_path.stem
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    entries = list(dest.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return dest


def cleanup_temp_dirs() -> None:
    """清理 .temp_extracted 下超过 TEMP_KEEP_DAYS 天未使用的解压目录"""
    if not TEMP_DIR.exists():
        return
    deadline = datetime.now().timestamp() - TEMP_KEEP_DAYS * 86400
    for p in TEMP_DIR.iterdir():
        try:
            if p.is_dir() and p.stat().st_mtime < deadline:
                shutil.rmtree(p, ignore_errors=True)
        except OSError:
            pass


def count_logs(root: Path) -> int:
    return sum(1 for _ in root.rglob("*.log") if "summary" not in _.name)


def preview_system_stats(log_root: Path) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for key in KNOWN_SYS:
        info = FULL_CONFIG.get(key, {})
        hosts = info.get("hosts", {})
        expected = len(hosts)
        log_dir = log_root / key
        if not log_dir.exists():
            log_dir = log_root / key.replace("NM", "NetMgmt")
        actual = len(list(log_dir.glob("*.log"))) if log_dir.exists() else 0
        stats[key] = {
            "display_name": info.get("display_name", key),
            "expected": expected if expected > 0 else actual,
            "actual": actual,
            "has_logs": actual > 0,
        }
    return stats


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.title("华为巡检报告生成工具")
        self.geometry("950x800")
        self.minsize(800, 680)

        self.settings = load_settings()

        self.progress_queue: queue.Queue = queue.Queue()
        self.running = False
        self.batch_items: list[dict] = []  # {path, name, system_count, log_count}
        self.batch_rows: list[ctk.CTkFrame] = []
        self.selected_batch_index: int = -1
        self.preview_cache: dict[str, dict] = {}
        self.result_files: list[Path] = []

        cleanup_temp_dirs()

        self._build_ui()
        self._load_saved_settings()
        self._auto_scan_logs()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ==================================================================
    # UI Construction
    # ==================================================================
    def _build_ui(self):
        # -- Title bar row --
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(title_frame, text="华为巡检报告生成工具",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        self.theme_switch = ctk.CTkSwitch(title_frame, text="深色模式",
                                           command=self._toggle_theme,
                                           font=ctk.CTkFont(size=12))
        self.theme_switch.pack(side="right")
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()

        # -- Drop zone --
        drop_frame = ctk.CTkFrame(self, height=70, corner_radius=12,
                                   fg_color=("gray90", "gray20"),
                                   border_width=2,
                                   border_color=("gray60", "gray50"))
        drop_frame.pack(fill="x", padx=20, pady=(5, 10))
        drop_frame.bind("<Button-1>", self._drop_zone_click)
        self.drop_label = ctk.CTkLabel(drop_frame, text="📂  点击选择 ZIP 文件",
                                        font=ctk.CTkFont(size=14),
                                        text_color=("gray40", "gray60"))
        self.drop_label.place(relx=0.5, rely=0.5, anchor="center")
        self.drop_label.bind("<Button-1>", self._drop_zone_click)

        # -- Batch list --
        batch_frame = ctk.CTkFrame(self)
        batch_frame.pack(fill="x", padx=20, pady=(0, 8))

        batch_header = ctk.CTkFrame(batch_frame, fg_color="transparent")
        batch_header.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(batch_header, text="待处理列表",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkButton(batch_header, text="+ 添加文件", width=90, height=28,
                      command=self._add_batch_file).pack(side="right", padx=4)
        ctk.CTkButton(batch_header, text="移除选中", width=80, height=28,
                      command=self._remove_batch_item).pack(side="right", padx=4)

        self.batch_scroll = ctk.CTkScrollableFrame(batch_frame, height=100)
        self.batch_scroll.pack(fill="x", padx=10, pady=(0, 8))

        self.batch_inner_frame = None

        # -- Preview --
        prev_frame = ctk.CTkFrame(self)
        prev_frame.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        prev_header = ctk.CTkFrame(prev_frame, fg_color="transparent")
        prev_header.pack(fill="x", padx=10, pady=(8, 4))
        self.prev_title = ctk.CTkLabel(prev_header, text="系统预览（请先选择左侧的日志文件）",
                                        font=ctk.CTkFont(size=14, weight="bold"))
        self.prev_title.pack(side="left")
        ctk.CTkButton(prev_header, text="全选", width=60, height=26,
                      command=self._preview_select_all).pack(side="right", padx=4)
        ctk.CTkButton(prev_header, text="取消", width=60, height=26,
                      command=self._preview_deselect_all).pack(side="right", padx=4)

        self.prev_scroll = ctk.CTkScrollableFrame(prev_frame)
        self.prev_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.prev_checkboxes: dict[str, ctk.CTkCheckBox] = {}
        self.prev_bars: dict[str, ctk.CTkProgressBar] = {}
        self.prev_stats_labels: dict[str, ctk.CTkLabel] = {}

        # -- Settings row --
        set_frame = ctk.CTkFrame(self, fg_color="transparent")
        set_frame.pack(fill="x", padx=20, pady=(0, 5))

        ctk.CTkLabel(set_frame, text="报告日期：", font=ctk.CTkFont(size=13)).pack(side="left")
        self.date_entry = ctk.CTkEntry(set_frame, width=130, height=32,
                                        placeholder_text="YYYY-MM-DD")
        self.date_entry.pack(side="left", padx=(5, 20))
        self.date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

        ctk.CTkLabel(set_frame, text="输出目录：", font=ctk.CTkFont(size=13)).pack(side="left")
        self.output_entry = ctk.CTkEntry(set_frame, width=320, height=32)
        self.output_entry.pack(side="left", padx=(5, 5))
        self.output_entry.insert(0, str(OUTPUT_BASE))
        ctk.CTkButton(set_frame, text="浏览", width=60, height=32,
                      command=self._browse_output).pack(side="left")

        # -- Progress --
        prog_frame = ctk.CTkFrame(self)
        prog_frame.pack(fill="x", padx=20, pady=(0, 8))

        self.progress_bar = ctk.CTkProgressBar(prog_frame, height=20)
        self.progress_bar.pack(fill="x", padx=10, pady=(10, 5))
        self.progress_bar.set(0)
        self.progress_label = ctk.CTkLabel(prog_frame, text="就绪",
                                            font=ctk.CTkFont(size=12))
        self.progress_label.pack(anchor="w", padx=10, pady=(2, 8))

        # -- Action buttons --
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(5, 10))

        self.gen_btn = ctk.CTkButton(btn_frame, text="开始生成报告", height=44,
                                      font=ctk.CTkFont(size=15, weight="bold"),
                                      command=self._start_generate)
        self.gen_btn.pack(side="left", padx=(10, 8))
        ctk.CTkButton(btn_frame, text="打开输出目录", width=120, height=36,
                      command=self._open_output).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="打开最新报告", width=120, height=36,
                      command=self._open_last_report).pack(side="left", padx=4)

        # -- Results log --
        self.result_text = ctk.CTkTextbox(self, height=120, font=ctk.CTkFont(size=12),
                                           wrap="word")
        self.result_text.pack(fill="x", padx=20, pady=(0, 15))
        self.result_text.configure(state="disabled")

    # ==================================================================
    # Theme
    # ==================================================================
    def _toggle_theme(self):
        mode = "Dark" if self.theme_switch.get() else "Light"
        ctk.set_appearance_mode(mode)

    # ==================================================================
    # Settings persistence
    # ==================================================================
    def _load_saved_settings(self):
        out = self.settings.get("output_dir")
        if out:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, out)

    def _save_settings_now(self):
        self.settings["output_dir"] = self.output_entry.get()
        self.settings.pop("date", None)
        save_settings(self.settings)

    # ==================================================================
    # Drop zone
    # ==================================================================
    def _drop_zone_click(self, event=None):
        self._add_batch_file()

    def _auto_scan_logs(self):
        if not LOGS_BASE.exists():
            return
        for f in sorted(LOGS_BASE.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
            self._add_item(f)

    def _add_batch_file(self):
        paths = filedialog.askopenfilenames(
            title="选择日志 ZIP 文件",
            filetypes=[("ZIP 压缩包", "*.zip"), ("所有文件", "*.*")],
            initialdir=str(LOGS_BASE) if LOGS_BASE.exists() else str(SCRIPT_DIR),
        )
        for p in paths:
            self._add_item(Path(p))

    def _add_item(self, path: Path):
        if not path.exists() or path.suffix.lower() != ".zip":
            return
        for item in self.batch_items:
            if item["path"] == path:
                return
        try:
            with zipfile.ZipFile(path) as zf:
                dirs = set()
                log_count = 0
                for name in zf.namelist():
                    parts = name.split("/")
                    if len(parts) >= 2 and not name.endswith("/"):
                        d = parts[1] if parts[1] else parts[0]
                        dirs.add(d)
                        if name.endswith(".log"):
                            log_count += 1
                sys_count = len(dirs & set(KNOWN_SYS))
        except Exception:
            sys_count = 0
            log_count = 0

        item = {"path": path, "name": path.name, "system_count": sys_count,
                "log_count": log_count}
        self.batch_items.append(item)
        self._refresh_batch_list()

    def _remove_batch_item(self):
        if 0 <= self.selected_batch_index < len(self.batch_items):
            removed = self.batch_items.pop(self.selected_batch_index)
            self.preview_cache.pop(str(removed["path"]), None)
            self.selected_batch_index = -1
            self._refresh_batch_list()
            self._clear_preview()

    def _refresh_batch_list(self):
        for w in self.batch_scroll.winfo_children():
            w.destroy()
        self.batch_rows = []
        self._refresh_gen_btn_text()

        if not self.batch_items:
            lbl = ctk.CTkLabel(self.batch_scroll, text="（暂无文件，请点击上方区域添加 ZIP）",
                               text_color="gray")
            lbl.pack(pady=15)
            return

        for idx, item in enumerate(self.batch_items):
            is_selected = idx == self.selected_batch_index
            row = ctk.CTkFrame(self.batch_scroll,
                               fg_color=SELECTED_ROW_COLOR if is_selected else "transparent")
            row.pack(fill="x", pady=2)
            row.bind("<Button-1>", lambda e, i=idx: self._select_batch(i))
            self.batch_rows.append(row)

            name_lbl = ctk.CTkLabel(
                row,
                text=f"{item['name']}   |   {item['system_count']} 个系统   |   {item['log_count']} 个日志",
                font=ctk.CTkFont(size=12),
                anchor="w",
            )
            name_lbl.pack(side="left", fill="x", expand=True, padx=10, pady=2)
            name_lbl.bind("<Button-1>", lambda e, i=idx: self._select_batch(i))

    def _gen_btn_text(self) -> str:
        if 0 <= self.selected_batch_index < len(self.batch_items):
            return f"开始生成报告（{self.batch_items[self.selected_batch_index]['name']}）"
        return "开始生成报告"

    def _refresh_gen_btn_text(self):
        if not self.running:
            self.gen_btn.configure(text=self._gen_btn_text())

    def _select_batch(self, idx):
        if 0 <= self.selected_batch_index < len(self.batch_rows):
            self.batch_rows[self.selected_batch_index].configure(fg_color="transparent")
        self.selected_batch_index = idx
        if 0 <= idx < len(self.batch_rows):
            self.batch_rows[idx].configure(fg_color=SELECTED_ROW_COLOR)
        self._refresh_gen_btn_text()
        self._show_preview(idx)

    # ==================================================================
    # Preview
    # ==================================================================
    def _clear_preview(self):
        for w in self.prev_scroll.winfo_children():
            w.destroy()
        self.prev_checkboxes.clear()
        self.prev_bars.clear()
        self.prev_stats_labels.clear()
        self.prev_title.configure(text="系统预览（请先选择左侧的日志文件）")

    def _cached_extract(self, zip_path: Path) -> dict:
        """取解压结果；ZIP 已更新或解压目录被清理时重新解压"""
        cache_key = str(zip_path)
        st = zip_path.stat()
        signature = (st.st_mtime, st.st_size)
        cached = self.preview_cache.get(cache_key)
        if (cached and cached.get("signature") == signature
                and Path(cached["log_root"]).exists()):
            return cached
        log_root = extract_zip(zip_path)
        data = {
            "log_root": log_root,
            "signature": signature,
            "stats": preview_system_stats(log_root),
        }
        self.preview_cache[cache_key] = data
        return data

    def _show_preview(self, idx):
        if idx < 0 or idx >= len(self.batch_items):
            return
        item = self.batch_items[idx]
        zip_path = item["path"]

        try:
            data = self._cached_extract(zip_path)
        except Exception as e:
            self._log_msg(f"解压失败：{e}")
            return
        stats = data["stats"]

        for w in self.prev_scroll.winfo_children():
            w.destroy()
        self.prev_checkboxes.clear()
        self.prev_bars.clear()
        self.prev_stats_labels.clear()

        self.prev_title.configure(text=f"系统预览 — {item['name']}")

        for key in KNOWN_SYS:
            info = stats.get(key, {})
            if not info:
                continue
            expected = info["expected"]
            actual = info["actual"]
            has = info["has_logs"]
            ratio = actual / max(expected, 1)

            row = ctk.CTkFrame(self.prev_scroll, fg_color="transparent")
            row.pack(fill="x", pady=3)

            var = ctk.BooleanVar(value=has)
            cb = ctk.CTkCheckBox(row, text="", variable=var, width=20)
            cb.pack(side="left", padx=(5, 2))
            self.prev_checkboxes[key] = var

            label_text = f"{info['display_name']:12s}   {actual:3d}/{expected:<3d}"
            icon = "✅" if ratio >= 1.0 else ("⚠️" if ratio >= 0.5 else "❌")
            ctk.CTkLabel(row, text=f"{icon} {label_text}",
                         font=ctk.CTkFont(size=12), width=220, anchor="w").pack(side="left", padx=2)

            bar = ctk.CTkProgressBar(row, width=250, height=14)
            bar.pack(side="left", padx=5)
            bar.set(min(ratio, 1.0))
            self.prev_bars[key] = bar

            if actual < expected and expected > 0:
                hint = f"缺 {expected - actual} 台设备"
            elif not has:
                hint = "无日志"
            else:
                hint = "已就绪"
            lbl = ctk.CTkLabel(row, text=hint, font=ctk.CTkFont(size=11),
                              text_color="gray", width=80, anchor="w")
            lbl.pack(side="left", padx=5)
            self.prev_stats_labels[key] = lbl

    def _preview_select_all(self):
        for v in self.prev_checkboxes.values():
            v.set(True)

    def _preview_deselect_all(self):
        for v in self.prev_checkboxes.values():
            v.set(False)

    def _browse_output(self):
        path = filedialog.askdirectory(
            title="选择输出目录",
            initialdir=str(OUTPUT_BASE) if OUTPUT_BASE.exists() else str(SCRIPT_DIR),
        )
        if path:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, path)

    # ==================================================================
    # Generate
    # ==================================================================
    def _start_generate(self):
        if self.running:
            messagebox.showinfo("提示", "报告生成正在进行中...")
            return

        self._save_settings_now()

        selected = [k for k, v in self.prev_checkboxes.items() if v.get()]
        if not selected:
            messagebox.showwarning("提示", "请先在系统预览中勾选至少一个系统。")
            return

        if self.selected_batch_index < 0:
            messagebox.showwarning("提示", "请先在待处理列表中点击选择一个 ZIP 文件。")
            return

        report_date = self.date_entry.get().strip()
        try:
            datetime.strptime(report_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("提示", "报告日期格式不正确，请按 YYYY-MM-DD 填写，例如 "
                                           f"{datetime.now().strftime('%Y-%m-%d')}。")
            self.date_entry.focus_set()
            return

        item = self.batch_items[self.selected_batch_index]
        zip_path = item["path"]

        try:
            log_root = self._cached_extract(zip_path)["log_root"]
        except Exception as e:
            messagebox.showerror("错误", f"解压失败：\n{e}")
            return

        filtered_config = {k: v for k, v in FULL_CONFIG.items() if k in selected}
        config_path = TEMP_DIR / "report_filtered.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(filtered_config, f, ensure_ascii=False, indent=2)

        output_root = Path(self.output_entry.get()) if self.output_entry.get() else (OUTPUT_BASE / report_date)
        output_dir = output_root / report_date if output_root.name != report_date else output_root

        self.result_files = []
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.configure(state="disabled")

        self.running = True
        self.gen_btn.configure(state="disabled", text="生成中...")
        self.progress_bar.set(0)
        self.progress_label.configure(text="正在启动...")

        paths = ReportPaths(
            root=PROJECT_DIR,
            config_path=config_path,
            logs_base=log_root.parent if log_root.parent.exists() else log_root,
            templates_dir=PROJECT_DIR / "assets" / "templates",
            output_base=output_dir,
        )

        thread = threading.Thread(
            target=self._run_generation,
            args=(paths, log_root, report_date, output_dir, len(filtered_config)),
            daemon=True,
        )
        thread.start()
        self._poll_progress()

    def _run_generation(self, paths, log_root, report_date, output_dir, total):
        try:
            def cb(completed, total_cnt, key, info):
                self.progress_queue.put(("progress", completed, total_cnt, info["display_name"]))

            summary = generate_reports(
                paths=paths, log_root=log_root, target_date=report_date,
                output_dir=output_dir, progress_callback=cb, max_workers=4,
            )
            self.progress_queue.put(("done", summary))
        except Exception as e:
            self.progress_queue.put(("error", str(e)))

    def _poll_progress(self):
        try:
            while True:
                msg = self.progress_queue.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    _, completed, total, label = msg
                    pct = completed / max(total, 1)
                    self.progress_bar.set(pct)
                    self.progress_label.configure(text=f"{int(pct * 100):3d}%  {label}")
                elif kind == "done":
                    summary = msg[1]
                    self.result_files = [Path(f) for f in summary.generated_files]
                    self._show_results(summary)
                    self.running = False
                    self.gen_btn.configure(state="normal", text=self._gen_btn_text())
                    self.progress_bar.set(1)
                    self.progress_label.configure(text="生成完成！")
                    self._notify_done(len(summary.generated_files))
                    return
                elif kind == "error":
                    messagebox.showerror("错误", msg[1])
                    self.running = False
                    self.gen_btn.configure(state="normal", text=self._gen_btn_text())
                    self.progress_label.configure(text=f"错误：{msg[1][:80]}")
                    return
        except queue.Empty:
            pass
        if self.running:
            self.after(100, self._poll_progress)

    def _show_results(self, summary):
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("end", f"输出目录：{summary.output_dir}\n")
        self.result_text.insert("end", f"生成报告：{len(summary.generated_files)} 份\n")
        self.result_text.insert("end", "─" * 50 + "\n")
        for f in sorted(summary.generated_files):
            self.result_text.insert("end", f"  ✓ {Path(f).name}\n")
        self.result_text.insert("end", "─" * 50 + "\n")
        self.result_text.insert("end", f"匹配日志：{summary.output_dir}\\audit_matching_result.txt\n")
        self.result_text.configure(state="disabled")

    # ==================================================================
    # Notification
    # ==================================================================
    def _notify_done(self, count):
        self.after(200, lambda: self._toast(count))

    def _toast(self, count):
        try:
            from plyer import notification
            notification.notify(
                title="巡检报告生成完毕",
                message=f"成功生成 {count} 份报告",
                app_name="华为巡检报告生成工具",
                timeout=5,
            )
        except Exception:
            pass

    # ==================================================================
    # Actions
    # ==================================================================
    def _open_output(self):
        out = Path(self.output_entry.get()) if self.output_entry.get() else OUTPUT_BASE
        if out.exists():
            os.startfile(str(out))
        elif OUTPUT_BASE.exists():
            os.startfile(str(OUTPUT_BASE))
        else:
            messagebox.showinfo("提示", "暂无输出目录。")

    def _open_last_report(self):
        files = self.result_files if self.result_files else (
            list(OUTPUT_BASE.rglob("*.docx")) if OUTPUT_BASE.exists() else [])
        files = [f for f in files if f.exists()]
        if files:
            os.startfile(str(max(files, key=lambda p: p.stat().st_mtime)))
        else:
            messagebox.showinfo("提示", "未找到报告文件。")

    def _log_msg(self, msg):
        self.result_text.configure(state="normal")
        self.result_text.insert("end", f"{msg}\n")
        self.result_text.see("end")
        self.result_text.configure(state="disabled")

    def _on_close(self):
        if self.running and not messagebox.askyesno("确认退出", "报告正在生成中，确定退出？"):
            return
        self._save_settings_now()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
