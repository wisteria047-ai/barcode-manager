#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
パスポート管理アプリケーション
- CSVファイルからパスポートデータを取り込み（任意のCSV構造に対応）
- Code128バーコードを生成・印刷
- バーコードスキャンによるステータス管理（回収済み/返却済み）
- リアルタイム履歴ログ
- JSONファイルによるデータ永続化
- レコード編集機能
- カラム並べ替え・表示名編集・表示/非表示設定
- テーブルヘッダーソート
- バーコードラベル印刷（項目別バーコード/テキスト/非表示選択、位置調整・PDF出力）
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import json
import os
import sys
import datetime
import tempfile
import subprocess
from io import BytesIO
import math

import shutil

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("警告: Pillowがインストールされていません。pip install Pillow でインストールしてください。")


# ==============================================================================
# クロスプラットフォーム パスユーティリティ
# ==============================================================================

def get_data_dir() -> str:
    """書き込み可能なデータディレクトリを取得"""
    if getattr(sys, 'frozen', False):
        # PyInstallerバンドル実行時
        if sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support")
        elif sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        else:
            base = os.path.expanduser("~/.local/share")
        data_dir = os.path.join(base, "PassportManager")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    else:
        # 開発時: スクリプトと同じディレクトリ
        return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(relative_path: str) -> str:
    """バンドル内の読み取り専用リソースパスを取得"""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


# ==============================================================================
# Code128 バーコード生成 (純粋Python実装)
# ==============================================================================

CODE128_PATTERNS = [
    "11011001100", "11001101100", "11001100110", "10010011000", "10010001100",
    "10001001100", "10011001000", "10011000100", "10001100100", "11001001000",
    "11001000100", "11000100100", "10110011100", "10011011100", "10011001110",
    "10111001100", "10011101100", "10011100110", "11001110010", "11001011100",
    "11001001110", "11011100100", "11001110100", "11101101110", "11101001100",
    "11100101100", "11100100110", "11101100100", "11100110100", "11100110010",
    "11011011000", "11011000110", "11000110110", "10100011000", "10001011000",
    "10001000110", "10110001000", "10001101000", "10001100010", "11010001000",
    "11000101000", "11000100010", "10110111000", "10110001110", "10001101110",
    "10111011000", "10111000110", "10001110110", "11101110110", "11010001110",
    "11000101110", "11011101000", "11011100010", "11011101110", "11101011000",
    "11101000110", "11100010110", "11101101000", "11101100010", "11100011010",
    "11101111010", "11001000010", "11110001010", "10100110000", "10100001100",
    "10010110000", "10010000110", "10000101100", "10000100110", "10110010000",
    "10110000100", "10011010000", "10011000010", "10000110100", "10000110010",
    "11000010010", "11001010000", "11110111010", "11000010100", "10001111010",
    "10100111100", "10010111100", "10010011110", "10111100100", "10011110100",
    "10011110010", "11110100100", "11110010100", "11110010010", "11011011110",
    "11011110110", "11110110110", "10101111000", "10100011110", "10001011110",
    "10111101000", "10111100010", "11110101000", "11110100010", "10111011110",
    "10111101110", "11101011110", "11110101110", "11010000100", "11010010000",
    "11010011100", "1100011101011",
]

CODE128B_START = 104
CODE128_STOP = 106


def encode_code128b(data: str) -> list:
    values = []
    values.append(CODE128B_START)
    for char in data:
        code = ord(char) - 32
        if code < 0 or code > 95:
            raise ValueError(f"Code128Bでエンコードできない文字: {char}")
        values.append(code)
    checksum = values[0]
    for i, val in enumerate(values[1:], 1):
        checksum += i * val
    checksum %= 103
    values.append(checksum)
    values.append(CODE128_STOP)
    return values


def _get_japanese_font(size: int = 14):
    font_paths = [
        # macOS
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        # Windows
        "C:/Windows/Fonts/msgothic.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
        "C:/Windows/Fonts/YuGothR.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msmincho.ttc",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def generate_code128_image(data: str, width: int = 400, height: int = 120,
                           quiet_zone: int = 20, show_text: bool = True) -> Image.Image:
    values = encode_code128b(data)
    pattern = "".join(CODE128_PATTERNS[v] for v in values)
    total_bars = len(pattern)
    available_width = width - 2 * quiet_zone
    bar_width = max(1, available_width // total_bars)
    actual_width = bar_width * total_bars + 2 * quiet_zone
    text_height = 25 if show_text else 0
    total_height = height + text_height + 10
    img = Image.new("RGB", (actual_width, total_height), "white")
    draw = ImageDraw.Draw(img)
    x = quiet_zone
    for bit in pattern:
        if bit == "1":
            draw.rectangle([x, 5, x + bar_width - 1, height + 5], fill="black")
        x += bar_width
    if show_text:
        font = _get_japanese_font(14)
        bbox = draw.textbbox((0, 0), data, font=font)
        text_w = bbox[2] - bbox[0]
        text_x = (actual_width - text_w) // 2
        draw.text((text_x, height + 10), data, fill="black", font=font)
    return img


# ==============================================================================
# データ管理クラス
# ==============================================================================

class PassportDataManager:
    def __init__(self, data_file: str = "passport_data.json"):
        self.data_file = data_file
        self.records = []
        self.history = []
        self.csv_columns = []
        self.barcode_column = None
        self.display_columns = []      # 表示順序（サブセット可）
        self.column_aliases = {}       # {元カラム名: 表示名}
        self.column_order = []         # 全カラム（管理列含む）の表示順
        self.load()

    def load(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.records = data.get("records", [])
                self.history = data.get("history", [])
                self.csv_columns = data.get("csv_columns", [])
                self.barcode_column = data.get("barcode_column", None)
                self.display_columns = data.get("display_columns", [])
                self.column_aliases = data.get("column_aliases", {})
                self.column_order = data.get("column_order", [])
            except (json.JSONDecodeError, IOError) as e:
                print(f"データ読み込みエラー: {e}")

    def save(self):
        data = {
            "records": self.records,
            "history": self.history,
            "csv_columns": self.csv_columns,
            "barcode_column": self.barcode_column,
            "display_columns": self.display_columns,
            "column_aliases": self.column_aliases,
            "column_order": self.column_order,
        }
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"データ保存エラー: {e}")

    def get_display_columns(self):
        """表示用カラムリストを取得。未設定なら csv_columns をフォールバック"""
        if self.display_columns:
            # csv_columnsに存在するもののみ
            return [c for c in self.display_columns if c in self.csv_columns]
        return list(self.csv_columns)

    def get_column_display_name(self, col: str) -> str:
        """カラムの表示名を取得"""
        return self.column_aliases.get(col, col)

    def import_csv(self, filepath: str, encoding: str = "utf-8") -> int:
        imported = 0
        try:
            with open(filepath, "r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames:
                    self.csv_columns = list(reader.fieldnames)
                    # display_columnsが空なら初期化
                    if not self.display_columns:
                        self.display_columns = list(self.csv_columns)

                for row in reader:
                    record = dict(row)
                    record["_status"] = "回収済み"
                    record["_barcode_id"] = self._generate_barcode_id(record)
                    record["_imported_at"] = datetime.datetime.now().isoformat()
                    self.records.append(record)
                    imported += 1

            self.add_history("CSV取り込み", f"{os.path.basename(filepath)} から {imported}件 取り込み")
            self.save()
        except Exception as e:
            raise RuntimeError(f"CSV読み込みエラー: {e}")
        return imported

    def _generate_barcode_id(self, record: dict) -> str:
        if self.barcode_column and self.barcode_column in record:
            return record[self.barcode_column]
        return f"PP{len(self.records):06d}"

    def find_by_barcode(self, barcode_value: str) -> list:
        results = []
        for i, rec in enumerate(self.records):
            if rec.get("_barcode_id") == barcode_value:
                results.append((i, rec))
            else:
                for key, val in rec.items():
                    if not key.startswith("_") and str(val) == barcode_value:
                        results.append((i, rec))
                        break
        return results

    def update_status(self, index: int, new_status: str):
        if 0 <= index < len(self.records):
            old_status = self.records[index].get("_status", "不明")
            self.records[index]["_status"] = new_status
            barcode_id = self.records[index].get("_barcode_id", "N/A")
            self.add_history("ステータス変更", f"ID:{barcode_id} {old_status} → {new_status}")
            self.save()

    def update_record(self, index: int, updates: dict) -> list:
        if not (0 <= index < len(self.records)):
            return []
        changes = []
        rec = self.records[index]
        for key, new_val in updates.items():
            old_val = str(rec.get(key, ""))
            if str(new_val) != old_val:
                changes.append(f"{key}: '{old_val}' → '{new_val}'")
                rec[key] = new_val
        if changes:
            barcode_id = rec.get("_barcode_id", "N/A")
            detail = f"ID:{barcode_id} | " + " | ".join(changes[:5])
            if len(changes) > 5:
                detail += f" ...他{len(changes)-5}件"
            self.add_history("レコード編集", detail)
            self.save()
        return changes

    def add_history(self, action: str, detail: str):
        entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "detail": detail,
        }
        self.history.append(entry)
        self.save()

    def delete_record(self, index: int):
        if 0 <= index < len(self.records):
            rec = self.records.pop(index)
            barcode_id = rec.get("_barcode_id", "N/A")
            self.add_history("レコード削除", f"ID:{barcode_id} を削除")
            self.save()

    def clear_all(self):
        count = len(self.records)
        self.records.clear()
        self.add_history("全データクリア", f"{count}件のレコードを削除")
        self.save()


# ==============================================================================
# ラベル印刷ダイアログ
# ==============================================================================

PAPER_SIZES = {
    "A4": (210, 297), "A4 横": (297, 210),
    "Letter": (215.9, 279.4), "B5": (176, 250), "はがき": (100, 148),
}

LABEL_PRESETS = {
    "A-one 72224 (24面)": {
        "paper_size": "A4", "margin_top": 13.0, "margin_bottom": 13.0,
        "margin_left": 8.0, "margin_right": 8.0,
        "label_width": 64.0, "label_height": 33.9,
        "spacing_h": 2.0, "spacing_v": 0.0, "cols": 3, "rows": 8,
    },
    "A-one 72312 (12面)": {
        "paper_size": "A4", "margin_top": 13.5, "margin_bottom": 13.5,
        "margin_left": 9.0, "margin_right": 9.0,
        "label_width": 86.4, "label_height": 42.3,
        "spacing_h": 2.5, "spacing_v": 0.0, "cols": 2, "rows": 6,
    },
    "A4 標準 (10面)": {
        "paper_size": "A4", "margin_top": 15.0, "margin_bottom": 15.0,
        "margin_left": 15.0, "margin_right": 15.0,
        "label_width": 85.0, "label_height": 50.0,
        "spacing_h": 5.0, "spacing_v": 3.4, "cols": 2, "rows": 5,
    },
    "カスタム": {},
}


class LabelPrintDialog:
    def __init__(self, parent, records, data_mgr, colors):
        self.parent = parent
        self.records = records
        self.data_mgr = data_mgr
        self.COLORS = colors
        self.current_page = 0
        self.total_pages = 1

        # 項目別印刷モード: {カラム名: "barcode"/"text"/"none"}
        self.field_print_modes = {}
        for col in data_mgr.csv_columns:
            if col == data_mgr.barcode_column:
                self.field_print_modes[col] = "barcode"
            else:
                self.field_print_modes[col] = "none"

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("バーコードラベル印刷")
        self.dialog.geometry("1050x750")
        self.dialog.minsize(900, 650)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_ui()
        self._update_preview()

    def _create_ui(self):
        # Notebook で設定を「レイアウト」と「印刷内容」に分ける
        main_pw = ttk.PanedWindow(self.dialog, orient="horizontal")
        main_pw.pack(fill="both", expand=True, padx=5, pady=5)

        # 左: 設定タブ
        left_notebook = ttk.Notebook(main_pw)
        main_pw.add(left_notebook, weight=2)

        # タブ1: レイアウト設定
        layout_outer = ttk.Frame(left_notebook)
        left_notebook.add(layout_outer, text="レイアウト")

        layout_canvas = tk.Canvas(layout_outer, highlightthickness=0)
        layout_sb = ttk.Scrollbar(layout_outer, orient="vertical", command=layout_canvas.yview)
        self.layout_frame = ttk.Frame(layout_canvas)
        self.layout_frame.bind("<Configure>",
                               lambda e: layout_canvas.configure(scrollregion=layout_canvas.bbox("all")))
        layout_canvas.create_window((0, 0), window=self.layout_frame, anchor="nw")
        layout_canvas.configure(yscrollcommand=layout_sb.set)
        layout_canvas.pack(side="left", fill="both", expand=True)
        layout_sb.pack(side="right", fill="y")

        self._create_layout_panel(self.layout_frame)

        # タブ2: 印刷内容設定
        content_outer = ttk.Frame(left_notebook)
        left_notebook.add(content_outer, text="印刷内容")
        self._create_content_panel(content_outer)

        # 右: プレビュー
        right_frame = ttk.Frame(main_pw)
        main_pw.add(right_frame, weight=3)

        ttk.Label(right_frame, text="プレビュー",
                  font=("Helvetica", 12, "bold")).pack(anchor="w", padx=5, pady=(5, 0))

        self.preview_canvas = tk.Canvas(right_frame, bg="white",
                                         highlightthickness=1,
                                         highlightbackground="#CBD5E1")
        self.preview_canvas.pack(fill="both", expand=True, padx=5, pady=5)
        self.preview_canvas.bind("<Configure>", lambda e: self._update_preview())

        nav_frame = ttk.Frame(right_frame)
        nav_frame.pack(fill="x", padx=5, pady=2)
        ttk.Button(nav_frame, text="< 前", command=self._prev_page).pack(side="left")
        self.page_label = ttk.Label(nav_frame, text="1 / 1")
        self.page_label.pack(side="left", padx=15)
        ttk.Button(nav_frame, text="次 >", command=self._next_page).pack(side="left")
        ttk.Label(nav_frame, text=f"対象: {len(self.records)}件").pack(side="right")

        # 下部ボタン
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(fill="x", padx=10, pady=8)
        ttk.Button(btn_frame, text="プレビュー更新", command=self._update_preview).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="PDF保存", command=self._save_pdf).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="印刷", command=self._print_labels).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="閉じる", command=self.dialog.destroy).pack(side="right", padx=3)

    def _create_layout_panel(self, parent):
        row = 0
        # プリセット
        ttk.Label(parent, text="プリセット:", font=("Helvetica", 10, "bold")).grid(row=row, column=0, sticky="e", padx=5, pady=3)
        self.preset_var = tk.StringVar(value="A4 標準 (10面)")
        combo = ttk.Combobox(parent, textvariable=self.preset_var, values=list(LABEL_PRESETS.keys()), state="readonly", width=22)
        combo.grid(row=row, column=1, sticky="w", padx=5, pady=3)
        combo.bind("<<ComboboxSelected>>", self._on_preset_change)
        row += 1

        # プリセット説明ラベル
        self.preset_info_label = ttk.Label(parent, text="", font=("Helvetica", 8),
                                            foreground="#64748B", wraplength=300)
        self.preset_info_label.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 3))
        self._update_preset_info()
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=5); row += 1

        # 用紙
        ttk.Label(parent, text="用紙サイズ:").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.paper_var = tk.StringVar(value="A4")
        ttk.Combobox(parent, textvariable=self.paper_var, values=list(PAPER_SIZES.keys()), state="readonly", width=15).grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1

        # 余白
        ttk.Label(parent, text="余白 (mm)", font=("Helvetica", 9, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(8, 2)); row += 1
        mf = ttk.Frame(parent); mf.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        self.margin_top_var = tk.DoubleVar(value=15.0)
        self.margin_bottom_var = tk.DoubleVar(value=15.0)
        self.margin_left_var = tk.DoubleVar(value=15.0)
        self.margin_right_var = tk.DoubleVar(value=15.0)
        for i, (lb, vr) in enumerate([("上:", self.margin_top_var), ("下:", self.margin_bottom_var),
                                       ("左:", self.margin_left_var), ("右:", self.margin_right_var)]):
            ttk.Label(mf, text=lb).grid(row=i//2, column=(i%2)*2, sticky="e", padx=2)
            ttk.Entry(mf, textvariable=vr, width=7).grid(row=i//2, column=(i%2)*2+1, sticky="w", padx=2, pady=1)
        row += 1

        # ラベルサイズ
        ttk.Label(parent, text="ラベルサイズ (mm)", font=("Helvetica", 9, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(8, 2)); row += 1
        sf = ttk.Frame(parent); sf.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        self.label_w_var = tk.DoubleVar(value=85.0)
        self.label_h_var = tk.DoubleVar(value=50.0)
        ttk.Label(sf, text="幅:").grid(row=0, column=0, sticky="e", padx=2)
        ttk.Entry(sf, textvariable=self.label_w_var, width=7).grid(row=0, column=1, padx=2)
        ttk.Label(sf, text="高さ:").grid(row=0, column=2, sticky="e", padx=2)
        ttk.Entry(sf, textvariable=self.label_h_var, width=7).grid(row=0, column=3, padx=2)
        row += 1

        # 配列
        ttk.Label(parent, text="配列", font=("Helvetica", 9, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(8, 2)); row += 1
        gf = ttk.Frame(parent); gf.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        self.cols_var = tk.IntVar(value=2)
        self.rows_var = tk.IntVar(value=5)
        ttk.Label(gf, text="列数:").grid(row=0, column=0, sticky="e", padx=2)
        ttk.Spinbox(gf, from_=1, to=10, textvariable=self.cols_var, width=5).grid(row=0, column=1, padx=2)
        ttk.Label(gf, text="行数:").grid(row=0, column=2, sticky="e", padx=2)
        ttk.Spinbox(gf, from_=1, to=20, textvariable=self.rows_var, width=5).grid(row=0, column=3, padx=2)
        row += 1

        # 間隔
        ttk.Label(parent, text="間隔 (mm)", font=("Helvetica", 9, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(8, 2)); row += 1
        spf = ttk.Frame(parent); spf.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        self.spacing_h_var = tk.DoubleVar(value=5.0)
        self.spacing_v_var = tk.DoubleVar(value=3.4)
        ttk.Label(spf, text="水平:").grid(row=0, column=0, sticky="e", padx=2)
        ttk.Entry(spf, textvariable=self.spacing_h_var, width=7).grid(row=0, column=1, padx=2)
        ttk.Label(spf, text="垂直:").grid(row=0, column=2, sticky="e", padx=2)
        ttk.Entry(spf, textvariable=self.spacing_v_var, width=7).grid(row=0, column=3, padx=2)
        row += 1

        # 開始位置
        ttk.Label(parent, text="開始位置", font=("Helvetica", 9, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(8, 2)); row += 1
        stf = ttk.Frame(parent); stf.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        self.start_pos_var = tk.IntVar(value=1)
        ttk.Label(stf, text="位置:").pack(side="left", padx=2)
        self.start_spin = ttk.Spinbox(stf, from_=1, to=100, textvariable=self.start_pos_var, width=5)
        self.start_spin.pack(side="left", padx=2)
        ttk.Label(stf, text="(1=左上)").pack(side="left", padx=2)
        row += 1

        self.start_grid_canvas = tk.Canvas(parent, width=200, height=120, bg="white",
                                            highlightthickness=1, highlightbackground="#CBD5E1")
        self.start_grid_canvas.grid(row=row, column=0, columnspan=2, padx=5, pady=5)
        self.start_grid_canvas.bind("<Button-1>", self._on_start_grid_click)
        row += 1

        # バーコードテキスト表示
        ttk.Separator(parent, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=5); row += 1
        self.show_text_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="バーコード下にID値を表示", variable=self.show_text_var).grid(row=row, column=0, columnspan=2, sticky="w", padx=15, pady=1)
        row += 1

        self._apply_preset("A4 標準 (10面)")

    def _create_content_panel(self, parent):
        """印刷内容設定パネル: 各カラムのバーコード/テキスト/非表示を選択"""
        ttk.Label(parent, text="各項目の印刷方法を選択してください",
                  font=("Helvetica", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 3))

        # 一括操作・プリセットボタン
        ctrl_frame = ttk.Frame(parent)
        ctrl_frame.pack(fill="x", padx=10, pady=(0, 5))
        ttk.Button(ctrl_frame, text="すべてバーコード", width=14,
                   command=lambda: self._set_all_modes("barcode")).pack(side="left", padx=2)
        ttk.Button(ctrl_frame, text="すべてテキスト", width=14,
                   command=lambda: self._set_all_modes("text")).pack(side="left", padx=2)
        ttk.Button(ctrl_frame, text="すべて非表示", width=12,
                   command=lambda: self._set_all_modes("none")).pack(side="left", padx=2)
        ttk.Button(ctrl_frame, text="デフォルトに戻す", width=14,
                   command=self._reset_modes_to_default).pack(side="right", padx=2)

        # スクロール可能なフレーム
        outer = ttk.Frame(parent)
        outer.pack(fill="both", expand=True, padx=5, pady=3)

        canvas = tk.Canvas(outer, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self._content_inner = ttk.Frame(canvas)
        self._content_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._content_inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.mode_vars = {}
        self._build_content_rows()

    def _build_content_rows(self):
        """印刷内容の行を構築"""
        inner = self._content_inner
        # 既存の子ウィジェットをクリア
        for w in inner.winfo_children():
            w.destroy()

        # ヘッダー
        ttk.Label(inner, text="カラム名", font=("Helvetica", 9, "bold"), width=20).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        for ci, (text, val) in enumerate([("バーコード", "barcode"), ("テキスト", "text"), ("非表示", "none")]):
            lbl = ttk.Label(inner, text=text, font=("Helvetica", 9, "bold"),
                            foreground="#3B82F6" if val == "barcode" else ("#15803D" if val == "text" else "#64748B"))
            lbl.grid(row=0, column=ci + 1, padx=8, pady=2)
        ttk.Separator(inner, orient="horizontal").grid(row=1, column=0, columnspan=4, sticky="ew", pady=2)

        self.mode_vars = {}
        for i, col in enumerate(self.data_mgr.csv_columns):
            r = i + 2
            display_name = self.data_mgr.get_column_display_name(col)

            # 行の背景色を交互に
            bg = "#F8FAFC" if i % 2 == 0 else "#FFFFFF"
            row_frame = tk.Frame(inner, bg=bg)
            row_frame.grid(row=r, column=0, columnspan=4, sticky="ew", pady=0)
            inner.grid_columnconfigure(0, weight=1)

            tk.Label(row_frame, text=display_name, width=20, anchor="w",
                     bg=bg, font=("Helvetica", 9)).grid(row=0, column=0, sticky="w", padx=5, pady=3)

            var = tk.StringVar(value=self.field_print_modes.get(col, "none"))
            self.mode_vars[col] = var

            # ボタン式の選択（ラジオボタンより押しやすい）
            for ci, (text, val, color) in enumerate([
                ("バーコード", "barcode", "#3B82F6"),
                ("テキスト", "text", "#15803D"),
                ("非表示", "none", "#94A3B8"),
            ]):
                btn = tk.Button(
                    row_frame, text=text, width=8, font=("Helvetica", 8),
                    relief="sunken" if var.get() == val else "raised",
                    bg=color if var.get() == val else "#E2E8F0",
                    fg="white" if var.get() == val else "#1E293B",
                    activebackground=color,
                    command=lambda v=var, vl=val, c=col: self._set_mode(c, vl)
                )
                btn.grid(row=0, column=ci + 1, padx=4, pady=3)

    def _set_mode(self, col, value):
        """個別カラムのモード変更"""
        self.mode_vars[col].set(value)
        self.field_print_modes[col] = value
        self._build_content_rows()

    def _set_all_modes(self, value):
        """全カラムを一括設定"""
        for col in self.data_mgr.csv_columns:
            self.field_print_modes[col] = value
            if col in self.mode_vars:
                self.mode_vars[col].set(value)
        self._build_content_rows()

    def _reset_modes_to_default(self):
        """デフォルトに戻す: バーコードカラムのみbarcode、他はnone"""
        for col in self.data_mgr.csv_columns:
            if col == self.data_mgr.barcode_column:
                self.field_print_modes[col] = "barcode"
            else:
                self.field_print_modes[col] = "none"
            if col in self.mode_vars:
                self.mode_vars[col].set(self.field_print_modes[col])
        self._build_content_rows()

    def _sync_modes(self):
        """UIのmode_varsから内部辞書に同期"""
        for col, var in self.mode_vars.items():
            self.field_print_modes[col] = var.get()

    def _on_preset_change(self, event=None):
        self._apply_preset(self.preset_var.get())
        self._update_preset_info()
        self._update_preview()

    def _update_preset_info(self):
        """選択中プリセットの寸法説明を更新"""
        name = self.preset_var.get()
        p = LABEL_PRESETS.get(name, {})
        if not p:
            self.preset_info_label.config(text="カスタム設定: 各項目を手動で入力してください")
            return
        ps = p.get("paper_size", "A4")
        pw, ph = PAPER_SIZES.get(ps, (210, 297))
        lw = p.get("label_width", 0)
        lh = p.get("label_height", 0)
        cols = p.get("cols", 0)
        rows = p.get("rows", 0)
        info = (f"用紙: {ps} ({pw}×{ph}mm) | "
                f"ラベル: {lw}×{lh}mm | "
                f"{cols}列×{rows}行={cols*rows}面")
        self.preset_info_label.config(text=info)

    def _apply_preset(self, name):
        p = LABEL_PRESETS.get(name, {})
        if not p:
            return
        self.paper_var.set(p.get("paper_size", "A4"))
        self.margin_top_var.set(p.get("margin_top", 15.0))
        self.margin_bottom_var.set(p.get("margin_bottom", 15.0))
        self.margin_left_var.set(p.get("margin_left", 15.0))
        self.margin_right_var.set(p.get("margin_right", 15.0))
        self.label_w_var.set(p.get("label_width", 85.0))
        self.label_h_var.set(p.get("label_height", 50.0))
        self.spacing_h_var.set(p.get("spacing_h", 5.0))
        self.spacing_v_var.set(p.get("spacing_v", 3.4))
        self.cols_var.set(p.get("cols", 2))
        self.rows_var.set(p.get("rows", 5))
        self.start_spin.configure(to=p.get("cols", 2) * p.get("rows", 5))

    def _get_config(self):
        self._sync_modes()
        return {
            "paper_size": self.paper_var.get(),
            "margin_top": self.margin_top_var.get(),
            "margin_bottom": self.margin_bottom_var.get(),
            "margin_left": self.margin_left_var.get(),
            "margin_right": self.margin_right_var.get(),
            "label_width": self.label_w_var.get(),
            "label_height": self.label_h_var.get(),
            "spacing_h": self.spacing_h_var.get(),
            "spacing_v": self.spacing_v_var.get(),
            "cols": self.cols_var.get(),
            "rows": self.rows_var.get(),
            "start_position": self.start_pos_var.get(),
            "show_text": self.show_text_var.get(),
            "field_modes": dict(self.field_print_modes),
            "dpi": 300,
        }

    def _on_start_grid_click(self, event):
        cfg = self._get_config()
        cols, rows = cfg["cols"], cfg["rows"]
        cw = self.start_grid_canvas.winfo_width()
        ch = self.start_grid_canvas.winfo_height()
        if cols == 0 or rows == 0:
            return
        col = max(0, min(int(event.x / (cw / cols)), cols - 1))
        row = max(0, min(int(event.y / (ch / rows)), rows - 1))
        self.start_pos_var.set(row * cols + col + 1)
        self._draw_start_grid()

    def _draw_start_grid(self):
        self.start_grid_canvas.delete("all")
        cfg = self._get_config()
        cols, rows, start = cfg["cols"], cfg["rows"], cfg["start_position"]
        cw = self.start_grid_canvas.winfo_width()
        ch = self.start_grid_canvas.winfo_height()
        if cols == 0 or rows == 0 or cw < 10 or ch < 10:
            return
        cw_cell, ch_cell = cw / cols, ch / rows
        for r in range(rows):
            for c in range(cols):
                x1, y1 = c * cw_cell + 1, r * ch_cell + 1
                x2, y2 = (c + 1) * cw_cell - 1, (r + 1) * ch_cell - 1
                pos = r * cols + c + 1
                fill = "#3B82F6" if pos == start else ("#BFDBFE" if pos >= start else "#F1F5F9")
                tc = "white" if pos == start else "#64748B"
                self.start_grid_canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="#94A3B8")
                self.start_grid_canvas.create_text((x1+x2)/2, (y1+y2)/2, text=str(pos), fill=tc, font=("Helvetica", 8))

    def _update_preview(self):
        self.preview_canvas.delete("all")
        self._preview_photo = None  # GC対策: 参照保持
        cfg = self._get_config()
        cw = self.preview_canvas.winfo_width()
        ch = self.preview_canvas.winfo_height()
        if cw < 50 or ch < 50:
            return

        if not HAS_PIL or not self.records:
            # データなし時は簡易レイアウトのみ
            self._draw_layout_preview(cfg, cw, ch)
            return

        # オーバーフローチェック
        errors = self._check_label_overflow()
        if errors:
            # エラー表示をプレビュー上に描画
            self._draw_layout_preview(cfg, cw, ch)
            # 「データなし」テキストを上書き
            self.preview_canvas.create_rectangle(
                cw*0.1, ch*0.3, cw*0.9, ch*0.7,
                fill="#FEF2F2", outline="#DC2626", width=2
            )
            self.preview_canvas.create_text(
                cw/2, ch*0.42, text="⚠ ラベルサイズ超過",
                fill="#DC2626", font=("Helvetica", 12, "bold")
            )
            self.preview_canvas.create_text(
                cw/2, ch*0.55, text="\n".join(errors),
                fill="#991B1B", font=("Helvetica", 9), width=cw*0.7
            )
            return

        # 実データで全ページ画像を生成
        try:
            pages = self._generate_pdf_images()
        except Exception:
            self._draw_layout_preview(cfg, cw, ch)
            return

        if not pages:
            self._draw_layout_preview(cfg, cw, ch)
            return

        # ページ数管理
        self.total_pages = len(pages)
        self.current_page = min(self.current_page, self.total_pages - 1)
        self.page_label.configure(text=f"{self.current_page+1} / {self.total_pages}")

        # 現在ページの画像をキャンバスサイズに縮小して表示
        page_img = pages[self.current_page]
        margin = 10
        max_w = cw - margin * 2
        max_h = ch - margin * 2
        img_w, img_h = page_img.size
        scale = min(max_w / img_w, max_h / img_h)
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))
        resized = page_img.resize((new_w, new_h), Image.LANCZOS)

        # 影
        ox = (cw - new_w) // 2
        oy = (ch - new_h) // 2
        self.preview_canvas.create_rectangle(
            ox + 3, oy + 3, ox + new_w + 3, oy + new_h + 3,
            fill="#CBD5E1", outline=""
        )

        self._preview_photo = ImageTk.PhotoImage(resized)
        self.preview_canvas.create_image(ox, oy, anchor="nw", image=self._preview_photo)

        # 枠線
        self.preview_canvas.create_rectangle(
            ox, oy, ox + new_w, oy + new_h,
            outline="#94A3B8", width=1
        )
        # 寸法情報をプレビュー上部に表示
        self._draw_size_info(cfg, cw, ch)
        self._draw_start_grid()

    def _draw_size_info(self, cfg, cw, ch):
        """プレビュー上に用紙・ラベルの寸法情報を表示"""
        pw, ph = PAPER_SIZES.get(cfg["paper_size"], (210, 297))
        lw = cfg["label_width"]
        lh = cfg["label_height"]
        cols = cfg["cols"]
        rows = cfg["rows"]
        lpp = cols * rows

        info_lines = [
            f"用紙: {cfg['paper_size']} ({pw}×{ph}mm)",
            f"ラベル: {lw}×{lh}mm  {cols}列×{rows}行={lpp}面",
            f"余白: 上{cfg['margin_top']}  下{cfg['margin_bottom']}  左{cfg['margin_left']}  右{cfg['margin_right']}mm",
            f"間隔: 水平{cfg['spacing_h']}mm  垂直{cfg['spacing_v']}mm",
        ]
        info_text = "  |  ".join(info_lines[:2])
        info_text2 = "  |  ".join(info_lines[2:])

        # 背景帯
        self.preview_canvas.create_rectangle(0, ch - 36, cw, ch, fill="#1E293B", outline="")
        self.preview_canvas.create_text(
            cw / 2, ch - 25, text=info_text,
            fill="#E2E8F0", font=("Helvetica", 8), anchor="center"
        )
        self.preview_canvas.create_text(
            cw / 2, ch - 11, text=info_text2,
            fill="#94A3B8", font=("Helvetica", 7), anchor="center"
        )

    def _draw_layout_preview(self, cfg, cw, ch):
        """データなし時の簡易レイアウトプレビュー"""
        pw, ph = PAPER_SIZES.get(cfg["paper_size"], (210, 297))
        margin = 20
        scale = min((cw - margin*2) / pw, (ch - margin*2) / ph)
        spw, sph = pw * scale, ph * scale
        ox, oy = (cw - spw) / 2, (ch - sph) / 2

        self.preview_canvas.create_rectangle(ox+3, oy+3, ox+spw+3, oy+sph+3, fill="#CBD5E1", outline="")
        self.preview_canvas.create_rectangle(ox, oy, ox+spw, oy+sph, fill="white", outline="#94A3B8")

        ml, mr = cfg["margin_left"]*scale, cfg["margin_right"]*scale
        mt, mb = cfg["margin_top"]*scale, cfg["margin_bottom"]*scale
        for args in [
            (ox+ml, oy, ox+ml, oy+sph), (ox+spw-mr, oy, ox+spw-mr, oy+sph),
            (ox, oy+mt, ox+spw, oy+mt), (ox, oy+sph-mb, ox+spw, oy+sph-mb)
        ]:
            self.preview_canvas.create_line(*args, fill="#93C5FD", dash=(3, 3))

        cols, rows = cfg["cols"], cfg["rows"]
        lw, lh = cfg["label_width"]*scale, cfg["label_height"]*scale
        sh, sv = cfg["spacing_h"]*scale, cfg["spacing_v"]*scale

        for r in range(rows):
            for c in range(cols):
                x = ox + ml + c * (lw + sh)
                y = oy + mt + r * (lh + sv)
                self.preview_canvas.create_rectangle(x, y, x+lw, y+lh, fill="#F8FAFC", outline="#E2E8F0", dash=(2,2))

        self.preview_canvas.create_text(cw/2, ch/2, text="データなし", fill="#94A3B8", font=("Helvetica", 14))

        lpp = rows * cols
        self.total_pages = 1
        self.current_page = 0
        self.page_label.configure(text="1 / 1")
        self._draw_size_info(cfg, cw, ch)
        self._draw_start_grid()

    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1; self._update_preview()
    def _next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1; self._update_preview()

    def _check_label_overflow(self):
        """印刷内容がラベルサイズに収まるかチェック。収まらない場合はエラーメッセージを返す"""
        cfg = self._get_config()
        dpi = cfg["dpi"]
        def mm2px(mm): return int(mm * dpi / 25.4)

        lh = mm2px(cfg["label_height"])
        modes = cfg["field_modes"]

        bc_fields = [c for c in self.data_mgr.csv_columns if modes.get(c) == "barcode"]
        text_fields = [c for c in self.data_mgr.csv_columns if modes.get(c) == "text"]

        bc_margin = mm2px(2)
        text_line_h = mm2px(3.5)
        text_total_h = len(text_fields) * text_line_h
        min_bc_h = mm2px(8)  # バーコード1つの最小高さ

        available_h = lh - bc_margin * 2 - text_total_h
        needed_bc_h = len(bc_fields) * min_bc_h

        errors = []
        if available_h < 0:
            errors.append(f"テキスト項目({len(text_fields)}個)だけでラベル高さを超えています。\n"
                          f"テキスト項目を減らすか、ラベルの高さを大きくしてください。")
        elif len(bc_fields) > 0 and available_h < needed_bc_h:
            max_bc = max(0, available_h // min_bc_h) if min_bc_h > 0 else 0
            errors.append(f"バーコード{len(bc_fields)}個 + テキスト{len(text_fields)}個が\n"
                          f"ラベル高さ {cfg['label_height']:.1f}mm に収まりません。\n"
                          f"現在のサイズではバーコードは最大{max_bc}個です。\n"
                          f"項目数を減らすか、ラベルの高さを大きくしてください。")
        return errors

    def _generate_pdf_images(self):
        cfg = self._get_config()
        dpi = cfg["dpi"]
        def mm2px(mm): return int(mm * dpi / 25.4)

        pw, ph = PAPER_SIZES.get(cfg["paper_size"], (210, 297))
        pgw, pgh = mm2px(pw), mm2px(ph)
        ml, mt = mm2px(cfg["margin_left"]), mm2px(cfg["margin_top"])
        lw, lh = mm2px(cfg["label_width"]), mm2px(cfg["label_height"])
        sh, sv = mm2px(cfg["spacing_h"]), mm2px(cfg["spacing_v"])
        cols, rows = cfg["cols"], cfg["rows"]
        lpp = cols * rows
        start = cfg["start_position"] - 1
        modes = cfg["field_modes"]

        # 項目分類
        bc_fields = [c for c in self.data_mgr.csv_columns if modes.get(c) == "barcode"]
        text_fields = [c for c in self.data_mgr.csv_columns if modes.get(c) == "text"]

        bc_margin = mm2px(2)
        font_small = _get_japanese_font(mm2px(2.5))
        font_bc_text = _get_japanese_font(mm2px(2))

        pages = []
        ri = 0
        slot = start

        while ri < len(self.records):
            page = Image.new("RGB", (pgw, pgh), "white")
            draw = ImageDraw.Draw(page)

            while slot < lpp and ri < len(self.records):
                r = slot // cols
                c = slot % cols
                x = ml + c * (lw + sh)
                y = mt + r * (lh + sv)
                rec = self.records[ri]

                # テキスト項目の高さ計算
                text_line_h = mm2px(3.5)
                n_text = len(text_fields)
                text_total_h = n_text * text_line_h
                n_bc = len(bc_fields)

                # 残り高さをバーコードに割り当て
                available_h = lh - bc_margin * 2 - text_total_h
                if n_bc > 0:
                    bc_each_h = max(mm2px(8), available_h // n_bc)
                else:
                    bc_each_h = 0

                cur_y = y + bc_margin

                # テキスト項目を上部に描画
                for tf in text_fields:
                    val = str(rec.get(tf, ""))
                    label = self.data_mgr.get_column_display_name(tf)
                    line = f"{label}: {val}"
                    bbox = draw.textbbox((0, 0), line, font=font_small)
                    tw = bbox[2] - bbox[0]
                    tx = x + (lw - tw) // 2
                    draw.text((tx, cur_y), line, fill="black", font=font_small)
                    cur_y += text_line_h

                # バーコード項目を描画
                for bf in bc_fields:
                    bc_val = str(rec.get(bf, ""))
                    if bc_val:
                        try:
                            bc_img = generate_code128_image(
                                bc_val,
                                width=lw - bc_margin * 2,
                                height=bc_each_h - (mm2px(3) if cfg["show_text"] else 0),
                                show_text=cfg["show_text"]
                            )
                            bx = x + (lw - bc_img.width) // 2
                            page.paste(bc_img, (bx, cur_y))
                            cur_y += bc_img.height + mm2px(1)
                        except Exception:
                            cur_y += bc_each_h

                ri += 1
                slot += 1

            pages.append(page)
            slot = 0
        return pages

    def _save_pdf(self):
        # オーバーフローチェック
        errors = self._check_label_overflow()
        if errors:
            messagebox.showerror("ラベルサイズ超過", "\n".join(errors), parent=self.dialog)
            return
        pages = self._generate_pdf_images()
        if not pages:
            messagebox.showwarning("データなし", "印刷するレコードがありません。", parent=self.dialog); return
        fp = filedialog.asksaveasfilename(parent=self.dialog, title="PDF保存", defaultextension=".pdf",
                                           initialfile="barcode_labels.pdf", filetypes=[("PDF", "*.pdf")])
        if not fp:
            return
        try:
            cfg = self._get_config()
            if len(pages) == 1:
                pages[0].save(fp, "PDF", resolution=cfg["dpi"])
            else:
                pages[0].save(fp, "PDF", save_all=True, append_images=pages[1:], resolution=cfg["dpi"])
            self.data_mgr.add_history("ラベル印刷", f"{len(self.records)}件PDF出力: {os.path.basename(fp)}")
            messagebox.showinfo("完了", f"PDF保存:\n{fp}", parent=self.dialog)
        except Exception as e:
            messagebox.showerror("エラー", f"PDF保存エラー: {e}", parent=self.dialog)

    def _print_labels(self):
        # オーバーフローチェック
        errors = self._check_label_overflow()
        if errors:
            messagebox.showerror("ラベルサイズ超過", "\n".join(errors), parent=self.dialog)
            return
        pages = self._generate_pdf_images()
        if not pages:
            messagebox.showwarning("データなし", "レコードがありません。", parent=self.dialog); return
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                cfg = self._get_config()
                if len(pages) == 1:
                    pages[0].save(tmp.name, "PDF", resolution=cfg["dpi"])
                else:
                    pages[0].save(tmp.name, "PDF", save_all=True, append_images=pages[1:], resolution=cfg["dpi"])
                tp = tmp.name
            if sys.platform == "win32":
                os.startfile(tp, "print")
            elif sys.platform == "darwin":
                subprocess.run(["lpr", tp])
            else:
                try: subprocess.run(["lpr", tp], check=True)
                except FileNotFoundError: subprocess.run(["xdg-open", tp])
            self.data_mgr.add_history("ラベル印刷", f"{len(self.records)}件印刷")
            messagebox.showinfo("印刷", "印刷キューに送信しました。", parent=self.dialog)
        except Exception as e:
            messagebox.showerror("エラー", f"印刷エラー: {e}", parent=self.dialog)


# ==============================================================================
# メイン GUI アプリケーション
# ==============================================================================

class PassportManagerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("パスポート管理システム")
        self.root.geometry("1300x800")
        self.root.minsize(1000, 600)

        self.COLORS = {
            "primary": "#1E40AF", "primary_light": "#3B82F6",
            "success": "#15803D", "success_light": "#22C55E",
            "warning": "#D97706", "danger": "#DC2626",
            "bg": "#F8FAFC", "card": "#FFFFFF", "text": "#1E293B",
            "muted": "#64748B", "border": "#E2E8F0", "toolbar_bg": "#EFF6FF",
            "collected": "#DBEAFE", "returned": "#BBF7D0",
        }
        self.root.configure(bg=self.COLORS["bg"])

        data_path = os.path.join(get_data_dir(), "passport_data.json")
        self.data_mgr = PassportDataManager(data_file=data_path)
        self.barcode_photo = None
        self.sort_column = None
        self.sort_reverse = False

        # ヘッダードラッグ&ドロップ用
        self._drag_src_col = None
        self._drag_label = None
        self._drag_active = False

        self._setup_styles()
        self._create_menu()
        self._create_ui()
        self._refresh_table()
        self._refresh_history()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=32, font=("Helvetica", 11))
        style.configure("Treeview.Heading", font=("Helvetica", 11, "bold"), background="#E2E8F0", foreground="#1E293B")
        style.configure("Toolbar.TButton", font=("Helvetica", 10), padding=(8, 4))

    def _create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        fm = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ファイル", menu=fm)
        fm.add_command(label="CSV取り込み...", command=self._import_csv, accelerator="Ctrl+I")
        fm.add_separator()
        fm.add_command(label="バーコードラベル印刷...", command=self._open_label_print_dialog, accelerator="Ctrl+P")
        fm.add_separator()
        fm.add_command(label="データをエクスポート (JSON)...", command=self._export_json)
        fm.add_command(label="履歴をエクスポート (CSV)...", command=self._export_history_csv)
        fm.add_separator()
        fm.add_command(label="全データクリア", command=self._clear_all_data)
        fm.add_separator()
        fm.add_command(label="終了", command=self.root.quit, accelerator="Ctrl+Q")

        em = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="編集", menu=em)
        em.add_command(label="レコード編集...", command=self._edit_selected, accelerator="Ctrl+E")
        em.add_separator()
        em.add_command(label="返却済みに変更", command=self._mark_returned)
        em.add_command(label="回収済みに変更", command=self._mark_collected)
        em.add_separator()
        em.add_command(label="選択削除", command=self._delete_selected)

        sm = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="設定", menu=sm)
        sm.add_command(label="カラム表示設定...", command=self._show_column_settings)
        sm.add_command(label="バーコードカラム設定...", command=self._set_barcode_column)
        sm.add_command(label="データファイル場所...", command=self._set_data_file)

        hm = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ヘルプ", menu=hm)
        hm.add_command(label="使い方", command=self._show_help)

        self.root.bind("<Control-i>", lambda e: self._import_csv())
        self.root.bind("<Control-q>", lambda e: self.root.quit())
        self.root.bind("<Control-p>", lambda e: self._open_label_print_dialog())
        self.root.bind("<Control-e>", lambda e: self._edit_selected())

    def _create_ui(self):
        header = tk.Frame(self.root, bg=self.COLORS["primary"], height=56)
        header.pack(fill="x"); header.pack_propagate(False)
        tk.Label(header, text="  パスポート管理システム", font=("Helvetica", 18, "bold"),
                 fg="white", bg=self.COLORS["primary"]).pack(side="left", padx=15, pady=10)
        self.status_label = tk.Label(header, text="レコード: 0件", font=("Helvetica", 11),
                                     fg="white", bg=self.COLORS["primary"])
        self.status_label.pack(side="right", padx=20)

        main_paned = ttk.PanedWindow(self.root, orient="horizontal")
        main_paned.pack(fill="both", expand=True, padx=10, pady=10)

        left_frame = ttk.Frame(main_paned); main_paned.add(left_frame, weight=3)

        # ツールバー
        tb = tk.Frame(left_frame, bg=self.COLORS["toolbar_bg"], highlightbackground=self.COLORS["border"], highlightthickness=1)
        tb.pack(fill="x", pady=(0, 5), ipady=3)

        ttk.Button(tb, text="CSV取り込み", command=self._import_csv, style="Toolbar.TButton").pack(side="left", padx=(5,2))
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=5, pady=3)
        ttk.Button(tb, text="バーコード印刷", command=self._print_barcode, style="Toolbar.TButton").pack(side="left", padx=2)
        ttk.Button(tb, text="ラベル印刷", command=self._open_label_print_dialog, style="Toolbar.TButton").pack(side="left", padx=2)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=5, pady=3)
        ttk.Button(tb, text="返却済み", command=self._mark_returned, style="Toolbar.TButton").pack(side="left", padx=2)
        ttk.Button(tb, text="回収済み", command=self._mark_collected, style="Toolbar.TButton").pack(side="left", padx=2)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=5, pady=3)
        ttk.Button(tb, text="編集", command=self._edit_selected, style="Toolbar.TButton").pack(side="left", padx=2)
        ttk.Button(tb, text="削除", command=self._delete_selected, style="Toolbar.TButton").pack(side="left", padx=2)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=5, pady=3)
        ttk.Button(tb, text="カラム設定", command=self._show_column_settings, style="Toolbar.TButton").pack(side="left", padx=2)

        # フィルター
        ff = tk.Frame(left_frame, bg=self.COLORS["bg"]); ff.pack(fill="x", pady=(0, 5))
        tk.Label(ff, text="検索:", bg=self.COLORS["bg"]).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._refresh_table())
        ttk.Entry(ff, textvariable=self.search_var, width=30).pack(side="left", padx=5)
        tk.Label(ff, text="ステータス:", bg=self.COLORS["bg"]).pack(side="left", padx=(15, 0))
        self.filter_status = tk.StringVar(value="すべて")
        sc = ttk.Combobox(ff, textvariable=self.filter_status, values=["すべて", "回収済み", "返却済み"], state="readonly", width=10)
        sc.pack(side="left", padx=5)
        sc.bind("<<ComboboxSelected>>", lambda e: self._refresh_table())

        # テーブル
        tf = ttk.Frame(left_frame); tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, selectmode="extended", show="headings")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tf.grid_rowconfigure(0, weight=1); tf.grid_columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double_click)

        # ヘッダードラッグ&ドロップで列入替（addで既存バインドと共存）
        self.tree.bind("<ButtonPress-1>", self._on_header_press, add=True)
        self.tree.bind("<B1-Motion>", self._on_header_drag, add=True)
        self.tree.bind("<ButtonRelease-1>", self._on_header_release, add=True)

        # 右クリック
        self.ctx = tk.Menu(self.tree, tearoff=0)
        self.ctx.add_command(label="編集...", command=self._edit_selected)
        self.ctx.add_command(label="返却済み", command=self._mark_returned)
        self.ctx.add_command(label="回収済み", command=self._mark_collected)
        self.ctx.add_separator()
        self.ctx.add_command(label="削除", command=self._delete_selected)
        if sys.platform == "darwin":
            self.tree.bind("<Button-2>", self._show_ctx)
            self.tree.bind("<Control-Button-1>", self._show_ctx)
        else:
            self.tree.bind("<Button-3>", self._show_ctx)

        # 右パネル
        rf = ttk.Frame(main_paned); main_paned.add(rf, weight=2)

        # スキャン
        ss = tk.LabelFrame(rf, text=" バーコードスキャン ", font=("Helvetica", 11, "bold"),
                           bg=self.COLORS["card"], fg=self.COLORS["text"], padx=12, pady=8)
        ss.pack(fill="x", pady=(0, 10))

        mf = tk.Frame(ss, bg=self.COLORS["card"]); mf.pack(fill="x", pady=(0, 5))
        tk.Label(mf, text="モード:", bg=self.COLORS["card"], font=("Helvetica", 9, "bold")).pack(side="left")
        self.scan_mode_var = tk.StringVar(value="instant")
        ttk.Radiobutton(mf, text="即時反映", variable=self.scan_mode_var, value="instant", command=self._on_scan_mode_change).pack(side="left", padx=(5,10))
        ttk.Radiobutton(mf, text="一括", variable=self.scan_mode_var, value="batch", command=self._on_scan_mode_change).pack(side="left")

        self.scan_mode_desc = tk.Label(ss, text="スキャン → 自動ステータストグル", bg=self.COLORS["card"], font=("Helvetica", 8), fg=self.COLORS["muted"])
        self.scan_mode_desc.pack(anchor="w")

        sif = tk.Frame(ss, bg=self.COLORS["card"]); sif.pack(fill="x", pady=5)
        self.scan_var = tk.StringVar()
        self.scan_entry = ttk.Entry(sif, textvariable=self.scan_var, font=("Helvetica", 16))
        self.scan_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.scan_entry.bind("<Return>", self._on_scan)
        ttk.Button(sif, text="スキャン", command=self._on_scan).pack(side="right")

        self.scan_result_label = tk.Label(ss, text="", bg=self.COLORS["card"], font=("Helvetica", 10), wraplength=350, justify="left")
        self.scan_result_label.pack(anchor="w", pady=3)

        self.batch_frame = tk.Frame(ss, bg=self.COLORS["card"])
        tk.Label(self.batch_frame, text="スキャン済み:", bg=self.COLORS["card"], font=("Helvetica", 9, "bold")).pack(anchor="w")
        blf = tk.Frame(self.batch_frame, bg=self.COLORS["card"]); blf.pack(fill="x", pady=3)
        self.batch_listbox = tk.Listbox(blf, height=5, font=("Helvetica", 9), selectmode="extended")
        bsb = ttk.Scrollbar(blf, orient="vertical", command=self.batch_listbox.yview)
        self.batch_listbox.configure(yscrollcommand=bsb.set)
        self.batch_listbox.pack(side="left", fill="x", expand=True); bsb.pack(side="right", fill="y")
        self.batch_count_label = tk.Label(self.batch_frame, text="0件", bg=self.COLORS["card"], font=("Helvetica", 9), fg=self.COLORS["muted"])
        self.batch_count_label.pack(anchor="w")
        bbf = tk.Frame(self.batch_frame, bg=self.COLORS["card"]); bbf.pack(fill="x", pady=3)
        ttk.Button(bbf, text="一括適用", command=self._batch_apply).pack(side="left", padx=2)
        ttk.Button(bbf, text="除外", command=self._batch_remove).pack(side="left", padx=2)
        ttk.Button(bbf, text="クリア", command=self._batch_clear).pack(side="left", padx=2)
        self.batch_scan_list = []
        self.scanned_indices = []

        # バーコードプレビュー
        bs = tk.LabelFrame(rf, text=" バーコードプレビュー ", font=("Helvetica", 11, "bold"),
                           bg=self.COLORS["card"], fg=self.COLORS["text"], padx=12, pady=8)
        bs.pack(fill="x", pady=(0, 10))
        self.barcode_canvas = tk.Label(bs, bg="white", relief="sunken", height=8)
        self.barcode_canvas.pack(fill="x", pady=5)
        self.barcode_info_label = tk.Label(bs, text="行を選択してバーコード表示", bg=self.COLORS["card"], font=("Helvetica", 9), fg=self.COLORS["muted"])
        self.barcode_info_label.pack(anchor="w")
        bbf2 = tk.Frame(bs, bg=self.COLORS["card"]); bbf2.pack(fill="x", pady=5)
        ttk.Button(bbf2, text="印刷", command=self._print_barcode).pack(side="left", padx=2)
        ttk.Button(bbf2, text="画像保存", command=self._save_barcode_image).pack(side="left", padx=2)

        bcf = tk.Frame(bs, bg=self.COLORS["card"]); bcf.pack(fill="x", pady=(5, 0))
        tk.Label(bcf, text="バーコード値カラム:", bg=self.COLORS["card"], font=("Helvetica", 9)).pack(side="left")
        self.bc_column_var = tk.StringVar(value=self.data_mgr.barcode_column or "")
        self.bc_column_combo = ttk.Combobox(bcf, textvariable=self.bc_column_var, state="readonly", width=20)
        self.bc_column_combo.pack(side="left", padx=5)
        self.bc_column_combo.bind("<<ComboboxSelected>>", self._on_barcode_column_change)
        self._update_column_combo()

        # 履歴
        hs = tk.LabelFrame(rf, text=" 操作履歴 ", font=("Helvetica", 11, "bold"),
                           bg=self.COLORS["card"], fg=self.COLORS["text"], padx=12, pady=8)
        hs.pack(fill="both", expand=True)
        self.history_tree = ttk.Treeview(hs, columns=("time", "action", "detail"), show="headings", height=8)
        self.history_tree.heading("time", text="日時"); self.history_tree.column("time", width=140, minwidth=130)
        self.history_tree.heading("action", text="操作"); self.history_tree.column("action", width=100, minwidth=80)
        self.history_tree.heading("detail", text="詳細"); self.history_tree.column("detail", width=250, minwidth=150)
        hvsb = ttk.Scrollbar(hs, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=hvsb.set)
        self.history_tree.pack(side="left", fill="both", expand=True); hvsb.pack(side="right", fill="y")

    def _show_ctx(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if item not in self.tree.selection(): self.tree.selection_set(item)
            self.ctx.post(event.x_root, event.y_root)

    # ──── テーブル ────
    # 管理列の定義
    SYSTEM_COLUMNS = {
        "_no":          {"text": "No.",           "width": 50,  "minwidth": 40, "anchor": "center"},
        "_status":      {"text": "ステータス",     "width": 110, "minwidth": 100, "anchor": "center"},
        "_barcode_id":  {"text": "バーコードID",   "width": 120, "minwidth": 100, "anchor": "w"},
    }

    def _get_all_columns(self):
        """表示順を考慮した全カラムリストを取得"""
        disp = self.data_mgr.get_display_columns()
        default = ["_no", "_status", "_barcode_id"] + disp
        # column_order が保存されていればそちらを優先
        saved = getattr(self.data_mgr, 'column_order', None)
        if saved:
            # 保存済みの中で現在有効なカラムのみ残す
            valid = set(default)
            ordered = [c for c in saved if c in valid]
            # 新規追加されたカラムを末尾に追加
            for c in default:
                if c not in ordered:
                    ordered.append(c)
            return ordered
        return default

    def _setup_tree_columns(self):
        columns = self._get_all_columns()
        self.tree["columns"] = columns

        for col in columns:
            if col in self.SYSTEM_COLUMNS:
                info = self.SYSTEM_COLUMNS[col]
                suf = self._sort_suffix(col)
                self.tree.heading(col, text=f"{info['text']}{suf}", command=lambda c=col: self._on_sort(c))
                self.tree.column(col, width=info["width"], minwidth=info["minwidth"], anchor=info.get("anchor", "w"))
            else:
                dn = self.data_mgr.get_column_display_name(col)
                suf = self._sort_suffix(col)
                self.tree.heading(col, text=f"{dn}{suf}", command=lambda c=col: self._on_sort(c))
                self.tree.column(col, width=120, minwidth=80)

    def _sort_suffix(self, col):
        if self.sort_column == col:
            return " ▼" if self.sort_reverse else " ▲"
        return ""

    def _on_sort(self, col):
        if self.sort_column == col:
            if self.sort_reverse:
                self.sort_column = None
                self.sort_reverse = False
            else:
                self.sort_reverse = True
        else:
            self.sort_column = col
            self.sort_reverse = False
        self._refresh_table()

    # ──── ヘッダードラッグ&ドロップ ────
    def _identify_header_col(self, x, y):
        """ヘッダー領域のクリック位置からカラムIDを取得"""
        region = self.tree.identify_region(x, y)
        if region == "heading":
            return self.tree.identify_column(x)
        return None

    def _col_id_to_name(self, col_id):
        """'#1' → 実カラム名に変換"""
        if not col_id:
            return None
        try:
            idx = int(col_id.replace("#", "")) - 1
            cols = list(self.tree["columns"])
            if 0 <= idx < len(cols):
                return cols[idx]
        except (ValueError, IndexError):
            pass
        return None

    def _get_col_display_text(self, col):
        """カラム名から表示テキストを取得"""
        if col in self.SYSTEM_COLUMNS:
            return self.SYSTEM_COLUMNS[col]["text"]
        return self.data_mgr.get_column_display_name(col)

    def _on_header_press(self, event):
        """ヘッダー上でマウスを押した: ドラッグ元を記録"""
        col_id = self._identify_header_col(event.x, event.y)
        col_name = self._col_id_to_name(col_id)
        if col_name:
            self._drag_src_col = col_name
            self._drag_start_x = event.x
            self._drag_active = False
        else:
            self._drag_src_col = None
            self._drag_active = False

    def _on_header_drag(self, event):
        """ドラッグ中: ヘッダー上から始まった場合のみフローティングラベル表示"""
        if not self._drag_src_col:
            return
        # 少し動かないとドラッグ開始しない（クリックとの区別）
        if not self._drag_active and abs(event.x - self._drag_start_x) < 20:
            return
        self._drag_active = True
        if not self._drag_label:
            dn = self._get_col_display_text(self._drag_src_col)
            self._drag_label = tk.Label(
                self.tree, text=f" {dn} ", font=("Helvetica", 10, "bold"),
                bg="#3B82F6", fg="white", relief="raised", bd=1, padx=6, pady=2
            )
        # マウス位置に追従
        self._drag_label.place(x=event.x - 30, y=2)

    def _on_header_release(self, event):
        """ドロップ: ドロップ先カラムを判定して入替"""
        # フローティングラベル消去
        if self._drag_label:
            self._drag_label.destroy()
            self._drag_label = None

        if not self._drag_src_col or not self._drag_active:
            self._drag_src_col = None
            self._drag_active = False
            return

        src = self._drag_src_col
        self._drag_src_col = None
        self._drag_active = False

        # ドロップ先判定
        col_id = self._identify_header_col(event.x, event.y)
        dst = self._col_id_to_name(col_id)
        if not dst or dst == src:
            return

        # 全カラムリスト内で入替
        cols = self._get_all_columns()
        if src in cols and dst in cols:
            si = cols.index(src)
            di = cols.index(dst)
            cols.pop(si)
            cols.insert(di, src)
            # column_order として保存
            self.data_mgr.column_order = cols
            self.data_mgr.save()
            self._refresh_table()

    def _refresh_table(self):
        self._setup_tree_columns()
        for item in self.tree.get_children():
            self.tree.delete(item)

        search_text = self.search_var.get().lower()
        filter_status = self.filter_status.get()
        all_cols = self._get_all_columns()

        # フィルタリング
        filtered = []
        for i, rec in enumerate(self.data_mgr.records):
            if filter_status != "すべて" and rec.get("_status") != filter_status:
                continue
            if search_text:
                if not any(search_text in str(v).lower() for v in rec.values()):
                    continue
            filtered.append((i, rec))

        # ソート
        if self.sort_column:
            sc = self.sort_column
            def sort_key(item):
                idx, rec = item
                if sc == "_no":
                    return idx
                return str(rec.get(sc, "")).lower()
            filtered.sort(key=sort_key, reverse=self.sort_reverse)

        for i, rec in filtered:
            status_raw = rec.get("_status", "")
            sd = f"● {status_raw}" if status_raw == "回収済み" else (f"◉ {status_raw}" if status_raw == "返却済み" else status_raw)
            vals = []
            for col in all_cols:
                if col == "_no":
                    vals.append(i + 1)
                elif col == "_status":
                    vals.append(sd)
                elif col == "_barcode_id":
                    vals.append(rec.get("_barcode_id", ""))
                else:
                    vals.append(rec.get(col, ""))
            tag = "collected" if status_raw == "回収済み" else "returned"
            self.tree.insert("", "end", iid=str(i), values=vals, tags=(tag,))

        self.tree.tag_configure("collected", background=self.COLORS["collected"])
        self.tree.tag_configure("returned", background=self.COLORS["returned"])

        total = len(self.data_mgr.records)
        coll = sum(1 for r in self.data_mgr.records if r.get("_status") == "回収済み")
        ret = sum(1 for r in self.data_mgr.records if r.get("_status") == "返却済み")
        self.status_label.config(text=f"全{total}件 | 回収済み: {coll} | 返却済み: {ret} | 表示: {len(filtered)}件")

    def _refresh_history(self):
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        for entry in reversed(self.data_mgr.history[-100:]):
            self.history_tree.insert("", "end", values=(entry.get("timestamp", ""), entry.get("action", ""), entry.get("detail", "")))

    # ──── カラム表示設定ダイアログ ────
    def _show_column_settings(self):
        if not self.data_mgr.csv_columns:
            messagebox.showinfo("情報", "まずCSVを取り込んでください。"); return

        dlg = tk.Toplevel(self.root)
        dlg.title("カラム表示設定")
        dlg.geometry("550x500")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="カラムの表示順序・表示名・表示/非表示を設定", font=("Helvetica", 10, "bold")).pack(padx=10, pady=(10, 5))

        main = ttk.Frame(dlg); main.pack(fill="both", expand=True, padx=10, pady=5)

        # リスト
        list_frame = ttk.Frame(main); list_frame.pack(side="left", fill="both", expand=True)

        cols_tree = ttk.Treeview(list_frame, columns=("visible", "original", "display"), show="headings", height=15)
        cols_tree.heading("visible", text="表示"); cols_tree.column("visible", width=40, anchor="center")
        cols_tree.heading("original", text="元カラム名"); cols_tree.column("original", width=180)
        cols_tree.heading("display", text="表示名 (ダブルクリックで編集)"); cols_tree.column("display", width=200)
        csb = ttk.Scrollbar(list_frame, orient="vertical", command=cols_tree.yview)
        cols_tree.configure(yscrollcommand=csb.set)
        cols_tree.pack(side="left", fill="both", expand=True)
        csb.pack(side="right", fill="y")

        current_disp = self.data_mgr.get_display_columns()
        all_cols = list(self.data_mgr.csv_columns)
        # 順序: display_columns の順 + 含まれないもの
        ordered = list(current_disp)
        for c in all_cols:
            if c not in ordered:
                ordered.append(c)

        visible_set = set(current_disp)
        for col in ordered:
            vis = "✓" if col in visible_set else ""
            dn = self.data_mgr.get_column_display_name(col)
            cols_tree.insert("", "end", iid=col, values=(vis, col, dn))

        # ダブルクリックで表示名をインライン編集
        def on_double_click(event):
            region = cols_tree.identify_region(event.x, event.y)
            if region != "cell":
                return
            col_id = cols_tree.identify_column(event.x)
            # #3 = display列のみ編集可
            if col_id != "#3":
                return
            item = cols_tree.identify_row(event.y)
            if not item:
                return

            # セルの位置・サイズを取得
            bbox = cols_tree.bbox(item, column="display")
            if not bbox:
                return
            x, y, w, h = bbox

            vals = cols_tree.item(item, "values")
            current_name = vals[2]

            # Entry をTreeview上に配置
            edit_entry = tk.Entry(cols_tree, font=("Helvetica", 11))
            edit_entry.place(x=x, y=y, width=w, height=h)
            edit_entry.insert(0, current_name)
            edit_entry.select_range(0, tk.END)
            edit_entry.focus_set()

            def finish_edit(ev=None):
                new_name = edit_entry.get().strip()
                if new_name:
                    cols_tree.item(item, values=(vals[0], vals[1], new_name))
                edit_entry.destroy()

            def cancel_edit(ev=None):
                edit_entry.destroy()

            edit_entry.bind("<Return>", finish_edit)
            edit_entry.bind("<Escape>", cancel_edit)
            edit_entry.bind("<FocusOut>", finish_edit)

        cols_tree.bind("<Double-1>", on_double_click)

        # ボタン
        btn_frame = ttk.Frame(main); btn_frame.pack(side="right", padx=(10, 0))

        def move_up():
            sel = cols_tree.selection()
            if not sel: return
            idx = cols_tree.index(sel[0])
            if idx > 0:
                cols_tree.move(sel[0], "", idx - 1)

        def move_down():
            sel = cols_tree.selection()
            if not sel: return
            idx = cols_tree.index(sel[0])
            if idx < len(cols_tree.get_children()) - 1:
                cols_tree.move(sel[0], "", idx + 1)

        def toggle_visible():
            sel = cols_tree.selection()
            if not sel: return
            for s in sel:
                vals = cols_tree.item(s, "values")
                new_vis = "" if vals[0] == "✓" else "✓"
                cols_tree.item(s, values=(new_vis, vals[1], vals[2]))

        def reset_order():
            for item in cols_tree.get_children():
                cols_tree.delete(item)
            for col in all_cols:
                dn = col  # リセットなのでエイリアスも戻す
                cols_tree.insert("", "end", iid=col, values=("✓", col, dn))

        def apply_settings():
            new_display = []
            new_aliases = {}
            for item in cols_tree.get_children():
                vals = cols_tree.item(item, "values")
                orig = vals[1]
                disp_name = vals[2]
                if vals[0] == "✓":
                    new_display.append(orig)
                if disp_name != orig:
                    new_aliases[orig] = disp_name
            self.data_mgr.display_columns = new_display
            self.data_mgr.column_aliases = new_aliases
            self.data_mgr.save()
            self._refresh_table()
            dlg.destroy()
            messagebox.showinfo("完了", "カラム表示設定を保存しました。")

        ttk.Button(btn_frame, text="▲ 上へ", command=move_up, width=12).pack(pady=2)
        ttk.Button(btn_frame, text="▼ 下へ", command=move_down, width=12).pack(pady=2)
        ttk.Button(btn_frame, text="表示切替", command=toggle_visible, width=12).pack(pady=2)
        ttk.Separator(btn_frame, orient="horizontal").pack(fill="x", pady=8)
        ttk.Button(btn_frame, text="リセット", command=reset_order, width=12).pack(pady=2)
        ttk.Separator(btn_frame, orient="horizontal").pack(fill="x", pady=8)
        ttk.Button(btn_frame, text="✓ 適用", command=apply_settings, width=12).pack(pady=2)
        ttk.Button(btn_frame, text="キャンセル", command=dlg.destroy, width=12).pack(pady=2)

    # ──── イベントハンドラ ────
    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except (ValueError, IndexError):
            return
        if 0 <= idx < len(self.data_mgr.records):
            rec = self.data_mgr.records[idx]
            bv = rec.get("_barcode_id", "")
            if bv:
                self._show_barcode(bv)
                # 詳細情報を表示
                info_parts = [f"ID: {bv}", rec.get("_status", "")]
                # 主要フィールドも表示
                for col in self.data_mgr.csv_columns[:3]:
                    val = rec.get(col, "")
                    if val:
                        dn = self.data_mgr.get_column_display_name(col)
                        info_parts.append(f"{dn}: {val}")
                self.barcode_info_label.config(text=" | ".join(info_parts))
            else:
                self.barcode_canvas.config(text="バーコードIDなし", image="")
                self.barcode_info_label.config(text="")

    def _on_double_click(self, event=None):
        sel = self.tree.selection()
        if not sel: return
        idx = int(sel[0])
        if 0 <= idx < len(self.data_mgr.records):
            self._show_edit_dialog(idx)

    def _on_scan_mode_change(self):
        if self.scan_mode_var.get() == "instant":
            self.batch_frame.pack_forget()
            self.scan_mode_desc.config(text="スキャン → 自動ステータストグル")
        else:
            self.batch_frame.pack(fill="x", pady=(5, 0))
            self.scan_mode_desc.config(text="スキャン → リスト蓄積 → 一括適用")

    def _on_scan(self, event=None):
        val = self.scan_var.get().strip()
        if not val: return
        results = self.data_mgr.find_by_barcode(val)
        self.scanned_indices = [i for i, _ in results]
        if not results:
            self.scan_result_label.config(text=f"'{val}' 該当なし", fg=self.COLORS["danger"])
            self.data_mgr.add_history("スキャン", f"値:{val} → 該当なし"); self._refresh_history()
            self.scan_var.set(""); self.scan_entry.focus_set(); return

        self.tree.selection_set([str(i) for i, _ in results])
        if results: self.tree.see(str(results[0][0]))

        if self.scan_mode_var.get() == "instant":
            info = []
            for idx, rec in results:
                old = rec.get("_status", "回収済み")
                new = "返却済み" if old == "回収済み" else "回収済み"
                self.data_mgr.update_status(idx, new)
                info.append(f"{rec.get('_barcode_id','')}: {old}→{new}")
            self._refresh_table(); self._refresh_history()
            self.scan_result_label.config(text=f"即時反映: {len(results)}件\n" + "\n".join(info), fg=self.COLORS["success"])
        else:
            added = 0
            for idx, rec in results:
                bid = rec.get("_barcode_id", "")
                old = rec.get("_status", "回収済み")
                if not any(x[0] == idx for x in self.batch_scan_list):
                    self.batch_scan_list.append((idx, bid, old))
                    new = "返却済み" if old == "回収済み" else "回収済み"
                    self.batch_listbox.insert(tk.END, f"[{idx+1}] {bid}: {old}→{new}")
                    added += 1
            self.batch_count_label.config(text=f"{len(self.batch_scan_list)}件")
            self.scan_result_label.config(text=f"{added}件追加 (計{len(self.batch_scan_list)}件)" if added else f"'{val}' 追加済み",
                                          fg=self.COLORS["primary"] if added else self.COLORS["warning"])
            self.data_mgr.add_history("スキャン(一括)", f"値:{val}"); self._refresh_history()

        self.scan_var.set(""); self.scan_entry.focus_set()

    def _batch_apply(self):
        if not self.batch_scan_list:
            messagebox.showwarning("空", "リストが空です。"); return
        n = len(self.batch_scan_list)
        if not messagebox.askyesno("確認", f"{n}件トグルしますか？"): return
        for idx, bid, old in self.batch_scan_list:
            new = "返却済み" if old == "回収済み" else "回収済み"
            self.data_mgr.update_status(idx, new)
        self.data_mgr.add_history("一括変更", f"{n}件トグル")
        self._refresh_table(); self._refresh_history()
        self.scan_result_label.config(text=f"{n}件変更完了", fg=self.COLORS["success"])
        self._batch_clear()

    def _batch_remove(self):
        sel = self.batch_listbox.curselection()
        for i in sorted(sel, reverse=True):
            self.batch_listbox.delete(i)
            if i < len(self.batch_scan_list): self.batch_scan_list.pop(i)
        self.batch_count_label.config(text=f"{len(self.batch_scan_list)}件")

    def _batch_clear(self):
        self.batch_scan_list.clear(); self.batch_listbox.delete(0, tk.END)
        self.batch_count_label.config(text="0件")

    def _on_barcode_column_change(self, event=None):
        col = self.bc_column_var.get()
        if col:
            self.data_mgr.barcode_column = col
            for rec in self.data_mgr.records:
                if col in rec: rec["_barcode_id"] = rec[col]
            self.data_mgr.save(); self._refresh_table()
            messagebox.showinfo("設定完了", f"バーコードカラム: '{col}'")

    # ──── CSV取り込み ────
    def _import_csv(self):
        fp = filedialog.askopenfilename(title="CSV選択", filetypes=[("CSV", "*.csv"), ("テキスト", "*.txt"), ("すべて", "*.*")])
        if not fp: return
        ed = tk.Toplevel(self.root); ed.title("エンコーディング"); ed.geometry("300x180"); ed.transient(self.root); ed.grab_set()
        tk.Label(ed, text="文字コードを選択:", font=("Helvetica", 10)).pack(pady=10)
        ev = tk.StringVar(value="utf-8")
        for enc in ["utf-8", "shift_jis", "cp932", "euc-jp"]:
            ttk.Radiobutton(ed, text=enc, variable=ev, value=enc).pack(anchor="w", padx=30)
        def do_imp():
            ed.destroy()
            try:
                n = self.data_mgr.import_csv(fp, ev.get())
                self._update_column_combo(); self._refresh_table(); self._refresh_history()
                messagebox.showinfo("完了", f"{n}件取り込み完了")
            except Exception as e:
                messagebox.showerror("エラー", str(e))
        ttk.Button(ed, text="取り込む", command=do_imp).pack(pady=10)

    def _update_column_combo(self):
        self.bc_column_combo["values"] = self.data_mgr.csv_columns
        if self.data_mgr.barcode_column and self.data_mgr.barcode_column in self.data_mgr.csv_columns:
            self.bc_column_var.set(self.data_mgr.barcode_column)

    # ──── バーコード ────
    def _show_barcode(self, value):
        if not HAS_PIL: self.barcode_canvas.config(text="Pillow必要"); return
        try:
            img = generate_code128_image(value, width=380, height=100)
            self.barcode_photo = ImageTk.PhotoImage(img)
            self.barcode_canvas.config(image=self.barcode_photo, text="")
            self._current_barcode_value = value; self._current_barcode_image = img
        except Exception as e:
            self.barcode_canvas.config(text=f"エラー: {e}", image="")

    def _print_barcode(self):
        sel = self.tree.selection()
        if not sel: messagebox.showwarning("選択なし", "印刷レコードを選択してください。"); return
        images = []
        for s in sel:
            idx = int(s)
            if 0 <= idx < len(self.data_mgr.records):
                bv = self.data_mgr.records[idx].get("_barcode_id", "")
                if bv:
                    try: images.append((bv, generate_code128_image(bv, width=400, height=120)))
                    except: pass
        if not images: return
        margin = 20
        th = sum(img.height for _, img in images) + margin * (len(images) + 1)
        mw = max(img.width for _, img in images) + margin * 2
        pi = Image.new("RGB", (mw, th), "white")
        y = margin
        for _, img in images:
            pi.paste(img, ((mw - img.width) // 2, y)); y += img.height + margin
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                pi.save(tmp.name); tp = tmp.name
            if sys.platform == "darwin": subprocess.run(["lpr", tp])
            elif sys.platform == "win32": os.startfile(tp, "print")
            else:
                try: subprocess.run(["lpr", tp], check=True)
                except: subprocess.run(["xdg-open", tp])
            self.data_mgr.add_history("バーコード印刷", f"{len(images)}件"); self._refresh_history()
        except Exception as e:
            messagebox.showerror("エラー", str(e))

    def _save_barcode_image(self):
        if not hasattr(self, "_current_barcode_image") or not self._current_barcode_image:
            messagebox.showwarning("なし", "バーコードがありません。"); return
        fp = filedialog.asksaveasfilename(title="保存", defaultextension=".png",
                                           initialfile=f"barcode_{self._current_barcode_value}.png",
                                           filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")])
        if fp: self._current_barcode_image.save(fp)

    def _open_label_print_dialog(self):
        sel = self.tree.selection()
        recs = [self.data_mgr.records[int(s)] for s in sel if 0 <= int(s) < len(self.data_mgr.records)] if sel else self.data_mgr.records
        if not recs: messagebox.showwarning("なし", "レコードがありません。"); return
        LabelPrintDialog(self.root, recs, self.data_mgr, self.COLORS)

    # ──── ステータス ────
    def _mark_returned(self): self._change_status("返却済み")
    def _mark_collected(self): self._change_status("回収済み")
    def _change_status(self, ns):
        sel = self.tree.selection()
        if not sel: messagebox.showwarning("選択なし", "レコードを選択してください。"); return
        for s in sel: self.data_mgr.update_status(int(s), ns)
        self._refresh_table(); self._refresh_history()

    # ──── 編集 ────
    def _edit_selected(self):
        sel = self.tree.selection()
        if not sel: messagebox.showwarning("選択なし", "編集レコードを選択。"); return
        if len(sel) > 1: messagebox.showwarning("複数", "1件ずつ編集してください。"); return
        self._show_edit_dialog(int(sel[0]))

    def _show_edit_dialog(self, index):
        rec = self.data_mgr.records[index]
        dlg = tk.Toplevel(self.root)
        dlg.title(f"編集 - {rec.get('_barcode_id', '')}")
        dlg.geometry("600x700")
        dlg.transient(self.root); dlg.grab_set()

        bv = rec.get("_barcode_id", "")
        if bv and HAS_PIL:
            try:
                img = generate_code128_image(bv, width=450, height=80)
                photo = ImageTk.PhotoImage(img)
                lbl = tk.Label(dlg, image=photo, bg="white"); lbl.image = photo
                lbl.pack(fill="x", padx=10, pady=(10, 5))
            except: pass

        fo = ttk.Frame(dlg); fo.pack(fill="both", expand=True, padx=10, pady=5)
        cv = tk.Canvas(fo, highlightthickness=0)
        sb = ttk.Scrollbar(fo, orient="vertical", command=cv.yview)
        ff = ttk.Frame(cv)
        ff.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=ff, anchor="nw"); cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")

        entry_vars = {}
        row = 0
        ttk.Label(ff, text="データフィールド", font=("Helvetica", 11, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 3)); row += 1
        for col in self.data_mgr.csv_columns:
            dn = self.data_mgr.get_column_display_name(col)
            ttk.Label(ff, text=f"{dn}:", width=20, anchor="e").grid(row=row, column=0, sticky="e", padx=5, pady=2)
            var = tk.StringVar(value=str(rec.get(col, "")))
            ttk.Entry(ff, textvariable=var, width=35).grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            entry_vars[col] = var; row += 1

        ttk.Separator(ff).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8); row += 1
        ttk.Label(ff, text="管理情報", font=("Helvetica", 11, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=5); row += 1

        ttk.Label(ff, text="バーコードID:", width=20, anchor="e").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        bc_var = tk.StringVar(value=rec.get("_barcode_id", ""))
        ttk.Entry(ff, textvariable=bc_var, width=35).grid(row=row, column=1, sticky="ew", padx=5, pady=2); row += 1

        ttk.Label(ff, text="ステータス:", width=20, anchor="e").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        st_var = tk.StringVar(value=rec.get("_status", "回収済み"))
        ttk.Combobox(ff, textvariable=st_var, values=["回収済み", "返却済み"], state="readonly", width=15).grid(row=row, column=1, sticky="w", padx=5, pady=2); row += 1

        ttk.Label(ff, text="取り込み日時:", width=20, anchor="e").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        ttk.Label(ff, text=rec.get("_imported_at", ""), foreground=self.COLORS["muted"]).grid(row=row, column=1, sticky="w", padx=5, pady=2); row += 1

        ff.grid_columnconfigure(1, weight=1)

        def save():
            updates = {}
            for col, var in entry_vars.items():
                if var.get() != str(rec.get(col, "")): updates[col] = var.get()
            nb = bc_var.get().strip()
            if nb and nb != rec.get("_barcode_id", ""): updates["_barcode_id"] = nb
            ns = st_var.get()
            if ns != rec.get("_status", ""): updates["_status"] = ns
            if updates:
                self.data_mgr.update_record(index, updates)
                self._refresh_table(); self._refresh_history()
                messagebox.showinfo("完了", f"{len(updates)}件変更保存", parent=dlg)
            dlg.destroy()

        bf = ttk.Frame(dlg); bf.pack(fill="x", padx=10, pady=10)
        ttk.Button(bf, text="保存", command=save).pack(side="left", padx=8)
        ttk.Button(bf, text="キャンセル", command=dlg.destroy).pack(side="right", padx=8)

    # ──── 削除・クリア ────
    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel: return
        if not messagebox.askyesno("確認", f"{len(sel)}件削除しますか？"): return
        for idx in sorted([int(s) for s in sel], reverse=True):
            self.data_mgr.delete_record(idx)
        self._refresh_table(); self._refresh_history()

    def _clear_all_data(self):
        if not messagebox.askyesno("確認", "全データ削除しますか？"): return
        self.data_mgr.clear_all(); self._refresh_table(); self._refresh_history()

    # ──── エクスポート ────
    def _export_json(self):
        fp = filedialog.asksaveasfilename(title="JSON保存", defaultextension=".json", initialfile="passport_export.json", filetypes=[("JSON", "*.json")])
        if fp:
            with open(fp, "w", encoding="utf-8") as f:
                json.dump({"records": self.data_mgr.records, "history": self.data_mgr.history, "exported_at": datetime.datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)

    def _export_history_csv(self):
        fp = filedialog.asksaveasfilename(title="履歴CSV", defaultextension=".csv", initialfile="history.csv", filetypes=[("CSV", "*.csv")])
        if fp:
            with open(fp, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f); w.writerow(["日時", "操作", "詳細"])
                for e in self.data_mgr.history:
                    w.writerow([e.get("timestamp", ""), e.get("action", ""), e.get("detail", "")])

    # ──── 設定 ────
    def _set_barcode_column(self):
        if not self.data_mgr.csv_columns:
            messagebox.showinfo("情報", "CSVを取り込んでください。"); return
        d = tk.Toplevel(self.root); d.title("バーコードカラム"); d.geometry("350x300"); d.transient(self.root); d.grab_set()
        tk.Label(d, text="バーコード値カラム:").pack(pady=10)
        v = tk.StringVar(value=self.data_mgr.barcode_column or "")
        for col in self.data_mgr.csv_columns:
            ttk.Radiobutton(d, text=col, variable=v, value=col).pack(anchor="w", padx=30)
        def apply():
            if v.get(): self.bc_column_var.set(v.get()); self._on_barcode_column_change()
            d.destroy()
        ttk.Button(d, text="適用", command=apply).pack(pady=10)

    def _set_data_file(self):
        fp = filedialog.asksaveasfilename(title="データファイル場所", defaultextension=".json", initialfile="passport_data.json", filetypes=[("JSON", "*.json")])
        if fp: self.data_mgr.data_file = fp; self.data_mgr.save()

    # ──── ヘルプ ────
    def _show_help(self):
        ht = """【パスポート管理システム 使い方】

■ CSV取り込み (Ctrl+I)
  任意のCSV構造に対応。項目が自動的にカラムとして登録されます。

■ カラム表示設定 (設定メニュー / ツールバー)
  - 列の表示順を上下ボタンで並べ替え
  - 表示/非表示を切り替え
  - カラム表示名を編集

■ テーブルソート
  ヘッダーをクリックで昇順▲/降順▼/解除をトグル

■ レコード編集 (Ctrl+E / ダブルクリック)
  全フィールドを編集可能

■ バーコードラベル印刷 (Ctrl+P)
  「印刷内容」タブで各項目を:
  - バーコード: バーコード画像として印刷
  - テキスト: 文字情報として印刷
  - 非表示: 印刷しない
  の3択で設定可能

■ スキャン
  即時反映 / 一括モード切替対応

■ キーボードショートカット
  Ctrl+I:CSV  Ctrl+P:ラベル印刷  Ctrl+E:編集  Ctrl+Q:終了
"""
        d = tk.Toplevel(self.root); d.title("使い方"); d.geometry("550x550"); d.transient(self.root)
        t = tk.Text(d, wrap="word", font=("Helvetica", 10), padx=15, pady=15)
        t.pack(fill="both", expand=True); t.insert("1.0", ht); t.config(state="disabled")
        ttk.Button(d, text="閉じる", command=d.destroy).pack(pady=10)


# ==============================================================================
# エントリーポイント
# ==============================================================================

def main():
    if not HAS_PIL:
        print("エラー: Pillow が必要です。pip install Pillow")
        sys.exit(1)

    # バンドル時: サンプルCSVをデータディレクトリに初回コピー
    if getattr(sys, 'frozen', False):
        data_dir = get_data_dir()
        sample_dest = os.path.join(data_dir, "sample_passports.csv")
        if not os.path.exists(sample_dest):
            sample_src = get_resource_path("sample_passports.csv")
            if os.path.exists(sample_src):
                shutil.copy2(sample_src, sample_dest)

    root = tk.Tk()
    app = PassportManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
