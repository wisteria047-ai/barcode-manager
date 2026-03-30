#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汎用バーコード管理システム v2.0.0
プロファイル設定式 — パスポート管理 / 書籍管理 / カスタム対応
"""

import csv
import datetime
import hashlib
import hmac as _hmac
import json
import logging
import math
import os
import shutil
import sys
import tempfile
import subprocess
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ==============================================================================
# 定数
# ==============================================================================

APP_VERSION   = "2.0.0"
APP_NAME      = "バーコード管理システム"
MAX_HISTORY   = 500          # 操作履歴の最大保持件数
PAGE_SIZE     = 500          # テーブル 1 ページの表示件数

# ライセンス設定
TRIAL_LIMIT   = 50           # 体験版の最大レコード数（全台帳合計）
# ★ リリース前に必ずここを変更してください ★
_APP_SECRET   = b"BM2024-XKJQ-9173-RSVP"
PURCHASE_URL  = "https://example.booth.pm/"   # ← 販売ページURLに変更

# カラースキーム
COLORS = {
    "primary":       "#1E40AF",
    "primary_light": "#3B82F6",
    "success":       "#15803D",
    "success_light": "#22C55E",
    "warning":       "#D97706",
    "danger":        "#DC2626",
    "bg":            "#F8FAFC",
    "card":          "#FFFFFF",
    "text":          "#1E293B",
    "muted":         "#64748B",
    "border":        "#E2E8F0",
        "toolbar_bg":    "#EFF6FF",
    # 拡張カラー
    "overdue_bg":    "#FEE2E2",
    "slate":         "#94A3B8",
    "shadow":        "#CBD5E1",
    "accent_light":  "#93C5FD",
    "bg_alt":        "#F1F5F9",
    "danger_dark":   "#991B1B",
    "danger_lighter":"#FEF2F2",
    "primary_lighter":"#BFDBFE",
    "badge_yellow":  "#FCD34D",
}
# フォントスキーム
FONTS = {
    "h1":           ("Helvetica", 18, "bold"),
    "h2":           ("Helvetica", 16, "bold"),
    "h3":           ("Helvetica", 14, "bold"),
    "h3_normal":    ("Helvetica", 14),
    "h4":           ("Helvetica", 13, "bold"),
    "h5":           ("Helvetica", 12, "bold"),
    "body_lg":      ("Helvetica", 12),
    "h6":           ("Helvetica", 11, "bold"),
    "body":         ("Helvetica", 11),
    "section":      ("Helvetica", 10, "bold"),
    "body_sm":      ("Helvetica", 10),
    "label_bold":   ("Helvetica", 9, "bold"),
    "caption":      ("Helvetica", 9),
    "small":        ("Helvetica", 8),
    "tiny":         ("Helvetica", 7),
    "stat_number":  ("Helvetica", 26, "bold"),
    "scan_input":   ("Helvetica", 15),
    "scan_large":   ("Helvetica", 18),
    "mono":         ("Courier", 11),
}
# 印刷 / PDF 定数
A4_WIDTH_MM       = 210
A4_HEIGHT_MM      = 297
REPORT_DPI        = 150
REPORT_MARGIN_MM  = 15

# バーコード画像サイズ
BARCODE_IMG_W      = 400       # 標準バーコード画像幅
BARCODE_IMG_H      = 120       # 標準バーコード画像高さ
BARCODE_PREVIEW_W  = 380       # プレビュー用バーコード幅
BARCODE_PREVIEW_H  = 100       # プレビュー用バーコード高さ
BARCODE_EDIT_W     = 450       # 編集ダイアログ用バーコード幅
BARCODE_EDIT_H     = 80        # 編集ダイアログ用バーコード高さ

# ラベル印刷マジックナンバー (mm)
LABEL_BC_MARGIN_MM   = 2.0     # ラベル内バーコード余白
LABEL_TEXT_LINE_H_MM = 3.5     # テキスト行高さ
LABEL_MIN_BC_H_MM   = 8.0     # バーコード最小高さ
LABEL_FONT_SIZE_MM   = 2.5     # ラベルフォントサイズ
LABEL_BC_GAP_MM      = 1.0     # バーコード間ギャップ
LABEL_BC_TEXT_H_MM   = 3.0     # バーコード下テキスト高さ

# キャンバスプレビュー (px)
PREVIEW_MARGIN_PX    = 10
LAYOUT_MARGIN_PX     = 20
INFO_BAR_HEIGHT_PX   = 36
PRINT_MARGIN_PX      = 20



# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ==============================================================================
# パスユーティリティ
# ==============================================================================

def get_data_dir() -> str:
    """書き込み可能なデータディレクトリを返す"""
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        elif sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support")
        else:
            base = os.path.expanduser("~/.local/share")
        d = os.path.join(base, "BarcodeManager")
        os.makedirs(d, exist_ok=True)
        return d
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(relative: str) -> str:
    """バンドル内リソースのフルパスを返す"""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)


def _atomic_save(path: str, payload: dict) -> None:
    """JSON をアトミックに保存する共通ヘルパー（tempfile + os.replace）。"""
    data_dir = os.path.dirname(os.path.abspath(path))
    os.makedirs(data_dir, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=data_dir, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except OSError as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise RuntimeError(f"データ保存エラー ({os.path.basename(path)}): {e}") from e


# ==============================================================================
# STEP 2 — ProfileTemplate & TEMPLATES
# ==============================================================================

@dataclass
class ProfileTemplate:
    label: str
    icon: str
    status_values: List[str]
    default_status: str
    status_colors: Dict[str, str]
    barcode_column_hint: str
    sample_csv: str


TEMPLATES: Dict[str, ProfileTemplate] = {
    "passport": ProfileTemplate(
        label="パスポート管理",
        icon="🛂",
        status_values=["回収済み", "返却済み"],
        default_status="回収済み",
        status_colors={"回収済み": "#DBEAFE", "返却済み": "#BBF7D0"},
        barcode_column_hint="Passport No",
        sample_csv="sample_passports.csv",
    ),
    "book": ProfileTemplate(
        label="書籍管理",
        icon="📚",
        status_values=["在庫あり", "貸出中", "返却済み", "紛失"],
        default_status="在庫あり",
        status_colors={
            "在庫あり": "#BBF7D0",
            "貸出中":   "#FEF3C7",
            "返却済み": "#DBEAFE",
            "紛失":     "#FEE2E2",
        },
        barcode_column_hint="ISBN",
        sample_csv="sample_books.csv",
    ),
    "custom": ProfileTemplate(
        label="カスタム",
        icon="📋",
        status_values=["有効", "無効"],
        default_status="有効",
        status_colors={"有効": "#BBF7D0", "無効": "#E2E8F0"},
        barcode_column_hint="",
        sample_csv="",
    ),
}

# ==============================================================================
# STEP 3 — Code128 バーコード生成（純粋 Python 実装）
# ==============================================================================

CODE128_PATTERNS = [
    "11011001100","11001101100","11001100110","10010011000","10010001100",
    "10001001100","10011001000","10011000100","10001100100","11001001000",
    "11001000100","11000100100","10110011100","10011011100","10011001110",
    "10111001100","10011101100","10011100110","11001110010","11001011100",
    "11001001110","11011100100","11001110100","11101101110","11101001100",
    "11100101100","11100100110","11101100100","11100110100","11100110010",
    "11011011000","11011000110","11000110110","10100011000","10001011000",
    "10001000110","10110001000","10001101000","10001100010","11010001000",
    "11000101000","11000100010","10110111000","10110001110","10001101110",
    "10111011000","10111000110","10001110110","11101110110","11010001110",
    "11000101110","11011101000","11011100010","11011101110","11101011000",
    "11101000110","11100010110","11101101000","11101100010","11100011010",
    "11101111010","11001000010","11110001010","10100110000","10100001100",
    "10010110000","10010000110","10000101100","10000100110","10110010000",
    "10110000100","10011010000","10011000010","10000110100","10000110010",
    "11000010010","11001010000","11110111010","11000010100","10001111010",
    "10100111100","10010111100","10010011110","10111100100","10011110100",
    "10011110010","11110100100","11110010100","11110010010","11011011110",
    "11011110110","11110110110","10101111000","10100011110","10001011110",
    "10111101000","10111100010","11110101000","11110100010","10111011110",
    "10111101110","11101011110","11110101110","11010000100","11010010000",
    "11010011100","1100011101011",
]

_CODE128B_START = 104
_CODE128_STOP   = 106


def _encode_code128b(data: str) -> List[int]:
    values = [_CODE128B_START]
    for ch in data:
        code = ord(ch) - 32
        if not (0 <= code <= 95):
            raise ValueError(f"Code128B でエンコードできない文字: {ch!r}")
        values.append(code)
    checksum = values[0]
    for i, v in enumerate(values[1:], 1):
        checksum += i * v
    values.append(checksum % 103)
    values.append(_CODE128_STOP)
    return values


def _get_japanese_font(size: int = 14):
    """日本語フォントを返す。見つからなければデフォルトフォント。"""
    candidates: List[str] = []
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", "C:/Windows")
        fonts_dir = os.path.join(windir, "Fonts")
        for fname in ["meiryo.ttc", "msgothic.ttc", "YuGothR.ttc",
                      "YuGothM.ttc", "msmincho.ttc"]:
            candidates.append(os.path.join(fonts_dir, fname))
    elif sys.platform == "darwin":
        candidates += [
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/HelveticaNeue.ttc",
        ]
    else:
        candidates += [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue
    return ImageFont.load_default()


def generate_code128_image(
    data: str,
    width: int = BARCODE_IMG_W,
    height: int = BARCODE_IMG_H,
    quiet_zone: int = 20,
    show_text: bool = True,
) -> "Image.Image":
    values  = _encode_code128b(data)
    pattern = "".join(CODE128_PATTERNS[v] for v in values)
    n_bars   = len(pattern)
    avail_w  = width - 2 * quiet_zone
    bar_w    = max(1, avail_w // n_bars)
    actual_w = bar_w * n_bars + 2 * quiet_zone
    text_h   = 25 if show_text else 0
    img = Image.new("RGB", (actual_w, height + text_h + 10), "white")
    draw = ImageDraw.Draw(img)
    x = quiet_zone
    for bit in pattern:
        if bit == "1":
            draw.rectangle([x, 5, x + bar_w - 1, height + 5], fill="black")
        x += bar_w
    if show_text:
        font  = _get_japanese_font(14)
        bbox  = draw.textbbox((0, 0), data, font=font)
        tw    = bbox[2] - bbox[0]
        tx    = (actual_w - tw) // 2
        draw.text((tx, height + 10), data, fill="black", font=font)
    return img


# ==============================================================================
# ライセンス管理
# ==============================================================================

class LicenseManager:
    """
    ライセンスキーの検証・保存を行うクラス。

    キー形式: BMGR-XXXX-YYYY-ZZZZ
      XXXX = シリアル番号（16進 4桁、0001〜FFFF = 最大65535本）
      YYYY = HMAC-SHA256(_APP_SECRET, "BMGR" + XXXX) の先頭4文字（大文字）
      ZZZZ = 同ハッシュの 5〜8 文字目

    keygen.py で生成したキーを認証ダイアログに入力することで機能解除。
    """

    FILENAME = "license.json"

    def __init__(self, data_dir: str) -> None:
        self.path        = os.path.join(data_dir, self.FILENAME)
        self._key: Optional[str] = None
        self._licensed   = False
        self._load()

    # ---- 永続化 ----

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            key = data.get("key", "")
            if self._validate(key):
                self._key      = key
                self._licensed = True
        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.warning("ライセンスファイル読み込みエラー: %s", e)

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"key": self._key}, f)
        except OSError as e:
            logger.warning("ライセンス保存エラー: %s", e)

    # ---- 検証 ----

    @staticmethod
    def _validate(key: str) -> bool:
        if not key:
            return False
        parts = key.strip().upper().split("-")
        if len(parts) != 4 or parts[0] != "BMGR":
            return False
        serial_hex = parts[1]
        try:
            serial = int(serial_hex, 16)
            if serial <= 0:
                return False
        except ValueError:
            return False
        msg      = f"BMGR{serial_hex}".encode()
        digest   = _hmac.new(_APP_SECRET, msg, hashlib.sha256).hexdigest().upper()
        expected = digest[:4] + digest[4:8]
        actual   = parts[2] + parts[3]
        return _hmac.compare_digest(expected, actual)

    # ---- 公開 API ----

    def activate(self, key: str) -> bool:
        """キーを認証する。成功なら True を返し保存する。"""
        if self._validate(key):
            self._key      = key.strip().upper()
            self._licensed = True
            self._save()
            return True
        return False

    @property
    def is_licensed(self) -> bool:
        return self._licensed

    @property
    def key(self) -> str:
        return self._key or ""


# ==============================================================================
# STEP 4 — DataManager（汎用・バグ修正版）
# ==============================================================================

class DataManager:
    """
    JSON ファイルへのデータ永続化を担うクラス。
    ・アトミック保存（tempfile + os.replace）
    ・BOM 付き CSV 自動吸収（utf-8-sig）
    ・バーコード重複チェック
    ・履歴上限 MAX_HISTORY
    ・add_history() は save() を呼ばない（呼び元が明示的に save）
    """

    def __init__(self, data_file: str, template: ProfileTemplate) -> None:
        self.data_file         = data_file
        self.template          = template
        self.records:          List[dict]       = []
        self.history:          List[dict]       = []
        self.csv_columns:      List[str]        = []
        self.barcode_column:   Optional[str]    = None
        self.display_columns:  List[str]        = []
        self.column_aliases:   Dict[str, str]   = {}
        self.column_order:     List[str]        = []
        self.print_settings:   Dict            = {}
        self.load()

    # ------------------------------------------------------------------ load/save

    def load(self) -> None:
        if not os.path.exists(self.data_file):
            return
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.records         = raw.get("records",         [])
            self.history         = raw.get("history",         [])
            self.csv_columns     = raw.get("csv_columns",     [])
            self.barcode_column  = raw.get("barcode_column",  None)
            self.display_columns = raw.get("display_columns", [])
            self.column_aliases  = raw.get("column_aliases",  {})
            self.column_order    = raw.get("column_order",    [])
            self.print_settings  = raw.get("print_settings",  {})
        except json.JSONDecodeError as e:
            logger.error("JSON 破損 %s: %s", self.data_file, e)
            messagebox.showerror(
                "データ読み込みエラー",
                f"データファイルが破損しています:\n{self.data_file}\n\n{e}",
            )
        except OSError as e:
            logger.error("ファイル読み込みエラー %s: %s", self.data_file, e)

    def save(self) -> None:
        """アトミック保存。クラッシュによるファイル破損を防ぐ。"""
        payload = {
            "version":         APP_VERSION,
            "records":         self.records,
            "history":         self.history,
            "csv_columns":     self.csv_columns,
            "barcode_column":  self.barcode_column,
            "display_columns": self.display_columns,
            "column_aliases":  self.column_aliases,
            "column_order":    self.column_order,
            "print_settings":  self.print_settings,
        }
        _atomic_save(self.data_file, payload)

    # ------------------------------------------------------------------ history

    def add_history(self, action: str, detail: str) -> None:
        """履歴を追加する。save() は呼ばない。"""
        entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action":    action,
            "detail":    detail,
        }
        self.history.append(entry)
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]

    # ------------------------------------------------------------------ CSV import

    def import_csv(
        self,
        filepath: str,
        encoding: str = "utf-8",
        max_records: Optional[int] = None,
    ) -> Tuple[int, List[str], bool]:
        """
        CSV を取り込む。
        Args:
            max_records: 取り込み後の最大レコード数。超えた分はスキップ（体験版制限）。
        Returns:
            (取り込み件数, 重複スキップしたバーコードIDのリスト, 上限に達したか)
        Raises:
            RuntimeError: 読み込み失敗時
        """
        # BOM 有無を自動吸収
        if encoding.lower() in ("utf-8", "utf8"):
            encoding = "utf-8-sig"

        imported:       int       = 0
        duplicates:     List[str] = []
        limit_reached:  bool      = False
        existing_barcodes = {
            r.get("_barcode_id") for r in self.records if r.get("_barcode_id")
        }

        try:
            with open(filepath, "r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    raise ValueError("CSV ヘッダーが見つかりません")

                # BOM 残骸除去
                new_cols = [c.lstrip("\ufeff").strip() for c in reader.fieldnames]

                if not self.csv_columns:
                    self.csv_columns    = new_cols
                    self.display_columns = list(new_cols)

                for row in reader:
                    # 上限チェック
                    if max_records is not None and len(self.records) >= max_records:
                        limit_reached = True
                        break

                    clean = {k.lstrip("\ufeff").strip(): v for k, v in row.items()}
                    bid   = self._make_barcode_id(clean, len(self.records) + imported)

                    if bid in existing_barcodes:
                        duplicates.append(bid)
                        continue

                    clean["_status"]      = self.template.default_status
                    clean["_barcode_id"]  = bid
                    clean["_imported_at"] = datetime.datetime.now().isoformat()
                    self.records.append(clean)
                    existing_barcodes.add(bid)
                    imported += 1

        except UnicodeDecodeError as e:
            raise RuntimeError(
                f"文字コードエラー: '{encoding}' で読み込めません。別のエンコードを試してください。"
            ) from e
        except Exception as e:
            raise RuntimeError(f"CSV 読み込みエラー: {e}") from e

        if imported > 0 or duplicates:
            detail = f"{os.path.basename(filepath)} から {imported} 件取り込み"
            if duplicates:
                detail += f"（重複スキップ: {len(duplicates)} 件）"
            if limit_reached:
                detail += f"（体験版上限 {max_records} 件のため残りをスキップ）"
            self.add_history("CSV取り込み", detail)
            self.save()

        return imported, duplicates, limit_reached

    def _make_barcode_id(self, record: dict, fallback_idx: int) -> str:
        if self.barcode_column and self.barcode_column in record:
            v = str(record[self.barcode_column]).strip()
            if v:
                return v
        # テンプレートヒントから自動検出
        hint = self.template.barcode_column_hint.lower()
        if hint:
            for k in record:
                if k.lower() == hint:
                    v = str(record[k]).strip()
                    if v:
                        return v
        prefix = "PP" if "passport" in self.data_file.lower() else "BK"
        return f"{prefix}{fallback_idx:06d}"

    # ------------------------------------------------------------------ CRUD

    def get_display_columns(self) -> List[str]:
        if self.display_columns:
            return [c for c in self.display_columns if c in self.csv_columns]
        return list(self.csv_columns)

    def get_column_display_name(self, col: str) -> str:
        return self.column_aliases.get(col, col)

    def find_by_barcode(self, value: str) -> List[Tuple[int, dict]]:
        results = []
        for i, rec in enumerate(self.records):
            if rec.get("_barcode_id") == value:
                results.append((i, rec))
                continue
            for k, v in rec.items():
                if not k.startswith("_") and str(v) == value:
                    results.append((i, rec))
                    break
        return results

    def update_status(self, index: int, new_status: str) -> None:
        if not (0 <= index < len(self.records)):
            return
        old = self.records[index].get("_status", "不明")
        self.records[index]["_status"] = new_status
        bid = self.records[index].get("_barcode_id", "N/A")
        self.add_history("ステータス変更", f"ID:{bid}  {old} → {new_status}")
        self.save()

    def update_record(self, index: int, updates: dict) -> List[str]:
        if not (0 <= index < len(self.records)):
            return []
        rec     = self.records[index]
        changes = []
        for k, nv in updates.items():
            ov = str(rec.get(k, ""))
            if str(nv) != ov:
                changes.append(f"{k}: '{ov}' → '{nv}'")
                rec[k] = nv
        if changes:
            bid    = rec.get("_barcode_id", "N/A")
            detail = f"ID:{bid} | " + " | ".join(changes[:5])
            if len(changes) > 5:
                detail += f" …他 {len(changes)-5} 件"
            self.add_history("レコード編集", detail)
            self.save()
        return changes

    def delete_record(self, index: int) -> None:
        if 0 <= index < len(self.records):
            rec = self.records.pop(index)
            self.add_history("レコード削除", f"ID:{rec.get('_barcode_id','N/A')} を削除")
            self.save()

    def clear_all(self) -> None:
        count = len(self.records)
        self.records.clear()
        self.add_history("全データクリア", f"{count} 件を削除")
        self.save()


# ==============================================================================
# STEP 5 — ProfileManager（profiles.json 管理）
# ==============================================================================

@dataclass
class Profile:
    id:        str
    type:      str   # TEMPLATES のキー
    name:      str
    data_file: str

    @property
    def template(self) -> ProfileTemplate:
        return TEMPLATES.get(self.type, TEMPLATES["custom"])


class ProfileManager:
    """profiles.json の読み書きを担うクラス。"""

    FILENAME = "profiles.json"

    def __init__(self, data_dir: str) -> None:
        self.path     = os.path.join(data_dir, self.FILENAME)
        self.profiles: List[Profile] = []
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for p in raw.get("profiles", []):
                self.profiles.append(Profile(
                    id        = p["id"],
                    type      = p.get("type", "custom"),
                    name      = p.get("name", ""),
                    data_file = p["data_file"],
                ))
        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.error("profiles.json 読み込みエラー: %s", e)

    def save(self) -> None:
        payload = {
            "version":  APP_VERSION,
            "profiles": [
                {"id": p.id, "type": p.type, "name": p.name, "data_file": p.data_file}
                for p in self.profiles
            ],
        }
        _atomic_save(self.path, payload)

    def add_profile(self, type_key: str, name: str) -> Profile:
        uid       = f"{type_key}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        data_file = os.path.join(os.path.dirname(self.path), f"{uid}_data.json")
        p         = Profile(id=uid, type=type_key, name=name, data_file=data_file)
        self.profiles.append(p)
        self.save()
        return p

    def remove_profile(self, profile_id: str) -> None:
        self.profiles = [p for p in self.profiles if p.id != profile_id]
        self.save()

    def is_empty(self) -> bool:
        return len(self.profiles) == 0


# ==============================================================================
# STEP 11a — Member / MemberManager（利用者管理）
# ==============================================================================

@dataclass
class Member:
    """利用者1件を表すデータクラス。"""
    id:         str
    name:       str
    ruby:       str  = ""    # 読み仮名（ソート用）
    barcode_id: str  = ""    # 利用者証バーコード（スキャン対応）
    email:      str  = ""
    phone:      str  = ""
    note:       str  = ""
    created_at: str  = ""
    active:     bool = True

    @property
    def display_name(self) -> str:
        return f"{self.name}（{self.barcode_id}）" if self.barcode_id else self.name


class MemberManager:
    """members.json の CRUD を担うクラス。"""
    FILENAME = "members.json"

    def __init__(self, data_dir: str) -> None:
        self.path    = os.path.join(data_dir, self.FILENAME)
        self.members: List[Member] = []
        self._load()

    # ------------------------------------------------------------------ I/O

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            fields = {f for f in Member.__dataclass_fields__}
            for m in raw.get("members", []):
                kwargs = {k: m[k] for k in fields if k in m}
                self.members.append(Member(**kwargs))
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error("members.json 読み込みエラー: %s", e)

    def save(self) -> None:
        payload = {
            "version": APP_VERSION,
            "members": [
                {"id": m.id, "name": m.name, "ruby": m.ruby,
                 "barcode_id": m.barcode_id, "email": m.email,
                 "phone": m.phone, "note": m.note,
                 "created_at": m.created_at, "active": m.active}
                for m in self.members
            ],
        }
        _atomic_save(self.path, payload)

    # ------------------------------------------------------------------ CRUD

    def add(self, name: str, barcode_id: str = "", ruby: str = "",
            email: str = "", phone: str = "", note: str = "") -> Member:
        mid = f"mbr_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self.members):04d}"
        m = Member(
            id=mid, name=name, ruby=ruby, barcode_id=barcode_id,
            email=email, phone=phone, note=note,
            created_at=datetime.datetime.now().isoformat(),
        )
        self.members.append(m)
        self.save()
        return m

    def update(self, member_id: str, **kwargs) -> bool:
        for m in self.members:
            if m.id == member_id:
                for k, v in kwargs.items():
                    if hasattr(m, k):
                        setattr(m, k, v)
                self.save()
                return True
        return False

    def delete(self, member_id: str) -> bool:
        """論理削除（active=False）。"""
        return self.update(member_id, active=False)

    # ------------------------------------------------------------------ 検索

    def find_by_id(self, member_id: str) -> Optional[Member]:
        for m in self.members:
            if m.id == member_id:
                return m
        return None

    def find_by_barcode(self, barcode_id: str) -> Optional[Member]:
        for m in self.members:
            if m.barcode_id == barcode_id and m.active:
                return m
        return None

    def get_active(self) -> List[Member]:
        return sorted(
            [m for m in self.members if m.active],
            key=lambda m: m.ruby or m.name,
        )


# ==============================================================================
# STEP 11b — LoanRecord / LoanManager（貸出管理）
# ==============================================================================

@dataclass
class LoanRecord:
    """貸出1件を表すデータクラス。"""
    loan_id:     str
    barcode_id:  str
    member_id:   str
    qty:         int            = 1
    loaned_at:   str            = ""
    due_date:    str            = ""   # "YYYY-MM-DD"  空=期限なし
    returned_at: Optional[str]  = None  # None=未返却
    note:        str            = ""

    @property
    def is_active(self) -> bool:
        return self.returned_at is None

    @property
    def is_overdue(self) -> bool:
        if not self.is_active or not self.due_date:
            return False
        return self.due_date < datetime.date.today().isoformat()

    @property
    def days_overdue(self) -> int:
        if not self.is_overdue:
            return 0
        due  = datetime.date.fromisoformat(self.due_date)
        return (datetime.date.today() - due).days


class LoanManager:
    """
    1プロファイル = 1 LoanManager。
    data_file = "{uuid}_data.json" → loans_file = "{uuid}_loans.json"
    """

    def __init__(self, data_file: str) -> None:
        base, _ = os.path.splitext(data_file)
        if base.endswith("_data"):
            base = base[:-5]
        self.loans_file = base + "_loans.json"
        self.loans: List[LoanRecord] = []
        self._load()

    # ------------------------------------------------------------------ I/O

    def _load(self) -> None:
        if not os.path.exists(self.loans_file):
            return
        try:
            with open(self.loans_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for ln in raw.get("loans", []):
                self.loans.append(LoanRecord(
                    loan_id     = ln["loan_id"],
                    barcode_id  = ln["barcode_id"],
                    member_id   = ln["member_id"],
                    qty         = ln.get("qty", 1),
                    loaned_at   = ln.get("loaned_at", ""),
                    due_date    = ln.get("due_date", ""),
                    returned_at = ln.get("returned_at"),
                    note        = ln.get("note", ""),
                ))
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error("loans ファイル読み込みエラー: %s", e)

    def save(self) -> None:
        payload = {
            "version": APP_VERSION,
            "loans": [
                {"loan_id": l.loan_id, "barcode_id": l.barcode_id,
                 "member_id": l.member_id, "qty": l.qty,
                 "loaned_at": l.loaned_at, "due_date": l.due_date,
                 "returned_at": l.returned_at, "note": l.note}
                for l in self.loans
            ],
        }
        _atomic_save(self.loans_file, payload)

    # ------------------------------------------------------------------ クエリ

    def get_active_loans(self) -> List[LoanRecord]:
        return [l for l in self.loans if l.is_active]

    def get_active_loan_for_item(self, barcode_id: str) -> Optional[LoanRecord]:
        for l in self.loans:
            if l.barcode_id == barcode_id and l.is_active:
                return l
        return None

    def get_overdue_loans(self) -> List[LoanRecord]:
        return [l for l in self.loans if l.is_overdue]

    def get_loans_for_member(self, member_id: str) -> List[LoanRecord]:
        return [l for l in self.loans if l.member_id == member_id and l.is_active]

    # ------------------------------------------------------------------ 操作

    def checkout(self, barcode_id: str, member_id: str,
                 qty: int = 1, due_date: str = "", note: str = "") -> LoanRecord:
        lid = f"loan_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        rec = LoanRecord(
            loan_id    = lid,
            barcode_id = barcode_id,
            member_id  = member_id,
            qty        = qty,
            loaned_at  = datetime.datetime.now().isoformat(),
            due_date   = due_date,
            note       = note,
        )
        self.loans.append(rec)
        self.save()
        return rec

    def return_item(self, loan_id: str) -> Optional[LoanRecord]:
        for l in self.loans:
            if l.loan_id == loan_id and l.is_active:
                l.returned_at = datetime.datetime.now().isoformat()
                self.save()
                return l
        return None




# ==============================================================================
# UI ヘルパー関数
# ==============================================================================

def _make_modal_dialog(
    parent: tk.Misc,
    title: str,
    geometry: str,
    *,
    resizable: bool = True,
    grab: bool = True,
) -> tk.Toplevel:
    """標準モーダルダイアログを生成する共通ヘルパー。"""
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.geometry(geometry)
    if not resizable:
        dlg.resizable(False, False)
    dlg.transient(parent)
    if grab:
        dlg.grab_set()
    return dlg


def _make_scrollable_frame(parent: tk.Misc) -> Tuple[tk.Canvas, ttk.Frame]:
    """Canvas + Scrollbar + 内部Frame のスクロール可能フレームを生成。"""
    canvas = tk.Canvas(parent, highlightthickness=0)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    return canvas, inner


def _make_treeview(
    parent: tk.Misc,
    columns: list,
    *,
    height: int = 10,
    selectmode: str = "browse",
    default_anchor: str = "w",
) -> Tuple[ttk.Treeview, ttk.Scrollbar]:
    """Treeview + 縦Scrollbar を生成する共通ヘルパー。

    columns: [(col_id, heading, width), ...] or [(col_id, heading, width, anchor), ...]
    """
    col_ids = [c[0] for c in columns]
    tree = ttk.Treeview(parent, columns=col_ids, show="headings",
                        height=height, selectmode=selectmode)
    for spec in columns:
        col_id, heading, width = spec[0], spec[1], spec[2]
        anchor = spec[3] if len(spec) > 3 else default_anchor
        tree.heading(col_id, text=heading)
        tree.column(col_id, width=width, anchor=anchor)
    vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    return tree, vsb


# ==============================================================================
# STEP 6 — SetupWizard（初回起動ダイアログ）
# ==============================================================================

class SetupWizard:
    """
    profiles.json が空の場合に表示する初回セットアップ画面。
    OK ボタン押下で ProfileManager に最初のプロファイルを追加し、
    self.created_profile に結果を格納する。
    キャンセル時は created_profile = None。
    """

    def __init__(self, parent: tk.Tk, profile_mgr: ProfileManager) -> None:
        self.profile_mgr     = profile_mgr
        self.created_profile: Optional[Profile] = None

        self.dlg = _make_modal_dialog(parent, f"{APP_NAME} — セットアップ", "480x400", resizable=False)
        self.dlg.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._build_ui()
        self.dlg.wait_window()

    def _build_ui(self) -> None:
        # ヘッダー
        hdr = tk.Frame(self.dlg, bg=COLORS["primary"], height=60)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(
            hdr,
            text=f"  {APP_NAME}  v{APP_VERSION}",
            font=FONTS["h2"],
            fg="white", bg=COLORS["primary"],
        ).pack(side="left", padx=16, pady=10)

        body = tk.Frame(self.dlg, bg=COLORS["bg"], padx=30, pady=20)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text="最初の管理台帳を作成してください",
            font=FONTS["h5"],
            bg=COLORS["bg"], fg=COLORS["text"],
        ).pack(anchor="w", pady=(0, 12))

        # テンプレート選択
        tk.Label(body, text="テンプレート:", bg=COLORS["bg"],
                 font=FONTS["body_sm"]).pack(anchor="w")
        self._type_var = tk.StringVar(value="passport")

        tpl_frame = tk.Frame(body, bg=COLORS["bg"])
        tpl_frame.pack(fill="x", pady=(4, 12))
        for key, tpl in TEMPLATES.items():
            ttk.Radiobutton(
                tpl_frame,
                text=f"{tpl.icon}  {tpl.label}",
                variable=self._type_var,
                value=key,
            ).pack(anchor="w", padx=10, pady=2)

        # 台帳名
        tk.Label(body, text="台帳名:", bg=COLORS["bg"],
                 font=FONTS["body_sm"]).pack(anchor="w")
        self._name_var = tk.StringVar()

        def _on_type_change(*_):
            key = self._type_var.get()
            if not self._name_var.get() or self._name_var.get() in [
                t.label for t in TEMPLATES.values()
            ]:
                self._name_var.set(TEMPLATES[key].label)

        self._type_var.trace_add("write", _on_type_change)
        _on_type_change()

        ttk.Entry(body, textvariable=self._name_var, width=36,
                  font=FONTS["body"]).pack(anchor="w", pady=(4, 0))

        # ボタン
        btn_frame = tk.Frame(body, bg=COLORS["bg"])
        btn_frame.pack(fill="x", pady=(24, 0))
        ttk.Button(btn_frame, text="キャンセル",
                   command=self._on_cancel).pack(side="right", padx=(6, 0))
        ttk.Button(btn_frame, text="作成して開始",
                   command=self._on_ok).pack(side="right")

    def _on_ok(self) -> None:
        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning("入力エラー", "台帳名を入力してください。",
                                   parent=self.dlg)
            return
        self.created_profile = self.profile_mgr.add_profile(
            self._type_var.get(), name
        )
        self.dlg.destroy()

    def _on_cancel(self) -> None:
        self.created_profile = None
        self.dlg.destroy()


# ==============================================================================
# STEP 17 — MemberTab（利用者管理タブ UI）
# ==============================================================================

class MemberTab(ttk.Frame):
    """利用者管理タブ (S1)。"""

    def __init__(self, parent, member_mgr: MemberManager,
                 get_loan_mgrs) -> None:   # Callable[[], List[LoanManager]]
        super().__init__(parent)
        self.member_mgr   = member_mgr
        self._get_loan_mgrs = get_loan_mgrs
        self._build_ui()
        self._refresh_table()

    # ---------------------------------------------------------------- UI 構築

    def _build_ui(self) -> None:
        # ツールバー
        tb = tk.Frame(self, bg=COLORS["toolbar_bg"],
                      highlightbackground=COLORS["border"], highlightthickness=1)
        tb.pack(fill="x", pady=(0, 4), ipady=3)

        def tbtn(text, cmd):
            return ttk.Button(tb, text=text, command=cmd, style="Toolbar.TButton")

        tbtn("新規登録",    self._add_member).pack(side="left", padx=(5, 2))
        tbtn("編集",        self._edit_member).pack(side="left", padx=2)
        tbtn("退会（無効）", self._deactivate_member).pack(side="left", padx=2)

        # 検索
        sf = tk.Frame(self, bg=COLORS["bg"]); sf.pack(fill="x", padx=6, pady=2)
        tk.Label(sf, text="検索:", bg=COLORS["bg"]).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh_table())
        ttk.Entry(sf, textvariable=self.search_var, width=30).pack(side="left", padx=4)

        # Treeview
        cols = ("name", "ruby", "barcode_id", "email", "phone", "loans")
        self.tree, _ = _make_treeview(self, [
            ("name", "氏名", 160), ("ruby", "よみ", 140),
            ("barcode_id", "利用者ID", 110), ("email", "メール", 180),
            ("phone", "電話", 120), ("loans", "現貸出数", 80),
        ])
        self.tree.bind("<Double-1>", lambda _: self._edit_member())

        # ステータスバー
        self.status_var = tk.StringVar()
        tk.Label(self, textvariable=self.status_var,
                 bg=COLORS["bg"], fg=COLORS["muted"],
                 font=FONTS["caption"], anchor="w").pack(fill="x", padx=6)

    # ---------------------------------------------------------------- テーブル更新

    def _refresh_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        search  = self.search_var.get().lower()
        members = self.member_mgr.get_active()
        loan_mgrs = self._get_loan_mgrs()
        shown = 0
        for m in members:
            if search and not any(
                search in s.lower()
                for s in [m.name, m.ruby or "", m.barcode_id or "",
                          m.email or "", m.phone or ""]
            ):
                continue
            active_cnt = sum(len(lm.get_loans_for_member(m.id)) for lm in loan_mgrs)
            self.tree.insert("", "end", iid=m.id, values=(
                m.name, m.ruby or "", m.barcode_id or "",
                m.email or "", m.phone or "", active_cnt,
            ))
            shown += 1
        self.status_var.set(f"利用者: {shown} 名 / 登録総数: {len(members)} 名")

    # ---------------------------------------------------------------- 新規登録

    def _add_member(self) -> None:
        self._member_form_dialog(None)

    def _edit_member(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("選択なし", "編集する利用者を選択してください。"); return
        self._member_form_dialog(sel[0])

    def _member_form_dialog(self, member_id: Optional[str]) -> None:
        existing = self.member_mgr.find_by_id(member_id) if member_id else None
        dlg = _make_modal_dialog(self.winfo_toplevel(), "利用者登録" if not existing else "利用者編集", "420x360", resizable=False)

        frm = ttk.Frame(dlg); frm.pack(padx=20, pady=16, fill="both")
        fields = [
            ("氏名 *",     "name",       existing.name        if existing else ""),
            ("よみ",       "ruby",       existing.ruby        if existing else ""),
            ("利用者ID",   "barcode_id", existing.barcode_id  if existing else ""),
            ("メール",     "email",      existing.email       if existing else ""),
            ("電話",       "phone",      existing.phone       if existing else ""),
            ("メモ",       "note",       existing.note        if existing else ""),
        ]
        vars_: Dict[str, tk.StringVar] = {}
        for i, (lbl, key, val) in enumerate(fields):
            tk.Label(frm, text=f"{lbl}:", anchor="e", width=10).grid(
                row=i, column=0, sticky="e", padx=6, pady=4)
            v = tk.StringVar(value=val)
            ttk.Entry(frm, textvariable=v, width=28).grid(
                row=i, column=1, sticky="ew", pady=4)
            vars_[key] = v
        frm.grid_columnconfigure(1, weight=1)

        err_var = tk.StringVar()
        tk.Label(dlg, textvariable=err_var, fg=COLORS["danger"],
                 font=FONTS["caption"]).pack()

        def _ok() -> None:
            name = vars_["name"].get().strip()
            if not name:
                err_var.set("氏名は必須です。"); return
            kwargs = {k: vars_[k].get().strip() for k in
                      ("ruby", "barcode_id", "email", "phone", "note")}
            if existing:
                self.member_mgr.update(existing.id, name=name, **kwargs)
            else:
                self.member_mgr.add(name=name, **kwargs)
            self._refresh_table()
            dlg.destroy()

        bf = ttk.Frame(dlg); bf.pack(pady=8)
        ttk.Button(bf, text="保存",      command=_ok).pack(side="left", padx=6)
        ttk.Button(bf, text="キャンセル",command=dlg.destroy).pack(side="left", padx=6)

    def _deactivate_member(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("選択なし", "利用者を選択してください。"); return
        m = self.member_mgr.find_by_id(sel[0])
        if not m:
            return
        if messagebox.askyesno("確認", f"「{m.name}」を退会（無効）にしますか？"):
            self.member_mgr.delete(m.id)
            self._refresh_table()


# ==============================================================================
# STEP 18 — DashboardTab（ダッシュボード）
# ==============================================================================

class DashboardTab(ttk.Frame):
    """全台帳の集計を表示するダッシュボードタブ (A4)。"""

    def __init__(self, parent, prof_mgr: "ProfileManager",
                 get_data_mgrs,   # Callable[[], List[DataManager]]
                 get_loan_mgrs,   # Callable[[], List[LoanManager]]
                 member_mgr: MemberManager) -> None:
        super().__init__(parent)
        self.prof_mgr       = prof_mgr
        self._get_data_mgrs = get_data_mgrs
        self._get_loan_mgrs = get_loan_mgrs
        self.member_mgr     = member_mgr
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        hdr = tk.Frame(self, bg=COLORS["primary"], height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="  ダッシュボード",
                 font=FONTS["h3"],
                 fg="white", bg=COLORS["primary"]).pack(side="left", padx=12)
        ttk.Button(hdr, text="更新", command=self.refresh).pack(side="right", padx=10)

        # サマリーカード行
        self.card_frame = tk.Frame(self, bg=COLORS["bg"])
        self.card_frame.pack(fill="x", padx=10, pady=10)

        # 台帳別集計テーブル
        tbl_lbl = tk.Label(self, text="台帳別サマリー",
                           font=FONTS["h6"],
                           bg=COLORS["bg"], anchor="w")
        tbl_lbl.pack(fill="x", padx=12, pady=(4, 0))

        tf = ttk.Frame(self); tf.pack(fill="both", expand=True, padx=10, pady=4)
        cols = ("name", "total", "lending", "overdue", "stock")
        self.table, _ = _make_treeview(tf, [
            ("name", "台帳名", 200, "w"), ("total", "総件数", 80, "center"),
            ("lending", "貸出中", 80, "center"), ("overdue", "延滞", 80, "center"),
            ("stock", "在庫あり", 80, "center"),
        ], height=8)
        self.table.tag_configure("has_overdue", foreground=COLORS["danger"])

        # 延滞アラート一覧
        al_lbl = tk.Label(self, text="延滞アイテム一覧",
                          font=FONTS["h6"],
                          bg=COLORS["bg"], fg=COLORS["danger"], anchor="w")
        al_lbl.pack(fill="x", padx=12, pady=(8, 0))
        af = ttk.Frame(self); af.pack(fill="both", expand=True, padx=10, pady=4)
        al_cols = ("ledger", "barcode_id", "member", "due_date", "days")
        self.alert_tree, _ = _make_treeview(af, [
            ("ledger", "台帳", 120), ("barcode_id", "ID", 130),
            ("member", "利用者", 140), ("due_date", "期限", 90),
            ("days", "超過日数", 80),
        ], height=6)
        self.alert_tree.tag_configure("overdue_row",
                                      background=COLORS["overdue_bg"], foreground=COLORS["danger"])

    def _make_card(self, parent: tk.Frame, label: str,
                   value: str, color: str) -> None:
        card = tk.Frame(parent, bg=color, padx=18, pady=10,
                        relief="raised", bd=1)
        card.pack(side="left", padx=6, pady=4)
        tk.Label(card, text=value,
                 font=FONTS["stat_number"],
                 bg=color, fg="white").pack()
        tk.Label(card, text=label,
                 font=FONTS["caption"],
                 bg=color, fg="white").pack()

    def refresh(self) -> None:
        """全データを集計して表示を更新する。"""
        for w in self.card_frame.winfo_children():
            w.destroy()

        data_mgrs = self._get_data_mgrs()
        loan_mgrs = self._get_loan_mgrs()

        total_items   = sum(len(d.records) for d in data_mgrs)
        total_loans   = sum(len(l.get_active_loans()) for l in loan_mgrs)
        total_overdue = sum(len(l.get_overdue_loans()) for l in loan_mgrs)
        total_members = len(self.member_mgr.get_active())

        self._make_card(self.card_frame, "総アイテム数", str(total_items),  COLORS["primary"])
        self._make_card(self.card_frame, "貸出中",       str(total_loans),  COLORS["warning"])
        self._make_card(self.card_frame, "延滞",         str(total_overdue),COLORS["danger"])
        self._make_card(self.card_frame, "利用者数",     str(total_members),COLORS["success"])

        # 台帳別テーブル
        for item in self.table.get_children():
            self.table.delete(item)
        for prof, dm, lm in zip(
            self.prof_mgr.profiles, data_mgrs, loan_mgrs
        ):
            lending = len(lm.get_active_loans())
            overdue = len(lm.get_overdue_loans())
            stock   = sum(
                1 for r in dm.records
                if r.get("_qty_available", r.get("_qty_total", 1)) > 0
            )
            tags = ("has_overdue",) if overdue > 0 else ()
            self.table.insert("", "end", values=(
                prof.name, len(dm.records), lending, overdue, stock
            ), tags=tags)

        # 延滞アラート一覧
        for item in self.alert_tree.get_children():
            self.alert_tree.delete(item)
        for prof, lm in zip(self.prof_mgr.profiles, loan_mgrs):
            for loan in lm.get_overdue_loans():
                member = self.member_mgr.find_by_id(loan.member_id)
                m_name = member.name if member else loan.member_id
                self.alert_tree.insert("", "end", values=(
                    prof.name, loan.barcode_id, m_name,
                    loan.due_date, f"{loan.days_overdue} 日",
                ), tags=("overdue_row",))


# ==============================================================================
# STEP 19 — InventoryDialog（棚卸モード）
# ==============================================================================

class InventoryDialog:
    """棚卸モード（S3）。全アイテムをスキャンして未スキャン品を抽出する。"""

    def __init__(self, parent, data_mgr: "DataManager") -> None:
        self.data_mgr = data_mgr
        self.scanned: set = set()

        self.dlg = _make_modal_dialog(parent, "棚卸モード", "820x600")
        self._build_ui()

    def _build_ui(self) -> None:
        # ヘッダー
        hdr = tk.Frame(self.dlg, bg=COLORS["warning"], height=50)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="  棚卸モード実行中",
                 font=FONTS["h3"],
                 bg=COLORS["warning"], fg="white").pack(side="left", padx=14)
        self.cnt_var = tk.StringVar(value="スキャン: 0 件")
        tk.Label(hdr, textvariable=self.cnt_var,
                 font=FONTS["body_lg"],
                 bg=COLORS["warning"], fg="white").pack(side="right", padx=14)

        # スキャン入力
        sf = tk.Frame(self.dlg, bg=COLORS["bg"]); sf.pack(fill="x", padx=12, pady=8)
        self.scan_var   = tk.StringVar()
        self.scan_entry = ttk.Entry(sf, textvariable=self.scan_var,
                                    font=FONTS["scan_large"], width=22)
        self.scan_entry.pack(side="left", padx=4)
        self.scan_entry.bind("<Return>", self._on_scan)
        self.scan_entry.focus_set()
        ttk.Button(sf, text="スキャン", command=self._on_scan).pack(side="left", padx=4)
        self.result_var = tk.StringVar()
        tk.Label(sf, textvariable=self.result_var, bg=COLORS["bg"],
                 font=FONTS["body"]).pack(side="left", padx=10)

        # 結果テーブル
        rf = ttk.Frame(self.dlg); rf.pack(fill="both", expand=True, padx=12, pady=4)
        self.result_tree, _ = _make_treeview(rf, [
            ("barcode_id", "バーコードID", 160),
            ("status", "ステータス", 110),
            ("info", "情報", 380),
        ], height=14)
        self.result_tree.tag_configure("missing", background=COLORS["overdue_bg"])

        # ボタン行
        bf = ttk.Frame(self.dlg); bf.pack(fill="x", padx=12, pady=8)
        ttk.Button(bf, text="棚卸完了・未スキャン抽出",
                   command=self._finish).pack(side="left", padx=4)
        ttk.Button(bf, text="CSV エクスポート",
                   command=self._export_csv).pack(side="left", padx=4)
        ttk.Button(bf, text="閉じる",
                   command=self.dlg.destroy).pack(side="right", padx=4)

    def _on_scan(self, _event=None) -> None:
        val = self.scan_var.get().strip()
        if not val:
            return
        hits = self.data_mgr.find_by_barcode(val)
        if hits:
            for _, rec in hits:
                bid = rec.get("_barcode_id", "")
                self.scanned.add(bid)
                rec["_last_scanned_at"] = datetime.datetime.now().isoformat()
            self.cnt_var.set(f"スキャン: {len(self.scanned)} 件")
            self.result_var.config(fg=COLORS["success"]) if hasattr(
                self.result_var, "config") else None
            self.result_var.set(f"✅ {val}  登録済み")
        else:
            self.result_var.set(f"❌ {val}  未登録")
        self.scan_var.set("")
        self.scan_entry.focus_set()

    def _finish(self) -> None:
        missing = [
            rec for rec in self.data_mgr.records
            if rec.get("_barcode_id", "") not in self.scanned
        ]
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        for rec in missing:
            info_cols = self.data_mgr.csv_columns[:3]
            info = " / ".join(str(rec.get(c, "")) for c in info_cols)
            self.result_tree.insert("", "end", values=(
                rec.get("_barcode_id", ""),
                rec.get("_status", ""),
                info,
            ), tags=("missing",))
        self.data_mgr.add_history(
            "棚卸",
            f"スキャン:{len(self.scanned)} / 未スキャン:{len(missing)} / "
            f"総数:{len(self.data_mgr.records)}",
        )
        self.data_mgr.save()
        messagebox.showinfo(
            "棚卸完了",
            f"総数: {len(self.data_mgr.records)} 件\n"
            f"スキャン済み: {len(self.scanned)} 件\n"
            f"未スキャン（行方不明候補）: {len(missing)} 件",
            parent=self.dlg,
        )

    def _export_csv(self) -> None:
        rows = [
            list(self.result_tree.item(i, "values"))
            for i in self.result_tree.get_children()
        ]
        if not rows:
            messagebox.showinfo("情報", "未スキャンアイテムはありません。",
                                parent=self.dlg); return
        fp = filedialog.asksaveasfilename(
            parent=self.dlg, defaultextension=".csv",
            initialfile=f"inventory_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
            filetypes=[("CSV", "*.csv")]
        )
        if fp:
            with open(fp, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["バーコードID", "ステータス", "情報"])
                w.writerows(rows)
            messagebox.showinfo("完了", f"エクスポート完了:\n{fp}", parent=self.dlg)


# ==============================================================================
# STEP 22 — MonthlyReportDialog（月次 PDF レポート）
# ==============================================================================

class MonthlyReportDialog:
    """月次 PDF レポート出力 (B8)。Pillow のみで multipage PDF を生成。"""

    A4_W_MM = A4_WIDTH_MM
    A4_H_MM = A4_HEIGHT_MM
    DPI     = REPORT_DPI
    MARGIN  = REPORT_MARGIN_MM

    def __init__(self, parent, data_mgr: "DataManager",
                 loan_mgr: LoanManager,
                 member_mgr: Optional[MemberManager],
                 profile_name: str) -> None:
        self.data_mgr    = data_mgr
        self.loan_mgr    = loan_mgr
        self.member_mgr  = member_mgr
        self.profile_name = profile_name

        self.dlg = _make_modal_dialog(parent, "月次レポート出力", "440x240", resizable=False)
        self._build_ui()

    def _build_ui(self) -> None:
        tk.Label(self.dlg, text=f"月次レポート — {self.profile_name}",
                 font=FONTS["h4"]).pack(pady=14)
        frm = ttk.Frame(self.dlg); frm.pack(padx=20, pady=6)
        now = datetime.date.today()
        tk.Label(frm, text="対象年月:").grid(row=0, column=0, sticky="e", padx=6)
        self.year_var  = tk.IntVar(value=now.year)
        self.month_var = tk.IntVar(value=now.month)
        ttk.Spinbox(frm, from_=2000, to=2099,
                    textvariable=self.year_var,  width=7).grid(row=0, column=1)
        tk.Label(frm, text="年").grid(row=0, column=2)
        ttk.Spinbox(frm, from_=1, to=12,
                    textvariable=self.month_var, width=4).grid(row=0, column=3)
        tk.Label(frm, text="月").grid(row=0, column=4)
        bf = ttk.Frame(self.dlg); bf.pack(pady=14)
        ttk.Button(bf, text="PDF 生成",
                   command=self._generate).pack(side="left", padx=8)
        ttk.Button(bf, text="閉じる",
                   command=self.dlg.destroy).pack(side="left", padx=8)

    def _generate(self) -> None:
        if not HAS_PIL:
            messagebox.showerror("エラー", "Pillow が必要です。",
                                 parent=self.dlg); return
        year  = self.year_var.get()
        month = self.month_var.get()
        fp = filedialog.asksaveasfilename(
            parent=self.dlg, title="レポート PDF 保存",
            defaultextension=".pdf",
            initialfile=f"report_{year}{month:02d}_{self.profile_name}.pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not fp:
            return
        try:
            pages = self._build_pages(year, month)
            if not pages:
                messagebox.showinfo("情報", "該当データがありません。",
                                    parent=self.dlg); return
            pages[0].save(fp, "PDF", save_all=True,
                          append_images=pages[1:], resolution=self.DPI)
            messagebox.showinfo("完了", f"レポート生成完了:\n{fp}", parent=self.dlg)
        except Exception as e:
            messagebox.showerror("エラー", str(e), parent=self.dlg)

    def _mm(self, mm: float) -> int:
        return int(mm * self.DPI / 25.4)

    def _build_pages(self, year: int, month: int) -> List["Image.Image"]:
        """Pillow で A4 複数ページ PDF を組み立てる。"""
        pgw   = self._mm(self.A4_W_MM)
        pgh   = self._mm(self.A4_H_MM)
        mg    = self._mm(self.MARGIN)
        lh    = self._mm(7)
        fnt_t = _get_japanese_font(self._mm(6))
        fnt_h = _get_japanese_font(self._mm(4.5))
        fnt_b = _get_japanese_font(self._mm(3.5))

        month_str  = f"{year}-{month:02d}"
        month_loans = [
            l for l in self.loan_mgr.loans
            if l.loaned_at.startswith(month_str)
            or (l.returned_at and l.returned_at.startswith(month_str))
        ]

        def new_page():
            p = Image.new("RGB", (pgw, pgh), "white")
            return p, ImageDraw.Draw(p)

        pages: List["Image.Image"] = []
        pages.append(self._build_summary_page(new_page, pgw, mg, lh,
                                               fnt_t, fnt_h, fnt_b,
                                               year, month, month_loans))
        if month_loans:
            pages.extend(self._build_loan_pages(new_page, pgh, mg, lh,
                                                 fnt_h, fnt_b,
                                                 year, month, month_loans))
        return pages

    def _build_summary_page(self, new_page, pgw, mg, lh,
                             fnt_t, fnt_h, fnt_b,
                             year, month, month_loans) -> "Image.Image":
        p, d = new_page()
        y = mg
        d.text((mg, y), f"{self.profile_name}  {year}年{month}月 月次レポート",
               fill="black", font=fnt_t)
        y += self._mm(10)
        d.line([(mg, y), (pgw - mg, y)], fill=COLORS["primary"], width=3)
        y += self._mm(6)
        for lbl, val in [
            ("総アイテム数",                str(len(self.data_mgr.records))),
            ("現在の貸出中",                str(len(self.loan_mgr.get_active_loans()))),
            ("延滞件数",                    str(len(self.loan_mgr.get_overdue_loans()))),
            (f"{month}月の貸出件数",        str(len(month_loans))),
        ]:
            d.text((mg, y), f"{lbl}: {val}", fill="black", font=fnt_h)
            y += lh
        y += self._mm(6)
        d.text((mg, y), "ステータス別集計", fill=COLORS["primary"], font=fnt_h)
        y += lh
        for sv in self.data_mgr.template.status_values:
            cnt = sum(1 for r in self.data_mgr.records if r.get("_status") == sv)
            d.text((mg + self._mm(6), y), f"{sv}: {cnt} 件",
                   fill="black", font=fnt_b)
            y += lh
        return p

    def _build_loan_pages(self, new_page, pgh, mg, lh,
                           fnt_h, fnt_b,
                           year, month, month_loans) -> List["Image.Image"]:
        pages: List["Image.Image"] = []
        p, d = new_page()
        y = mg
        d.text((mg, y), f"{year}年{month}月 貸出一覧", fill="black", font=fnt_h)
        y += lh * 2
        for loan in month_loans:
            if y + lh > pgh - mg:
                pages.append(p)
                p, d = new_page()
                y = mg
            member = (self.member_mgr.find_by_id(loan.member_id)
                      if self.member_mgr else None)
            m_name = member.name if member else loan.member_id[:12]
            if loan.returned_at:
                status = "返却済"
            elif loan.is_overdue:
                status = "延滞"
            else:
                status = "貸出中"
            color = COLORS["danger"] if loan.is_overdue and not loan.returned_at else "black"
            line = (f"  {loan.loaned_at[:10]}  "
                    f"ID:{loan.barcode_id:<16}  "
                    f"{m_name:<12}  {status}")
            d.text((mg, y), line, fill=color, font=fnt_b)
            y += lh
        pages.append(p)
        return pages


# ==============================================================================
# STEP 7 — LabelPrintDialog（印刷設定永続化付き）
# ==============================================================================

PAPER_SIZES = {
    "A4": (210, 297), "A4 横": (297, 210),
    "Letter": (215.9, 279.4), "B5": (176, 250), "はがき": (100, 148),
}

LABEL_PRESETS = {
    "A-one 72224 (24面)": {
        "paper_size":"A4","margin_top":13.0,"margin_bottom":13.0,
        "margin_left":8.0,"margin_right":8.0,
        "label_width":64.0,"label_height":33.9,
        "spacing_h":2.0,"spacing_v":0.0,"cols":3,"rows":8,
    },
    "A-one 72312 (12面)": {
        "paper_size":"A4","margin_top":13.5,"margin_bottom":13.5,
        "margin_left":9.0,"margin_right":9.0,
        "label_width":86.4,"label_height":42.3,
        "spacing_h":2.5,"spacing_v":0.0,"cols":2,"rows":6,
    },
    "A4 標準 (10面)": {
        "paper_size":"A4","margin_top":15.0,"margin_bottom":15.0,
        "margin_left":15.0,"margin_right":15.0,
        "label_width":85.0,"label_height":50.0,
        "spacing_h":5.0,"spacing_v":3.4,"cols":2,"rows":5,
    },
    "カスタム": {},
}


class LabelPrintDialog:
    """バーコードラベル印刷ダイアログ（設定は DataManager.print_settings に保存）。"""

    def __init__(self, parent, records: list, data_mgr: DataManager) -> None:
        self.parent   = parent
        self.records  = records
        self.data_mgr = data_mgr

        # 項目別印刷モード
        self.field_print_modes: Dict[str, str] = {}
        for col in data_mgr.csv_columns:
            if col == data_mgr.barcode_column:
                self.field_print_modes[col] = "barcode"
            else:
                self.field_print_modes[col] = "none"

        self.current_page = 0
        self.total_pages  = 1

        self.dlg = _make_modal_dialog(parent, "バーコードラベル印刷", "1050x750")
        self.dlg.minsize(900, 650)

        self._build_ui()
        self._restore_settings()
        self._update_preview()

    # ---------------------------------------------------------------- UI構築

    def _build_ui(self) -> None:
        main_pw = ttk.PanedWindow(self.dlg, orient="horizontal")
        main_pw.pack(fill="both", expand=True, padx=5, pady=5)

        # 左: 設定タブ
        left_nb = ttk.Notebook(main_pw)
        main_pw.add(left_nb, weight=2)

        layout_outer = ttk.Frame(left_nb)
        left_nb.add(layout_outer, text="レイアウト")
        _, self._layout_frame = _make_scrollable_frame(layout_outer)
        self._build_layout_panel(self._layout_frame)

        content_outer = ttk.Frame(left_nb)
        left_nb.add(content_outer, text="印刷内容")
        self._build_content_panel(content_outer)

        # 右: プレビュー
        rf = ttk.Frame(main_pw)
        main_pw.add(rf, weight=3)
        ttk.Label(rf, text="プレビュー", font=FONTS["h5"]).pack(
            anchor="w", padx=5, pady=(5, 0))
        self.preview_canvas = tk.Canvas(rf, bg="white",
                                        highlightthickness=1,
                                        highlightbackground=COLORS["border"])
        self.preview_canvas.pack(fill="both", expand=True, padx=5, pady=5)
        self.preview_canvas.bind("<Configure>", lambda e: self._update_preview())

        nav = ttk.Frame(rf)
        nav.pack(fill="x", padx=5, pady=2)
        ttk.Button(nav, text="< 前", command=self._prev_page).pack(side="left")
        self.page_label = ttk.Label(nav, text="1 / 1")
        self.page_label.pack(side="left", padx=15)
        ttk.Button(nav, text="次 >", command=self._next_page).pack(side="left")
        ttk.Label(nav, text=f"対象: {len(self.records)} 件").pack(side="right")

        # 下部ボタン
        bf = ttk.Frame(self.dlg)
        bf.pack(fill="x", padx=10, pady=8)
        ttk.Button(bf, text="プレビュー更新",command=self._update_preview).pack(side="left", padx=3)
        ttk.Button(bf, text="PDF 保存",      command=self._save_pdf).pack(side="left", padx=3)
        ttk.Button(bf, text="印刷",           command=self._print_labels).pack(side="left", padx=3)
        ttk.Button(bf, text="閉じる",         command=self.dlg.destroy).pack(side="right", padx=3)

    def _build_layout_panel(self, parent) -> None:
        row = 0
        row = self._build_preset_section(parent, row)
        row = self._build_paper_and_margins(parent, row)
        row = self._build_label_grid_section(parent, row)
        row = self._build_start_and_options(parent, row)
        self._apply_preset("A4 標準 (10面)")

    def _build_preset_section(self, parent, row: int) -> int:
        ttk.Label(parent, text="プリセット:", font=FONTS["section"]).grid(
            row=row, column=0, sticky="e", padx=5, pady=3)
        self.preset_var = tk.StringVar(value="A4 標準 (10面)")
        combo = ttk.Combobox(parent, textvariable=self.preset_var,
                             values=list(LABEL_PRESETS.keys()), state="readonly", width=22)
        combo.grid(row=row, column=1, sticky="w", padx=5, pady=3)
        combo.bind("<<ComboboxSelected>>", self._on_preset_change)
        row += 1
        self.preset_info = ttk.Label(parent, text="", font=FONTS["small"],
                                     foreground=COLORS["muted"], wraplength=300)
        self.preset_info.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 3))
        row += 1
        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=5); row += 1
        return row

    def _build_paper_and_margins(self, parent, row: int) -> int:
        ttk.Label(parent, text="用紙サイズ:").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.paper_var = tk.StringVar(value="A4")
        ttk.Combobox(parent, textvariable=self.paper_var, values=list(PAPER_SIZES.keys()),
                     state="readonly", width=15).grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        ttk.Label(parent, text="余白 (mm)", font=FONTS["label_bold"]).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(8, 2)); row += 1
        mf = ttk.Frame(parent); mf.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5)
        self.margin_top_var    = tk.DoubleVar(value=15.0)
        self.margin_bottom_var = tk.DoubleVar(value=15.0)
        self.margin_left_var   = tk.DoubleVar(value=15.0)
        self.margin_right_var  = tk.DoubleVar(value=15.0)
        for i, (lb, vr) in enumerate([
            ("上:", self.margin_top_var), ("下:", self.margin_bottom_var),
            ("左:", self.margin_left_var), ("右:", self.margin_right_var),
        ]):
            ttk.Label(mf, text=lb).grid(row=i//2, column=(i%2)*2, sticky="e", padx=2)
            ttk.Entry(mf, textvariable=vr, width=7).grid(
                row=i//2, column=(i%2)*2+1, sticky="w", padx=2, pady=1)
        row += 1
        return row

    def _build_label_grid_section(self, parent, row: int) -> int:
        ttk.Label(parent, text="ラベルサイズ (mm)", font=FONTS["label_bold"]).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(8, 2)); row += 1
        sf = ttk.Frame(parent); sf.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5)
        self.label_w_var = tk.DoubleVar(value=85.0)
        self.label_h_var = tk.DoubleVar(value=50.0)
        ttk.Label(sf, text="幅:").grid(row=0, column=0, sticky="e", padx=2)
        ttk.Entry(sf, textvariable=self.label_w_var, width=7).grid(row=0, column=1, padx=2)
        ttk.Label(sf, text="高さ:").grid(row=0, column=2, sticky="e", padx=2)
        ttk.Entry(sf, textvariable=self.label_h_var, width=7).grid(row=0, column=3, padx=2)
        row += 1
        ttk.Label(parent, text="配列", font=FONTS["label_bold"]).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(8, 2)); row += 1
        gf = ttk.Frame(parent); gf.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5)
        self.cols_var = tk.IntVar(value=2)
        self.rows_var = tk.IntVar(value=5)
        ttk.Label(gf, text="列数:").grid(row=0, column=0, sticky="e", padx=2)
        ttk.Spinbox(gf, from_=1, to=10, textvariable=self.cols_var, width=5).grid(row=0, column=1, padx=2)
        ttk.Label(gf, text="行数:").grid(row=0, column=2, sticky="e", padx=2)
        ttk.Spinbox(gf, from_=1, to=20, textvariable=self.rows_var, width=5).grid(row=0, column=3, padx=2)
        row += 1
        ttk.Label(parent, text="間隔 (mm)", font=FONTS["label_bold"]).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(8, 2)); row += 1
        spf = ttk.Frame(parent); spf.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5)
        self.spacing_h_var = tk.DoubleVar(value=5.0)
        self.spacing_v_var = tk.DoubleVar(value=3.4)
        ttk.Label(spf, text="水平:").grid(row=0, column=0, sticky="e", padx=2)
        ttk.Entry(spf, textvariable=self.spacing_h_var, width=7).grid(row=0, column=1, padx=2)
        ttk.Label(spf, text="垂直:").grid(row=0, column=2, sticky="e", padx=2)
        ttk.Entry(spf, textvariable=self.spacing_v_var, width=7).grid(row=0, column=3, padx=2)
        row += 1
        return row

    def _build_start_and_options(self, parent, row: int) -> int:
        ttk.Label(parent, text="開始位置", font=FONTS["label_bold"]).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(8, 2)); row += 1
        stf = ttk.Frame(parent); stf.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5)
        self.start_pos_var = tk.IntVar(value=1)
        ttk.Label(stf, text="位置:").pack(side="left", padx=2)
        self.start_spin = ttk.Spinbox(stf, from_=1, to=100,
                                      textvariable=self.start_pos_var, width=5)
        self.start_spin.pack(side="left", padx=2)
        ttk.Label(stf, text="(1=左上)").pack(side="left", padx=2)
        row += 1
        self.start_grid_canvas = tk.Canvas(parent, width=200, height=120, bg="white",
                                           highlightthickness=1,
                                           highlightbackground=COLORS["border"])
        self.start_grid_canvas.grid(row=row, column=0, columnspan=2, padx=5, pady=5)
        self.start_grid_canvas.bind("<Button-1>", self._on_start_grid_click)
        row += 1
        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=5); row += 1
        self.show_text_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="バーコード下に ID 値を表示",
                        variable=self.show_text_var).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=1)
        return row + 1
        self._update_preset_info()

    def _build_content_panel(self, parent) -> None:
        ttk.Label(parent, text="各項目の印刷方法を選択",
                  font=FONTS["section"]).pack(anchor="w", padx=10, pady=(10, 3))

        ctrl = ttk.Frame(parent)
        ctrl.pack(fill="x", padx=10, pady=(0, 5))
        ttk.Button(ctrl, text="すべてバーコード", width=14,
                   command=lambda: self._set_all_modes("barcode")).pack(side="left", padx=2)
        ttk.Button(ctrl, text="すべてテキスト", width=14,
                   command=lambda: self._set_all_modes("text")).pack(side="left", padx=2)
        ttk.Button(ctrl, text="すべて非表示", width=12,
                   command=lambda: self._set_all_modes("none")).pack(side="left", padx=2)
        ttk.Button(ctrl, text="デフォルトに戻す", width=14,
                   command=self._reset_modes).pack(side="right", padx=2)

        outer = ttk.Frame(parent)
        outer.pack(fill="both", expand=True, padx=5, pady=3)
        _, self._content_inner = _make_scrollable_frame(outer)
        self.mode_vars: Dict[str, tk.StringVar] = {}
        self._rebuild_content_rows()

    def _rebuild_content_rows(self) -> None:
        inner = self._content_inner
        for w in inner.winfo_children():
            w.destroy()
        ttk.Label(inner, text="カラム名", font=FONTS["label_bold"],
                  width=20).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        for ci, (label, val) in enumerate([("バーコード","barcode"),("テキスト","text"),("非表示","none")]):
            fg = COLORS["primary_light"] if val=="barcode" else (COLORS["success"] if val=="text" else COLORS["muted"])
            ttk.Label(inner, text=label, font=FONTS["label_bold"],
                      foreground=fg).grid(row=0, column=ci+1, padx=8, pady=2)
        ttk.Separator(inner, orient="horizontal").grid(
            row=1, column=0, columnspan=4, sticky="ew", pady=2)

        self.mode_vars = {}
        for i, col in enumerate(self.data_mgr.csv_columns):
            r  = i + 2
            dn = self.data_mgr.get_column_display_name(col)
            bg = COLORS["bg"] if i % 2 == 0 else COLORS["card"]
            rf = tk.Frame(inner, bg=bg)
            rf.grid(row=r, column=0, columnspan=4, sticky="ew")
            inner.grid_columnconfigure(0, weight=1)
            tk.Label(rf, text=dn, width=20, anchor="w", bg=bg,
                     font=FONTS["caption"]).grid(row=0, column=0, sticky="w", padx=5, pady=3)
            var = tk.StringVar(value=self.field_print_modes.get(col, "none"))
            self.mode_vars[col] = var
            for ci, (label, val, color) in enumerate([
                ("バーコード","barcode",COLORS["primary_light"]),
                ("テキスト","text",COLORS["success"]),
                ("非表示","none",COLORS["slate"]),
            ]):
                sel = (var.get() == val)
                tk.Button(
                    rf, text=label, width=8, font=FONTS["small"],
                    relief="sunken" if sel else "raised",
                    bg=color if sel else COLORS["border"],
                    fg="white" if sel else COLORS["text"],
                    activebackground=color,
                    command=lambda c=col, v=val: self._set_mode(c, v),
                ).grid(row=0, column=ci+1, padx=4, pady=3)

    def _set_mode(self, col: str, value: str) -> None:
        self.field_print_modes[col] = value
        if col in self.mode_vars:
            self.mode_vars[col].set(value)
        self._rebuild_content_rows()

    def _set_all_modes(self, value: str) -> None:
        for col in self.data_mgr.csv_columns:
            self.field_print_modes[col] = value
        self._rebuild_content_rows()

    def _reset_modes(self) -> None:
        for col in self.data_mgr.csv_columns:
            self.field_print_modes[col] = (
                "barcode" if col == self.data_mgr.barcode_column else "none"
            )
        self._rebuild_content_rows()

    # ---------------------------------------------------------------- 設定保存・復元

    def _restore_settings(self) -> None:
        ps = self.data_mgr.print_settings
        if not ps:
            return
        try:
            if "preset" in ps:
                self.preset_var.set(ps["preset"])
                self._apply_preset(ps["preset"])
            for attr, key in [
                ("paper_var",       "paper_size"),
                ("margin_top_var",  "margin_top"),
                ("margin_bottom_var","margin_bottom"),
                ("margin_left_var", "margin_left"),
                ("margin_right_var","margin_right"),
                ("label_w_var",     "label_width"),
                ("label_h_var",     "label_height"),
                ("spacing_h_var",   "spacing_h"),
                ("spacing_v_var",   "spacing_v"),
                ("cols_var",        "cols"),
                ("rows_var",        "rows"),
                ("start_pos_var",   "start_position"),
                ("show_text_var",   "show_text"),
            ]:
                if key in ps:
                    getattr(self, attr).set(ps[key])
            if "field_modes" in ps:
                self.field_print_modes.update(ps["field_modes"])
                self._rebuild_content_rows()
        except Exception as e:
            logger.warning("印刷設定復元エラー: %s", e)

    def _persist_settings(self) -> None:
        cfg = self._get_config()
        self.data_mgr.print_settings = {
            "preset":        self.preset_var.get(),
            "paper_size":    cfg["paper_size"],
            "margin_top":    cfg["margin_top"],
            "margin_bottom": cfg["margin_bottom"],
            "margin_left":   cfg["margin_left"],
            "margin_right":  cfg["margin_right"],
            "label_width":   cfg["label_width"],
            "label_height":  cfg["label_height"],
            "spacing_h":     cfg["spacing_h"],
            "spacing_v":     cfg["spacing_v"],
            "cols":          cfg["cols"],
            "rows":          cfg["rows"],
            "start_position":cfg["start_position"],
            "show_text":     cfg["show_text"],
            "field_modes":   dict(self.field_print_modes),
        }
        try:
            self.data_mgr.save()
        except Exception as e:
            logger.error("印刷設定保存エラー: %s", e)

    # ---------------------------------------------------------------- プリセット

    def _on_preset_change(self, _event=None) -> None:
        self._apply_preset(self.preset_var.get())
        self._update_preset_info()
        self._update_preview()

    def _update_preset_info(self) -> None:
        name = self.preset_var.get()
        p    = LABEL_PRESETS.get(name, {})
        if not p:
            self.preset_info.config(text="カスタム設定: 各項目を手動で入力してください")
            return
        ps   = p.get("paper_size", "A4")
        pw, ph = PAPER_SIZES.get(ps, (210, 297))
        info = (f"用紙: {ps} ({pw}×{ph}mm) | "
                f"ラベル: {p['label_width']}×{p['label_height']}mm | "
                f"{p['cols']}列×{p['rows']}行={p['cols']*p['rows']}面")
        self.preset_info.config(text=info)

    def _apply_preset(self, name: str) -> None:
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

    # ---------------------------------------------------------------- 設定取得

    def _get_config(self) -> dict:
        for col, var in self.mode_vars.items():
            self.field_print_modes[col] = var.get()
        return {
            "paper_size":    self.paper_var.get(),
            "margin_top":    self.margin_top_var.get(),
            "margin_bottom": self.margin_bottom_var.get(),
            "margin_left":   self.margin_left_var.get(),
            "margin_right":  self.margin_right_var.get(),
            "label_width":   self.label_w_var.get(),
            "label_height":  self.label_h_var.get(),
            "spacing_h":     self.spacing_h_var.get(),
            "spacing_v":     self.spacing_v_var.get(),
            "cols":          self.cols_var.get(),
            "rows":          self.rows_var.get(),
            "start_position":self.start_pos_var.get(),
            "show_text":     self.show_text_var.get(),
            "field_modes":   dict(self.field_print_modes),
            "dpi":           300,
        }

    # ---------------------------------------------------------------- グリッド

    def _on_start_grid_click(self, event) -> None:
        cfg  = self._get_config()
        cols, rows = cfg["cols"], cfg["rows"]
        cw = self.start_grid_canvas.winfo_width()
        ch = self.start_grid_canvas.winfo_height()
        if cols == 0 or rows == 0 or cw < 10 or ch < 10:
            return
        col = max(0, min(int(event.x / (cw / cols)), cols - 1))
        row = max(0, min(int(event.y / (ch / rows)), rows - 1))
        self.start_pos_var.set(row * cols + col + 1)
        self._draw_start_grid()

    def _draw_start_grid(self) -> None:
        c = self.start_grid_canvas
        c.delete("all")
        cfg  = self._get_config()
        cols, rows, start = cfg["cols"], cfg["rows"], cfg["start_position"]
        cw = c.winfo_width(); ch = c.winfo_height()
        if cols == 0 or rows == 0 or cw < 10 or ch < 10:
            return
        cw_c = cw / cols; ch_c = ch / rows
        for r in range(rows):
            for col in range(cols):
                x1, y1 = col*cw_c+1, r*ch_c+1
                x2, y2 = (col+1)*cw_c-1, (r+1)*ch_c-1
                pos    = r * cols + col + 1
                fill   = COLORS["primary_light"] if pos == start else (COLORS["primary_lighter"] if pos > start else COLORS["bg_alt"])
                tc     = "white"   if pos == start else COLORS["muted"]
                c.create_rectangle(x1, y1, x2, y2, fill=fill, outline=COLORS["slate"])
                c.create_text((x1+x2)/2, (y1+y2)/2, text=str(pos), fill=tc,
                              font=FONTS["small"])

    # ---------------------------------------------------------------- プレビュー

    def _update_preview(self) -> None:
        self.preview_canvas.delete("all")
        self._preview_photo = None
        cfg = self._get_config()
        cw  = self.preview_canvas.winfo_width()
        ch  = self.preview_canvas.winfo_height()
        if cw < 50 or ch < 50:
            return

        if not HAS_PIL or not self.records:
            self._draw_layout_preview(cfg, cw, ch)
            return

        errs = self._check_overflow()
        if errs:
            self._draw_layout_preview(cfg, cw, ch)
            self.preview_canvas.create_rectangle(
                cw*0.1, ch*0.3, cw*0.9, ch*0.7, fill=COLORS["danger_lighter"], outline=COLORS["danger"], width=2)
            self.preview_canvas.create_text(
                cw/2, ch*0.42, text="⚠ ラベルサイズ超過",
                fill=COLORS["danger"], font=FONTS["h5"])
            self.preview_canvas.create_text(
                cw/2, ch*0.55, text="\n".join(errs),
                fill=COLORS["danger_dark"], font=FONTS["caption"], width=cw*0.7)
            return

        try:
            pages = self._generate_pages()
        except Exception as e:
            logger.warning("プレビュー生成エラー: %s", e)
            self._draw_layout_preview(cfg, cw, ch)
            return

        if not pages:
            self._draw_layout_preview(cfg, cw, ch)
            return

        self.total_pages  = len(pages)
        self.current_page = min(self.current_page, self.total_pages - 1)
        self.page_label.configure(text=f"{self.current_page+1} / {self.total_pages}")

        pg = pages[self.current_page]
        margin  = PREVIEW_MARGIN_PX
        scale   = min((cw - margin*2) / pg.width, (ch - margin*2) / pg.height)
        new_w   = max(1, int(pg.width  * scale))
        new_h   = max(1, int(pg.height * scale))
        resized = pg.resize((new_w, new_h), Image.LANCZOS)
        ox = (cw - new_w) // 2
        oy = (ch - new_h) // 2
        self.preview_canvas.create_rectangle(
            ox+3, oy+3, ox+new_w+3, oy+new_h+3, fill=COLORS["shadow"], outline="")
        self._preview_photo = ImageTk.PhotoImage(resized)
        self.preview_canvas.create_image(ox, oy, anchor="nw", image=self._preview_photo)
        self.preview_canvas.create_rectangle(
            ox, oy, ox+new_w, oy+new_h, outline=COLORS["slate"], width=1)
        self._draw_size_info(cfg, cw, ch)
        self._draw_start_grid()

    def _draw_layout_preview(self, cfg, cw, ch) -> None:
        pw, ph  = PAPER_SIZES.get(cfg["paper_size"], (210, 297))
        margin  = 20
        scale   = min((cw - margin*2) / pw, (ch - margin*2) / ph)
        spw, sph = pw*scale, ph*scale
        ox, oy  = (cw - spw)/2, (ch - sph)/2
        c = self.preview_canvas
        c.create_rectangle(ox+3, oy+3, ox+spw+3, oy+sph+3, fill=COLORS["shadow"], outline="")
        c.create_rectangle(ox, oy, ox+spw, oy+sph, fill="white", outline=COLORS["slate"])
        ml  = cfg["margin_left"]*scale; mr = cfg["margin_right"]*scale
        mt  = cfg["margin_top"]*scale;  mb = cfg["margin_bottom"]*scale
        for args in [
            (ox+ml, oy, ox+ml, oy+sph),(ox+spw-mr, oy, ox+spw-mr, oy+sph),
            (ox, oy+mt, ox+spw, oy+mt),(ox, oy+sph-mb, ox+spw, oy+sph-mb),
        ]:
            c.create_line(*args, fill=COLORS["accent_light"], dash=(3,3))
        cols, rows  = cfg["cols"], cfg["rows"]
        lw, lh      = cfg["label_width"]*scale, cfg["label_height"]*scale
        sh, sv      = cfg["spacing_h"]*scale,   cfg["spacing_v"]*scale
        for r in range(rows):
            for col in range(cols):
                x = ox + ml + col*(lw+sh)
                y = oy + mt + r*(lh+sv)
                c.create_rectangle(x, y, x+lw, y+lh, fill=COLORS["bg"],
                                   outline=COLORS["border"], dash=(2,2))
        c.create_text(cw/2, ch/2, text="データなし", fill=COLORS["slate"],
                      font=FONTS["h3_normal"])
        self.total_pages  = 1
        self.current_page = 0
        self.page_label.configure(text="1 / 1")
        self._draw_size_info(cfg, cw, ch)
        self._draw_start_grid()

    def _draw_size_info(self, cfg, cw, ch) -> None:
        pw, ph = PAPER_SIZES.get(cfg["paper_size"], (210, 297))
        info1 = (f"用紙: {cfg['paper_size']} ({pw}×{ph}mm)  |  "
                 f"ラベル: {cfg['label_width']}×{cfg['label_height']}mm  "
                 f"{cfg['cols']}列×{cfg['rows']}行={cfg['cols']*cfg['rows']}面")
        info2 = (f"余白: 上{cfg['margin_top']} 下{cfg['margin_bottom']} "
                 f"左{cfg['margin_left']} 右{cfg['margin_right']}mm  |  "
                 f"間隔: 水平{cfg['spacing_h']} 垂直{cfg['spacing_v']}mm")
        c = self.preview_canvas
        c.create_rectangle(0, ch-INFO_BAR_HEIGHT_PX, cw, ch, fill=COLORS["text"], outline="")
        c.create_text(cw/2, ch-INFO_BAR_HEIGHT_PX+11, text=info1, fill=COLORS["border"],
                      font=FONTS["small"], anchor="center")
        c.create_text(cw/2, ch-INFO_BAR_HEIGHT_PX+25, text=info2, fill=COLORS["slate"],
                      font=FONTS["tiny"], anchor="center")

    def _prev_page(self) -> None:
        if self.current_page > 0:
            self.current_page -= 1; self._update_preview()

    def _next_page(self) -> None:
        if self.current_page < self.total_pages - 1:
            self.current_page += 1; self._update_preview()

    # ---------------------------------------------------------------- チェック

    def _check_overflow(self) -> List[str]:
        cfg = self._get_config()
        def mm2px(mm): return int(mm * cfg["dpi"] / 25.4)
        lh        = mm2px(cfg["label_height"])
        bc_fields = [c for c in self.data_mgr.csv_columns
                     if cfg["field_modes"].get(c) == "barcode"]
        tx_fields = [c for c in self.data_mgr.csv_columns
                     if cfg["field_modes"].get(c) == "text"]
        bc_margin   = mm2px(2)
        text_line_h = mm2px(3.5)
        available_h = lh - bc_margin*2 - len(tx_fields)*text_line_h
        min_bc_h    = mm2px(8)
        errs = []
        if available_h < 0:
            errs.append(f"テキスト項目 ({len(tx_fields)} 個) だけでラベル高さを超えます。")
        elif bc_fields and available_h < len(bc_fields)*min_bc_h:
            max_bc = max(0, available_h // min_bc_h) if min_bc_h else 0
            errs.append(
                f"バーコード {len(bc_fields)} 個＋テキスト {len(tx_fields)} 個が"
                f"ラベル高さ {cfg['label_height']:.1f}mm に収まりません。"
                f"（現サイズ最大 {max_bc} 個）"
            )
        return errs

    # ---------------------------------------------------------------- PDF生成

    def _generate_pages(self) -> List["Image.Image"]:
        cfg = self._get_config()
        dpi = cfg["dpi"]
        def mm2px(mm): return int(mm * dpi / 25.4)

        pw, ph = PAPER_SIZES.get(cfg["paper_size"], (210, 297))
        pgw, pgh = mm2px(pw), mm2px(ph)
        ml,  mt  = mm2px(cfg["margin_left"]),  mm2px(cfg["margin_top"])
        lw,  lh  = mm2px(cfg["label_width"]),  mm2px(cfg["label_height"])
        sh,  sv  = mm2px(cfg["spacing_h"]),    mm2px(cfg["spacing_v"])
        cols, rows = cfg["cols"], cfg["rows"]
        lpp   = cols * rows
        start = cfg["start_position"] - 1
        modes = cfg["field_modes"]

        bc_fields = [c for c in self.data_mgr.csv_columns if modes.get(c) == "barcode"]
        tx_fields = [c for c in self.data_mgr.csv_columns if modes.get(c) == "text"]

        bc_margin   = mm2px(LABEL_BC_MARGIN_MM)
        font_small  = _get_japanese_font(mm2px(LABEL_FONT_SIZE_MM))
        text_line_h = mm2px(LABEL_TEXT_LINE_H_MM)
        text_total_h = len(tx_fields) * text_line_h
        available_h  = lh - bc_margin*2 - text_total_h
        bc_each_h    = max(mm2px(LABEL_MIN_BC_H_MM), available_h // len(bc_fields)) if bc_fields else 0

        pages: List["Image.Image"] = []
        ri    = 0
        slot  = start

        while ri < len(self.records):
            page = Image.new("RGB", (pgw, pgh), "white")
            draw = ImageDraw.Draw(page)

            while slot < lpp and ri < len(self.records):
                r_pos = slot // cols
                c_pos = slot %  cols
                x = ml + c_pos * (lw + sh)
                y = mt + r_pos * (lh + sv)
                self._render_label(draw, page, self.records[ri], x, y,
                                   lw, bc_margin, bc_fields, tx_fields,
                                   bc_each_h, text_line_h, font_small, cfg, mm2px)
                ri   += 1
                slot += 1

            pages.append(page)
            slot = 0

        return pages

    def _render_label(self, draw, page, rec: dict,
                      x: int, y: int, lw: int, bc_margin: int,
                      bc_fields: list, tx_fields: list,
                      bc_each_h: int, text_line_h: int,
                      font_small, cfg: dict, mm2px) -> None:
        """1枚のラベルを描画する。"""
        cur_y = y + bc_margin
        for tf in tx_fields:
            val  = str(rec.get(tf, ""))
            line = f"{self.data_mgr.get_column_display_name(tf)}: {val}"
            bbox = draw.textbbox((0, 0), line, font=font_small)
            tw   = bbox[2] - bbox[0]
            tx   = x + (lw - tw) // 2
            draw.text((tx, cur_y), line, fill="black", font=font_small)
            cur_y += text_line_h

        for bf in bc_fields:
            bc_val = str(rec.get(bf, ""))
            if bc_val:
                try:
                    bc_img = generate_code128_image(
                        bc_val,
                        width=lw - bc_margin*2,
                        height=bc_each_h - (mm2px(LABEL_BC_TEXT_H_MM) if cfg["show_text"] else 0),
                        show_text=cfg["show_text"],
                    )
                    bx = x + (lw - bc_img.width) // 2
                    page.paste(bc_img, (bx, cur_y))
                    cur_y += bc_img.height + mm2px(LABEL_BC_GAP_MM)
                except Exception as e:
                    logger.warning("バーコード生成スキップ (%s): %s", bc_val, e)
                    cur_y += bc_each_h

    # ---------------------------------------------------------------- 保存・印刷

    def _save_pdf(self) -> None:
        errs = self._check_overflow()
        if errs:
            messagebox.showerror("ラベルサイズ超過", "\n".join(errs), parent=self.dlg); return
        pages = self._generate_pages()
        if not pages:
            messagebox.showwarning("データなし", "印刷するレコードがありません。",
                                   parent=self.dlg); return
        fp = filedialog.asksaveasfilename(
            parent=self.dlg, title="PDF 保存", defaultextension=".pdf",
            initialfile="barcode_labels.pdf", filetypes=[("PDF", "*.pdf")])
        if not fp:
            return
        try:
            cfg = self._get_config()
            if len(pages) == 1:
                pages[0].save(fp, "PDF", resolution=cfg["dpi"])
            else:
                pages[0].save(fp, "PDF", save_all=True,
                              append_images=pages[1:], resolution=cfg["dpi"])
            self.data_mgr.add_history("ラベル印刷", f"{len(self.records)} 件 PDF 出力: {os.path.basename(fp)}")
            self.data_mgr.save()
            self._persist_settings()
            messagebox.showinfo("完了", f"PDF 保存完了:\n{fp}", parent=self.dlg)
        except Exception as e:
            logger.error("PDF 保存エラー: %s", e)
            messagebox.showerror("エラー", f"PDF 保存エラー:\n{e}", parent=self.dlg)

    def _print_labels(self) -> None:
        errs = self._check_overflow()
        if errs:
            messagebox.showerror("ラベルサイズ超過", "\n".join(errs), parent=self.dlg); return
        pages = self._generate_pages()
        if not pages:
            messagebox.showwarning("データなし", "レコードがありません。",
                                   parent=self.dlg); return
        try:
            cfg = self._get_config()
            tmp_fd, tp = tempfile.mkstemp(suffix=".pdf")
            with os.fdopen(tmp_fd, "wb"):
                pass
            if len(pages) == 1:
                pages[0].save(tp, "PDF", resolution=cfg["dpi"])
            else:
                pages[0].save(tp, "PDF", save_all=True,
                              append_images=pages[1:], resolution=cfg["dpi"])

            if sys.platform == "win32":
                os.startfile(tp, "print")
            elif sys.platform == "darwin":
                subprocess.run(["lpr", tp], timeout=30, check=True)
            else:
                try:
                    subprocess.run(["lpr", tp], timeout=30, check=True)
                except (FileNotFoundError, subprocess.CalledProcessError):
                    subprocess.run(["xdg-open", tp], timeout=30)

            self.data_mgr.add_history("ラベル印刷", f"{len(self.records)} 件印刷")
            self.data_mgr.save()
            self._persist_settings()
            messagebox.showinfo("印刷", "印刷キューに送信しました。", parent=self.dlg)
        except subprocess.TimeoutExpired:
            messagebox.showerror("タイムアウト", "印刷処理がタイムアウトしました。", parent=self.dlg)
        except Exception as e:
            logger.error("印刷エラー: %s", e)
            messagebox.showerror("エラー", f"印刷エラー:\n{e}", parent=self.dlg)


# ==============================================================================
# STEP 8 — ManagerTab（汎用管理UIタブ）
# ==============================================================================

class ManagerTab(ttk.Frame):
    """
    1 つのプロファイルに対応する管理タブ。
    DataManager / ProfileTemplate を受け取り、汎用的に動作する。
    """

    SYSTEM_COLS = {
        "_no":         {"text": "No.",        "width": 50,  "minwidth": 40,  "anchor": "center"},
        "_status":     {"text": "ステータス",  "width": 110, "minwidth": 100, "anchor": "center"},
        "_barcode_id": {"text": "バーコードID","width": 130, "minwidth": 100, "anchor": "w"},
    }

    def __init__(self, parent, data_mgr: DataManager, profile: "Profile",
                 license_mgr: Optional["LicenseManager"] = None,
                 member_mgr:  Optional["MemberManager"]  = None) -> None:
        super().__init__(parent)
        self.data_mgr    = data_mgr
        self.profile     = profile
        self.template    = profile.template
        self.license_mgr = license_mgr
        self.member_mgr  = member_mgr
        self.loan_mgr    = LoanManager(data_mgr.data_file)

        self.sort_col     = None
        self.sort_rev     = False
        self.current_page = 0
        self._drag_src    = None
        self._drag_lbl    = None
        self._drag_active = False
        self._barcode_img = None   # 現在表示中の PIL Image
        self._barcode_val = ""
        self.barcode_photo = None

        self._batch_list: List[Tuple[int, str, str]] = []

        self._setup_styles()
        self._create_ui()
        self._refresh_table()
        self._refresh_history()

    # ---------------------------------------------------------------- スタイル

    def _setup_styles(self) -> None:
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("Treeview",         rowheight=32, font=FONTS["body"])
        s.configure("Treeview.Heading", font=FONTS["h6"],
                    background=COLORS["border"], foreground=COLORS["text"])
        s.configure("Toolbar.TButton",  font=FONTS["body_sm"], padding=(8, 4))

    # ---------------------------------------------------------------- UI構築

    def _create_ui(self) -> None:
        self._create_toolbar()
        self._create_filter_bar()
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True)
        left = ttk.Frame(pw); pw.add(left, weight=3)
        self._create_table(left)
        self._create_page_nav(left)
        right = ttk.Frame(pw); pw.add(right, weight=2)
        self._create_scan_panel(right)
        self._create_barcode_panel(right)
        self._create_history_panel(right)

    # ---- UI サブメソッド ----

    def _create_toolbar(self) -> None:
        tb = tk.Frame(self, bg=COLORS["toolbar_bg"],
                      highlightbackground=COLORS["border"], highlightthickness=1)
        tb.pack(fill="x", pady=(0, 4), ipady=3)

        def tbtn(text, cmd):
            return ttk.Button(tb, text=text, command=cmd, style="Toolbar.TButton")

        tbtn("CSV取り込み", self._import_csv).pack(side="left", padx=(5, 2))
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=5, pady=3)
        tbtn("バーコード印刷", self._print_barcode).pack(side="left", padx=2)
        tbtn("ラベル印刷",    self._open_label_print).pack(side="left", padx=2)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=5, pady=3)
        for sv in self.template.status_values:
            tbtn(sv, lambda s=sv: self._change_status(s)).pack(side="left", padx=2)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=5, pady=3)
        tbtn("編集",      self._edit_selected).pack(side="left", padx=2)
        tbtn("削除",      self._delete_selected).pack(side="left", padx=2)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=5, pady=3)
        tbtn("カラム設定", self._column_settings).pack(side="left", padx=2)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=5, pady=3)
        tbtn("貸出",       self._checkout_dialog).pack(side="left", padx=2)
        tbtn("返却",       self._return_dialog).pack(side="left", padx=2)
        tbtn("棚卸",       self._inventory_mode).pack(side="left", padx=2)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=5, pady=3)
        tbtn("一括印刷",   self._bulk_label_print).pack(side="left", padx=2)
        tbtn("レポート",   self._report_dialog).pack(side="left", padx=2)

    def _create_filter_bar(self) -> None:
        ff = tk.Frame(self, bg=COLORS["bg"]); ff.pack(fill="x", pady=(0, 4))
        tk.Label(ff, text="検索:", bg=COLORS["bg"]).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._on_search_changed())
        ttk.Entry(ff, textvariable=self.search_var, width=30).pack(side="left", padx=5)
        tk.Label(ff, text="ステータス:", bg=COLORS["bg"]).pack(side="left", padx=(12, 0))
        self.filter_status_var = tk.StringVar(value="すべて")
        sc = ttk.Combobox(ff, textvariable=self.filter_status_var,
                          values=["すべて"] + self.template.status_values,
                          state="readonly", width=12)
        sc.pack(side="left", padx=5)
        sc.bind("<<ComboboxSelected>>", lambda _: self._refresh_table())

    def _create_table(self, parent: tk.Widget) -> None:
        tf = ttk.Frame(parent); tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, selectmode="extended", show="headings")
        vsb = ttk.Scrollbar(tf, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tf.grid_rowconfigure(0, weight=1); tf.grid_columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>",         self._on_double_click)
        self.tree.bind("<ButtonPress-1>",    self._on_header_press,   add=True)
        self.tree.bind("<B1-Motion>",        self._on_header_drag,    add=True)
        self.tree.bind("<ButtonRelease-1>",  self._on_header_release, add=True)

        ctx = tk.Menu(self.tree, tearoff=0)
        ctx.add_command(label="編集...",   command=self._edit_selected)
        for sv in self.template.status_values:
            ctx.add_command(label=sv, command=lambda s=sv: self._change_status(s))
        ctx.add_separator()
        ctx.add_command(label="削除", command=self._delete_selected)
        self.ctx = ctx
        bind_ev = "<Button-2>" if sys.platform == "darwin" else "<Button-3>"
        self.tree.bind(bind_ev, self._show_ctx)
        if sys.platform == "darwin":
            self.tree.bind("<Control-Button-1>", self._show_ctx)

    def _create_page_nav(self, parent: tk.Widget) -> None:
        pnav = tk.Frame(parent, bg=COLORS["bg"]); pnav.pack(fill="x", pady=2)
        ttk.Button(pnav, text="< 前",
                   command=self._prev_page).pack(side="left", padx=4)
        self.page_label_var = tk.StringVar(value="1 / 1ページ")
        tk.Label(pnav, textvariable=self.page_label_var,
                 bg=COLORS["bg"], font=FONTS["caption"]).pack(side="left", padx=8)
        ttk.Button(pnav, text="次 >",
                   command=self._next_page).pack(side="left", padx=4)
        self.status_label_var = tk.StringVar()
        tk.Label(pnav, textvariable=self.status_label_var,
                 bg=COLORS["bg"], font=FONTS["caption"],
                 fg=COLORS["muted"]).pack(side="right", padx=8)

    def _create_scan_panel(self, parent: tk.Widget) -> None:
        ss = tk.LabelFrame(parent, text=" バーコードスキャン ",
                           font=FONTS["h6"],
                           bg=COLORS["card"], fg=COLORS["text"], padx=10, pady=6)
        ss.pack(fill="x", pady=(0, 8))

        mf = tk.Frame(ss, bg=COLORS["card"]); mf.pack(fill="x", pady=(0, 4))
        tk.Label(mf, text="モード:", bg=COLORS["card"], font=FONTS["label_bold"]).pack(side="left")
        self.scan_mode_var = tk.StringVar(value="instant")
        ttk.Radiobutton(mf, text="即時反映", variable=self.scan_mode_var,
                        value="instant", command=self._on_scan_mode_change).pack(side="left", padx=(4,10))
        ttk.Radiobutton(mf, text="一括",     variable=self.scan_mode_var,
                        value="batch",   command=self._on_scan_mode_change).pack(side="left")

        self.scan_desc = tk.Label(ss, text="スキャン → 自動ステータス切替",
                                  bg=COLORS["card"], font=FONTS["small"], fg=COLORS["muted"])
        self.scan_desc.pack(anchor="w")

        sif = tk.Frame(ss, bg=COLORS["card"]); sif.pack(fill="x", pady=4)
        self.scan_var   = tk.StringVar()
        self.scan_entry = ttk.Entry(sif, textvariable=self.scan_var, font=FONTS["scan_input"])
        self.scan_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.scan_entry.bind("<Return>", self._on_scan)
        ttk.Button(sif, text="スキャン", command=self._on_scan).pack(side="right")

        self.scan_result = tk.Label(ss, text="", bg=COLORS["card"],
                                    font=FONTS["body_sm"], wraplength=340, justify="left")
        self.scan_result.pack(anchor="w", pady=2)

        # 一括モードフレーム
        self.batch_frame = tk.Frame(ss, bg=COLORS["card"])
        tk.Label(self.batch_frame, text="スキャン済み:",
                 bg=COLORS["card"], font=FONTS["label_bold"]).pack(anchor="w")
        blf = tk.Frame(self.batch_frame, bg=COLORS["card"]); blf.pack(fill="x", pady=2)
        self.batch_lb  = tk.Listbox(blf, height=5, font=FONTS["caption"], selectmode="extended")
        bsb = ttk.Scrollbar(blf, orient="vertical", command=self.batch_lb.yview)
        self.batch_lb.configure(yscrollcommand=bsb.set)
        self.batch_lb.pack(side="left", fill="x", expand=True); bsb.pack(side="right", fill="y")
        self.batch_cnt = tk.Label(self.batch_frame, text="0 件",
                                  bg=COLORS["card"], font=FONTS["caption"], fg=COLORS["muted"])
        self.batch_cnt.pack(anchor="w")
        bbf = tk.Frame(self.batch_frame, bg=COLORS["card"]); bbf.pack(fill="x", pady=2)
        ttk.Button(bbf, text="一括適用", command=self._batch_apply).pack(side="left", padx=2)
        ttk.Button(bbf, text="除外",     command=self._batch_remove).pack(side="left", padx=2)
        ttk.Button(bbf, text="クリア",   command=self._batch_clear).pack(side="left", padx=2)

    def _create_barcode_panel(self, parent: tk.Widget) -> None:
        bs = tk.LabelFrame(parent, text=" バーコードプレビュー ",
                           font=FONTS["h6"],
                           bg=COLORS["card"], fg=COLORS["text"], padx=10, pady=6)
        bs.pack(fill="x", pady=(0, 8))
        self.bc_canvas = tk.Label(bs, bg="white", relief="sunken", height=7)
        self.bc_canvas.pack(fill="x", pady=4)
        self.bc_info   = tk.Label(bs, text="行を選択するとバーコードを表示",
                                  bg=COLORS["card"], font=FONTS["caption"], fg=COLORS["muted"])
        self.bc_info.pack(anchor="w")
        bcbf = tk.Frame(bs, bg=COLORS["card"]); bcbf.pack(fill="x", pady=(4, 0))
        ttk.Button(bcbf, text="印刷",    command=self._print_barcode).pack(side="left", padx=2)
        ttk.Button(bcbf, text="画像保存",command=self._save_barcode).pack(side="left", padx=2)

        bcol_f = tk.Frame(bs, bg=COLORS["card"]); bcol_f.pack(fill="x", pady=(4, 0))
        tk.Label(bcol_f, text="バーコード値カラム:", bg=COLORS["card"],
                 font=FONTS["caption"]).pack(side="left")
        self.bc_col_var   = tk.StringVar(value=self.data_mgr.barcode_column or "")
        self.bc_col_combo = ttk.Combobox(bcol_f, textvariable=self.bc_col_var,
                                         state="readonly", width=20)
        self.bc_col_combo.pack(side="left", padx=4)
        self.bc_col_combo.bind("<<ComboboxSelected>>", self._on_barcode_col_change)
        self._update_col_combo()

    def _create_history_panel(self, parent: tk.Widget) -> None:
        hs = tk.LabelFrame(parent, text=" 操作履歴 ",
                           font=FONTS["h6"],
                           bg=COLORS["card"], fg=COLORS["text"], padx=10, pady=6)
        hs.pack(fill="both", expand=True)
        self.hist_tree, _ = _make_treeview(hs, [
            ("time", "日時", 140), ("action", "操作", 100), ("detail", "詳細", 250),
        ], height=8)

    # ---------------------------------------------------------------- テーブル

    def _all_columns(self) -> List[str]:
        disp    = self.data_mgr.get_display_columns()
        default = ["_no", "_status", "_barcode_id"] + disp
        saved   = self.data_mgr.column_order
        if saved:
            valid   = set(default)
            ordered = [c for c in saved if c in valid]
            for c in default:
                if c not in ordered:
                    ordered.append(c)
            return ordered
        return default

    def _sort_suffix(self, col: str) -> str:
        if self.sort_col == col:
            return " ▼" if self.sort_rev else " ▲"
        return ""

    def _setup_columns(self) -> None:
        cols = self._all_columns()
        self.tree["columns"] = cols
        for col in cols:
            suf = self._sort_suffix(col)
            if col in self.SYSTEM_COLS:
                info = self.SYSTEM_COLS[col]
                self.tree.heading(col, text=info["text"] + suf,
                                  command=lambda c=col: self._on_sort(c))
                self.tree.column(col, width=info["width"],
                                 minwidth=info["minwidth"], anchor=info["anchor"])
            else:
                dn = self.data_mgr.get_column_display_name(col)
                self.tree.heading(col, text=dn + suf,
                                  command=lambda c=col: self._on_sort(c))
                self.tree.column(col, width=120, minwidth=80)

    def _get_filtered(self) -> List[Tuple[int, dict]]:
        search = self.search_var.get().lower()
        fstatus = self.filter_status_var.get()
        out = []
        for i, rec in enumerate(self.data_mgr.records):
            if fstatus != "すべて" and rec.get("_status") != fstatus:
                continue
            if search and not any(search in str(v).lower() for v in rec.values()):
                continue
            out.append((i, rec))
        if self.sort_col:
            sc = self.sort_col
            out.sort(
                key=lambda item: item[0] if sc == "_no" else str(item[1].get(sc, "")).lower(),
                reverse=self.sort_rev,
            )
        return out

    def _refresh_table(self) -> None:
        self._setup_columns()
        for item in self.tree.get_children():
            self.tree.delete(item)

        all_filtered = self._get_filtered()
        total_pages  = max(1, math.ceil(len(all_filtered) / PAGE_SIZE))
        self.current_page = min(self.current_page, total_pages - 1)

        start = self.current_page * PAGE_SIZE
        page  = all_filtered[start: start + PAGE_SIZE]

        cols = self._all_columns()
        for i, rec in page:
            status_raw = rec.get("_status", "")
            sd = ("● " if status_raw == self.template.status_values[0] else "◉ ") + status_raw
            vals = []
            for col in cols:
                if   col == "_no":         vals.append(i + 1)
                elif col == "_status":     vals.append(sd)
                elif col == "_barcode_id": vals.append(rec.get("_barcode_id", ""))
                else:                      vals.append(rec.get(col, ""))
            # 延滞行は overdue タグで上書き
            active_loan = self.loan_mgr.get_active_loan_for_item(
                rec.get("_barcode_id", "")
            )
            if active_loan and active_loan.is_overdue:
                tag = "overdue"
            else:
                tag = self._tag_for_status(status_raw)
            self.tree.insert("", "end", iid=str(i), values=vals, tags=(tag,))

        for st, color in self.template.status_colors.items():
            self.tree.tag_configure("st_" + st, background=color)
        self.tree.tag_configure("overdue", background=COLORS["overdue_bg"], foreground=COLORS["danger"])

        # サマリー更新
        total = len(self.data_mgr.records)
        self.page_label_var.set(
            f"{self.current_page+1} / {total_pages} ページ"
            f"（{len(all_filtered)} 件中 {len(page)} 件表示）"
        )
        counts = {sv: sum(1 for r in self.data_mgr.records if r.get("_status")==sv)
                  for sv in self.template.status_values}
        summary = "  ".join(f"{k}: {v}" for k, v in counts.items())
        self.status_label_var.set(f"全 {total} 件  |  {summary}")

    def _tag_for_status(self, status: str) -> str:
        return "st_" + status if status in self.template.status_colors else ""

    def _on_sort(self, col: str) -> None:
        if self.sort_col == col:
            if self.sort_rev:
                self.sort_col = None; self.sort_rev = False
            else:
                self.sort_rev = True
        else:
            self.sort_col = col; self.sort_rev = False
        self._refresh_table()

    def _on_search_changed(self) -> None:
        self.current_page = 0
        self._refresh_table()

    def _prev_page(self) -> None:
        if self.current_page > 0:
            self.current_page -= 1; self._refresh_table()

    def _next_page(self) -> None:
        all_filtered = self._get_filtered()
        total_pages  = max(1, math.ceil(len(all_filtered) / PAGE_SIZE))
        if self.current_page < total_pages - 1:
            self.current_page += 1; self._refresh_table()

    def _refresh_history(self) -> None:
        for item in self.hist_tree.get_children():
            self.hist_tree.delete(item)
        for entry in reversed(self.data_mgr.history[-100:]):
            self.hist_tree.insert("", "end", values=(
                entry.get("timestamp", ""),
                entry.get("action",    ""),
                entry.get("detail",    ""),
            ))

    # ---------------------------------------------------------------- ヘッダー D&D

    def _on_header_press(self, event) -> None:
        if self.tree.identify_region(event.x, event.y) == "heading":
            self._drag_src    = self._col_id_to_name(self.tree.identify_column(event.x))
            self._drag_start_x = event.x
            self._drag_active  = False
        else:
            self._drag_src = None

    def _on_header_drag(self, event) -> None:
        if not self._drag_src:
            return
        if not self._drag_active and abs(event.x - self._drag_start_x) < 20:
            return
        self._drag_active = True
        if not self._drag_lbl:
            dn = (self.SYSTEM_COLS[self._drag_src]["text"]
                  if self._drag_src in self.SYSTEM_COLS
                  else self.data_mgr.get_column_display_name(self._drag_src))
            self._drag_lbl = tk.Label(
                self.tree, text=f" {dn} ", font=FONTS["section"],
                bg=COLORS["primary_light"], fg="white", relief="raised", padx=6, pady=2)
        self._drag_lbl.place(x=event.x - 30, y=2)

    def _on_header_release(self, event) -> None:
        if self._drag_lbl:
            self._drag_lbl.destroy(); self._drag_lbl = None
        if not self._drag_src or not self._drag_active:
            self._drag_src = None; self._drag_active = False; return
        src = self._drag_src; self._drag_src = None; self._drag_active = False
        if self.tree.identify_region(event.x, event.y) == "heading":
            dst = self._col_id_to_name(self.tree.identify_column(event.x))
            if dst and dst != src:
                cols = self._all_columns()
                if src in cols and dst in cols:
                    si = cols.index(src); di = cols.index(dst)
                    cols.pop(si); cols.insert(di, src)
                    self.data_mgr.column_order = cols
                    self.data_mgr.save()
                    self._refresh_table()

    def _col_id_to_name(self, col_id: str) -> Optional[str]:
        try:
            idx  = int(col_id.replace("#", "")) - 1
            cols = list(self.tree["columns"])
            return cols[idx] if 0 <= idx < len(cols) else None
        except (ValueError, IndexError):
            return None

    # ---------------------------------------------------------------- イベント

    def _show_ctx(self, event) -> None:
        item = self.tree.identify_row(event.y)
        if item:
            if item not in self.tree.selection():
                self.tree.selection_set(item)
            self.ctx.post(event.x_root, event.y_root)

    def _on_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except ValueError:
            return
        if 0 <= idx < len(self.data_mgr.records):
            rec = self.data_mgr.records[idx]
            bv  = rec.get("_barcode_id", "")
            if bv:
                self._show_barcode(bv)
                parts = [f"ID: {bv}", rec.get("_status", "")]
                for col in self.data_mgr.csv_columns[:3]:
                    val = rec.get(col, "")
                    if val:
                        parts.append(f"{self.data_mgr.get_column_display_name(col)}: {val}")
                self.bc_info.config(text=" | ".join(parts))

    def _on_double_click(self, _event=None) -> None:
        sel = self.tree.selection()
        if sel:
            self._show_edit_dialog(int(sel[0]))

    # ---------------------------------------------------------------- スキャン

    def _on_scan_mode_change(self) -> None:
        if self.scan_mode_var.get() == "instant":
            self.batch_frame.pack_forget()
            self.scan_desc.config(text="スキャン → 自動ステータス切替")
        else:
            self.batch_frame.pack(fill="x", pady=(4, 0))
            self.scan_desc.config(text="スキャン → リスト蓄積 → 一括適用")

    def _next_status(self, current: str) -> str:
        vals = self.template.status_values
        if current in vals:
            return vals[(vals.index(current) + 1) % len(vals)]
        return vals[0] if vals else current

    def _on_scan(self, _event=None) -> None:
        val = self.scan_var.get().strip()
        if not val:
            return
        results = self.data_mgr.find_by_barcode(val)
        if not results:
            self.scan_result.config(text=f"'{val}' 該当なし", fg=COLORS["danger"])
            self.data_mgr.add_history("スキャン", f"値:{val} → 該当なし")
            self.data_mgr.save()
            self._refresh_history()
            self.scan_var.set(""); self.scan_entry.focus_set()
            return

        self.tree.selection_set([str(i) for i, _ in results])
        if results:
            self.tree.see(str(results[0][0]))

        if self.scan_mode_var.get() == "instant":
            info = []
            for idx, rec in results:
                old = rec.get("_status", self.template.default_status)
                new = self._next_status(old)
                self.data_mgr.update_status(idx, new)
                info.append(f"{rec.get('_barcode_id','')}: {old} → {new}")
            self._refresh_table(); self._refresh_history()
            self.scan_result.config(
                text=f"即時反映 {len(results)} 件\n" + "\n".join(info),
                fg=COLORS["success"])
        else:
            added = 0
            for idx, rec in results:
                bid = rec.get("_barcode_id", "")
                old = rec.get("_status", self.template.default_status)
                if not any(x[0] == idx for x in self._batch_list):
                    self._batch_list.append((idx, bid, old))
                    new = self._next_status(old)
                    self.batch_lb.insert(tk.END, f"[{idx+1}] {bid}: {old} → {new}")
                    added += 1
            self.batch_cnt.config(text=f"{len(self._batch_list)} 件")
            self.scan_result.config(
                text=f"{added} 件追加（計 {len(self._batch_list)} 件）" if added else f"'{val}' 追加済み",
                fg=COLORS["primary"] if added else COLORS["warning"])
            self.data_mgr.add_history("スキャン(一括)", f"値:{val}"); self.data_mgr.save()
            self._refresh_history()

        self.scan_var.set(""); self.scan_entry.focus_set()

    def _batch_apply(self) -> None:
        if not self._batch_list:
            messagebox.showwarning("空", "リストが空です。"); return
        n = len(self._batch_list)
        if not messagebox.askyesno("確認", f"{n} 件のステータスを切り替えますか？"):
            return
        for idx, bid, old in self._batch_list:
            self.data_mgr.update_status(idx, self._next_status(old))
        self.data_mgr.add_history("一括変更", f"{n} 件ステータス切替")
        self.data_mgr.save()
        self._refresh_table(); self._refresh_history()
        self.scan_result.config(text=f"{n} 件変更完了", fg=COLORS["success"])
        self._batch_clear()

    def _batch_remove(self) -> None:
        for i in sorted(self.batch_lb.curselection(), reverse=True):
            self.batch_lb.delete(i)
            if i < len(self._batch_list):
                self._batch_list.pop(i)
        self.batch_cnt.config(text=f"{len(self._batch_list)} 件")

    def _batch_clear(self) -> None:
        self._batch_list.clear()
        self.batch_lb.delete(0, tk.END)
        self.batch_cnt.config(text="0 件")

    # ---------------------------------------------------------------- バーコード

    def _show_barcode(self, value: str) -> None:
        if not HAS_PIL:
            self.bc_canvas.config(text="Pillow が必要です", image=""); return
        try:
            img = generate_code128_image(value, width=BARCODE_PREVIEW_W, height=BARCODE_PREVIEW_H)
            self.barcode_photo = ImageTk.PhotoImage(img)
            self.bc_canvas.config(image=self.barcode_photo, text="")
            self._barcode_val = value
            self._barcode_img = img
        except Exception as e:
            logger.warning("バーコード表示エラー: %s", e)
            self.bc_canvas.config(text=f"エラー: {e}", image="")

    def _print_barcode(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("選択なし", "印刷するレコードを選択してください。"); return
        images = []
        for s in sel:
            try:
                idx = int(s)
                if 0 <= idx < len(self.data_mgr.records):
                    bv = self.data_mgr.records[idx].get("_barcode_id", "")
                    if bv:
                        images.append((bv, generate_code128_image(bv, width=BARCODE_IMG_W, height=BARCODE_IMG_H)))
            except Exception as e:
                logger.warning("バーコード生成スキップ: %s", e)
        if not images:
            return
        margin = 20
        total_h = sum(img.height for _, img in images) + margin * (len(images) + 1)
        max_w   = max(img.width  for _, img in images) + margin * 2
        pi      = Image.new("RGB", (max_w, total_h), "white")
        y = margin
        for _, img in images:
            pi.paste(img, ((max_w - img.width) // 2, y)); y += img.height + margin
        try:
            tmp_fd, tp = tempfile.mkstemp(suffix=".png")
            with os.fdopen(tmp_fd, "wb"):
                pass
            pi.save(tp)
            if sys.platform == "darwin":
                subprocess.run(["lpr", tp], timeout=30)
            elif sys.platform == "win32":
                os.startfile(tp, "print")
            else:
                try:
                    subprocess.run(["lpr", tp], timeout=30, check=True)
                except (FileNotFoundError, subprocess.CalledProcessError):
                    subprocess.run(["xdg-open", tp], timeout=30)
            self.data_mgr.add_history("バーコード印刷", f"{len(images)} 件")
            self.data_mgr.save()
            self._refresh_history()
        except subprocess.TimeoutExpired:
            messagebox.showerror("タイムアウト", "印刷処理がタイムアウトしました。")
        except Exception as e:
            logger.error("バーコード印刷エラー: %s", e)
            messagebox.showerror("エラー", str(e))

    def _save_barcode(self) -> None:
        if not self._barcode_img:
            messagebox.showwarning("なし", "バーコードがありません。"); return
        fp = filedialog.asksaveasfilename(
            title="バーコード画像保存", defaultextension=".png",
            initialfile=f"barcode_{self._barcode_val}.png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")])
        if fp:
            self._barcode_img.save(fp)

    def _update_col_combo(self) -> None:
        self.bc_col_combo["values"] = self.data_mgr.csv_columns
        if (self.data_mgr.barcode_column and
                self.data_mgr.barcode_column in self.data_mgr.csv_columns):
            self.bc_col_var.set(self.data_mgr.barcode_column)

    def _on_barcode_col_change(self, _event=None) -> None:
        col = self.bc_col_var.get()
        if col:
            self.data_mgr.barcode_column = col
            for rec in self.data_mgr.records:
                if col in rec:
                    rec["_barcode_id"] = rec[col]
            self.data_mgr.save()
            self._refresh_table()
            messagebox.showinfo("設定完了", f"バーコードカラム: '{col}'")

    # ---------------------------------------------------------------- CSV取り込み

    def _import_csv(self) -> None:
        # 体験版: 既に上限に達していれば先に警告
        licensed = self.license_mgr.is_licensed if self.license_mgr else True
        if not licensed and len(self.data_mgr.records) >= TRIAL_LIMIT:
            self._show_trial_limit_dialog()
            return

        fp = filedialog.askopenfilename(
            title="CSV 選択",
            filetypes=[("CSV", "*.csv"), ("テキスト", "*.txt"), ("すべて", "*.*")])
        if not fp:
            return

        dlg = _make_modal_dialog(self.winfo_toplevel(), "エンコーディング選択", "300x200")
        tk.Label(dlg, text="文字コードを選択:", font=FONTS["body_sm"]).pack(pady=10)
        ev = tk.StringVar(value="utf-8")
        for enc in ["utf-8", "shift_jis", "cp932", "euc-jp"]:
            ttk.Radiobutton(dlg, text=enc, variable=ev, value=enc).pack(anchor="w", padx=30)

        def do_import():
            dlg.destroy()
            max_recs = None if licensed else TRIAL_LIMIT
            try:
                n, dups, limit_hit = self.data_mgr.import_csv(fp, ev.get(), max_recs)
                self._update_col_combo()
                self._refresh_table()
                self._refresh_history()
                msg = f"{n} 件取り込み完了。"
                if dups:
                    msg += f"\n重複スキップ: {len(dups)} 件"
                if limit_hit:
                    msg += f"\n\n⚠ 体験版のため {TRIAL_LIMIT} 件で停止しました。\n続きは製品版をご購入ください。"
                messagebox.showinfo("完了", msg)
                if limit_hit:
                    self._show_trial_limit_dialog()
            except Exception as e:
                logger.error("CSV 取り込みエラー: %s", e)
                messagebox.showerror("エラー", str(e))

        ttk.Button(dlg, text="取り込む", command=do_import).pack(pady=10)

    def _show_trial_limit_dialog(self) -> None:
        """体験版の上限到達ダイアログ。"""
        ans = messagebox.askyesno(
            "体験版の上限に達しました",
            f"体験版では {TRIAL_LIMIT} 件まで管理できます。\n\n"
            "製品版（無制限）を購入しますか？\n"
            "「はい」で購入ページを開きます。",
        )
        if ans:
            import webbrowser
            webbrowser.open(PURCHASE_URL)

    # ---------------------------------------------------------------- ステータス変更

    def _change_status(self, new_status: str) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("選択なし", "レコードを選択してください。"); return
        for s in sel:
            self.data_mgr.update_status(int(s), new_status)
        self._refresh_table(); self._refresh_history()

    # ---------------------------------------------------------------- 編集

    def _edit_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("選択なし", "編集するレコードを選択してください。"); return
        if len(sel) > 1:
            messagebox.showwarning("複数選択", "1 件ずつ編集してください。"); return
        self._show_edit_dialog(int(sel[0]))

    def _show_edit_dialog(self, index: int) -> None:
        rec = self.data_mgr.records[index]
        dlg = _make_modal_dialog(self.winfo_toplevel(), f"編集 — {rec.get('_barcode_id','')}", "600x700")
        self._edit_dlg_barcode_header(dlg, rec)
        fo = ttk.Frame(dlg); fo.pack(fill="both", expand=True, padx=10, pady=5)
        _, ff = _make_scrollable_frame(fo)
        r = 0
        entry_vars, r = self._edit_dlg_data_fields(ff, rec, r)
        bc_var, st_var, r = self._edit_dlg_system_fields(ff, rec, r)
        qty_total_var, qty_avail_var, r = self._edit_dlg_quantity_fields(ff, rec, r)
        current_photo_path, r = self._edit_dlg_photo_fields(ff, rec, dlg, r)
        ff.grid_columnconfigure(1, weight=1)
        self._edit_dlg_save_buttons(dlg, index, rec, entry_vars, bc_var,
                                     st_var, qty_total_var, qty_avail_var,
                                     current_photo_path)

    def _edit_dlg_barcode_header(self, dlg: tk.Toplevel, rec: dict) -> None:
        bv = rec.get("_barcode_id", "")
        if bv and HAS_PIL:
            try:
                img   = generate_code128_image(bv, width=BARCODE_EDIT_W, height=BARCODE_EDIT_H)
                photo = ImageTk.PhotoImage(img)
                lbl   = tk.Label(dlg, image=photo, bg="white")
                lbl.image = photo
                lbl.pack(fill="x", padx=10, pady=(10, 5))
            except Exception as e:
                logger.warning("編集ダイアログ バーコード表示エラー: %s", e)

    def _edit_dlg_data_fields(self, ff: ttk.Frame, rec: dict,
                               r: int) -> Tuple[Dict[str, tk.StringVar], int]:
        ttk.Label(ff, text="データフィールド",
                  font=FONTS["h6"]).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=5, pady=(5,3)); r += 1
        entry_vars: Dict[str, tk.StringVar] = {}
        for col in self.data_mgr.csv_columns:
            dn  = self.data_mgr.get_column_display_name(col)
            ttk.Label(ff, text=f"{dn}:", width=20, anchor="e").grid(
                row=r, column=0, sticky="e", padx=5, pady=2)
            var = tk.StringVar(value=str(rec.get(col, "")))
            ttk.Entry(ff, textvariable=var, width=35).grid(
                row=r, column=1, sticky="ew", padx=5, pady=2)
            entry_vars[col] = var; r += 1
        return entry_vars, r

    def _edit_dlg_system_fields(self, ff: ttk.Frame, rec: dict,
                                 r: int) -> Tuple[tk.StringVar, tk.StringVar, int]:
        ttk.Separator(ff).grid(row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1
        ttk.Label(ff, text="管理情報",
                  font=FONTS["h6"]).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=5); r += 1
        ttk.Label(ff, text="バーコードID:", width=20, anchor="e").grid(
            row=r, column=0, sticky="e", padx=5, pady=2)
        bc_var = tk.StringVar(value=rec.get("_barcode_id",""))
        ttk.Entry(ff, textvariable=bc_var, width=35).grid(
            row=r, column=1, sticky="ew", padx=5, pady=2); r += 1
        ttk.Label(ff, text="ステータス:", width=20, anchor="e").grid(
            row=r, column=0, sticky="e", padx=5, pady=2)
        st_var = tk.StringVar(value=rec.get("_status", self.template.default_status))
        ttk.Combobox(ff, textvariable=st_var, values=self.template.status_values,
                     state="readonly", width=15).grid(
            row=r, column=1, sticky="w", padx=5, pady=2); r += 1
        ttk.Label(ff, text="取り込み日時:", width=20, anchor="e").grid(
            row=r, column=0, sticky="e", padx=5, pady=2)
        ttk.Label(ff, text=rec.get("_imported_at",""),
                  foreground=COLORS["muted"]).grid(
            row=r, column=1, sticky="w", padx=5, pady=2); r += 1
        return bc_var, st_var, r

    def _edit_dlg_quantity_fields(self, ff: ttk.Frame, rec: dict,
                                   r: int) -> Tuple[tk.IntVar, tk.IntVar, int]:
        ttk.Separator(ff).grid(row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1
        ttk.Label(ff, text="数量管理", font=FONTS["h6"]).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=5); r += 1
        ttk.Label(ff, text="所有数:", width=20, anchor="e").grid(
            row=r, column=0, sticky="e", padx=5, pady=2)
        qty_total_var = tk.IntVar(value=int(rec.get("_qty_total", 1)))
        ttk.Spinbox(ff, from_=1, to=9999, textvariable=qty_total_var, width=8).grid(
            row=r, column=1, sticky="w", padx=5, pady=2); r += 1
        ttk.Label(ff, text="利用可能数:", width=20, anchor="e").grid(
            row=r, column=0, sticky="e", padx=5, pady=2)
        qty_avail_var = tk.IntVar(value=int(rec.get("_qty_available",
                                                     rec.get("_qty_total", 1))))
        ttk.Spinbox(ff, from_=0, to=9999, textvariable=qty_avail_var, width=8).grid(
            row=r, column=1, sticky="w", padx=5, pady=2); r += 1
        return qty_total_var, qty_avail_var, r

    def _edit_dlg_photo_fields(self, ff: ttk.Frame, rec: dict,
                                dlg: tk.Toplevel, r: int) -> Tuple[list, int]:
        ttk.Separator(ff).grid(row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1
        ttk.Label(ff, text="写真", font=FONTS["h6"]).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=5); r += 1
        photo_label = tk.Label(ff, bg=COLORS["bg_alt"], relief="sunken",
                               width=22, height=7, text="（写真未登録）",
                               fg=COLORS["muted"])
        photo_label.grid(row=r, column=0, columnspan=2, sticky="ew",
                         padx=5, pady=4); r += 1
        current_photo_path = [rec.get("_photo", "")]

        def _reload_photo_preview() -> None:
            rel = current_photo_path[0]
            if not rel or not HAS_PIL:
                return
            abs_p = os.path.join(os.path.dirname(self.data_mgr.data_file), rel)
            if not os.path.exists(abs_p):
                return
            try:
                img   = Image.open(abs_p).resize((200, 130), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                photo_label.config(image=photo, text="")
                photo_label._photo_ref = photo
            except Exception as e:
                logger.warning("写真プレビューエラー: %s", e)

        _reload_photo_preview()

        def _select_photo() -> None:
            fp = filedialog.askopenfilename(
                parent=dlg, title="写真を選択",
                filetypes=[("画像", "*.jpg *.jpeg *.png *.bmp *.gif"), ("すべて", "*.*")]
            )
            if not fp:
                return
            photos_dir = os.path.join(
                os.path.dirname(self.data_mgr.data_file), "photos"
            )
            os.makedirs(photos_dir, exist_ok=True)
            bid_s = rec.get("_barcode_id", "unknown").replace("/", "_").replace("\\", "_")
            ts    = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            ext   = os.path.splitext(fp)[1].lower() or ".jpg"
            dest  = os.path.join(photos_dir, f"{bid_s}_{ts}{ext}")
            shutil.copy2(fp, dest)
            current_photo_path[0] = os.path.join("photos", os.path.basename(dest))
            _reload_photo_preview()

        ttk.Button(ff, text="写真を選択...", command=_select_photo).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=5, pady=2); r += 1
        return current_photo_path, r

    def _edit_dlg_save_buttons(self, dlg: tk.Toplevel, index: int, rec: dict,
                                entry_vars: Dict[str, tk.StringVar],
                                bc_var: tk.StringVar, st_var: tk.StringVar,
                                qty_total_var: tk.IntVar, qty_avail_var: tk.IntVar,
                                current_photo_path: list) -> None:
        def save_edit() -> None:
            updates: Dict[str, str] = {}
            for col, var in entry_vars.items():
                if var.get() != str(rec.get(col, "")):
                    updates[col] = var.get()
            nb = bc_var.get().strip()
            if nb and nb != rec.get("_barcode_id", ""):
                updates["_barcode_id"] = nb
            ns = st_var.get()
            if ns != rec.get("_status", ""):
                updates["_status"] = ns
            new_total = qty_total_var.get()
            new_avail = qty_avail_var.get()
            if new_total != int(rec.get("_qty_total", 1)):
                updates["_qty_total"] = new_total
            if new_avail != int(rec.get("_qty_available", rec.get("_qty_total", 1))):
                updates["_qty_available"] = new_avail
            if current_photo_path[0] != rec.get("_photo", ""):
                updates["_photo"] = current_photo_path[0]
            if updates:
                self.data_mgr.update_record(index, updates)
                self._refresh_table(); self._refresh_history()
                messagebox.showinfo("完了", f"{len(updates)} 件変更保存", parent=dlg)
            dlg.destroy()

        bf = ttk.Frame(dlg); bf.pack(fill="x", padx=10, pady=10)
        ttk.Button(bf, text="保存",      command=save_edit).pack(side="left",  padx=8)
        ttk.Button(bf, text="キャンセル",command=dlg.destroy).pack(side="right", padx=8)

    # ---------------------------------------------------------------- 削除・クリア

    def _delete_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("確認", f"{len(sel)} 件を削除しますか？"):
            return
        for idx in sorted([int(s) for s in sel], reverse=True):
            self.data_mgr.delete_record(idx)
        self._refresh_table(); self._refresh_history()

    # ---------------------------------------------------------------- ラベル印刷

    def _open_label_print(self) -> None:
        sel  = self.tree.selection()
        recs = ([self.data_mgr.records[int(s)] for s in sel
                 if 0 <= int(s) < len(self.data_mgr.records)]
                if sel else self.data_mgr.records)
        if not recs:
            messagebox.showwarning("なし", "レコードがありません。"); return
        LabelPrintDialog(self.winfo_toplevel(), recs, self.data_mgr)

    # ---------------------------------------------------------------- 貸出処理

    def _checkout_dialog(self) -> None:
        """貸出ダイアログ。"""
        import webbrowser as _wb
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("選択なし", "貸出するアイテムを選択してください。"); return
        idx = int(sel[0])
        if idx >= len(self.data_mgr.records):
            return
        rec = self.data_mgr.records[idx]
        bid = rec.get("_barcode_id", "")

        avail = rec.get("_qty_available", rec.get("_qty_total", 1))
        if avail <= 0:
            messagebox.showwarning("在庫なし", "利用可能数がありません。"); return

        dlg = _make_modal_dialog(self.winfo_toplevel(), "貸出処理", "440x340", resizable=False)

        tk.Label(dlg, text=f"アイテムID: {bid}",
                 font=FONTS["h5"]).pack(pady=12)

        frm = ttk.Frame(dlg); frm.pack(padx=20, fill="x")

        # 利用者選択
        tk.Label(frm, text="利用者:").grid(row=0, column=0, sticky="e", padx=6, pady=4)
        members = self.member_mgr.get_active() if self.member_mgr else []
        member_var = tk.StringVar()
        combo = ttk.Combobox(
            frm, textvariable=member_var, width=28,
            values=[f"{m.name}（{m.barcode_id}）" if m.barcode_id else m.name
                    for m in members],
        )
        combo.grid(row=0, column=1, sticky="w", pady=4)

        tk.Label(frm, text="または\nバーコード直接入力:").grid(row=1, column=0, sticky="e", padx=6)
        scan_var = tk.StringVar()
        scan_entry = ttk.Entry(frm, textvariable=scan_var, width=24)
        scan_entry.grid(row=1, column=1, sticky="w", pady=4)
        scan_entry.focus_set()

        tk.Label(frm, text="返却期限 (YYYY-MM-DD):").grid(row=2, column=0, sticky="e", padx=6)
        due_var = tk.StringVar()
        ttk.Entry(frm, textvariable=due_var, width=14).grid(row=2, column=1, sticky="w", pady=4)

        err_var = tk.StringVar()
        tk.Label(dlg, textvariable=err_var, fg=COLORS["danger"],
                 font=FONTS["caption"]).pack()

        def _do() -> None:
            member = None
            scan_val = scan_var.get().strip()
            if scan_val and self.member_mgr:
                member = self.member_mgr.find_by_barcode(scan_val)
                if member is None:
                    err_var.set(f"利用者バーコード '{scan_val}' が見つかりません。"); return
            if member is None and member_var.get() and self.member_mgr:
                sel_name = member_var.get()
                for m in members:
                    disp = f"{m.name}（{m.barcode_id}）" if m.barcode_id else m.name
                    if disp == sel_name:
                        member = m; break
            if member is None:
                err_var.set("利用者を選択またはバーコードを入力してください。"); return

            self.loan_mgr.checkout(
                barcode_id = bid,
                member_id  = member.id,
                due_date   = due_var.get().strip(),
            )
            # 在庫数を減算
            new_avail = max(0, avail - 1)
            self.data_mgr.records[idx]["_qty_available"] = new_avail
            if new_avail == 0:
                self.data_mgr.records[idx]["_status"] = "貸出中"
            self.data_mgr.add_history(
                "貸出",
                f"ID:{bid} → {member.name}  期限:{due_var.get().strip() or 'なし'}",
            )
            self.data_mgr.save()
            self._refresh_table()
            dlg.destroy()
            messagebox.showinfo("完了", f"貸出完了\n利用者: {member.name}")

        bf = ttk.Frame(dlg); bf.pack(pady=12)
        ttk.Button(bf, text="貸出実行", command=_do).pack(side="left", padx=6)
        ttk.Button(bf, text="キャンセル", command=dlg.destroy).pack(side="left", padx=6)
        dlg.bind("<Return>", lambda _: _do())

    def _return_dialog(self) -> None:
        """返却ダイアログ。"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("選択なし", "返却するアイテムを選択してください。"); return
        idx = int(sel[0])
        if idx >= len(self.data_mgr.records):
            return
        rec = self.data_mgr.records[idx]
        bid = rec.get("_barcode_id", "")

        active = self.loan_mgr.get_active_loan_for_item(bid)
        if active is None:
            messagebox.showinfo("情報", "このアイテムは現在貸出中ではありません。"); return

        member_name = ""
        if self.member_mgr:
            m = self.member_mgr.find_by_id(active.member_id)
            if m:
                member_name = m.name

        if not messagebox.askyesno(
            "返却確認",
            f"アイテム ID: {bid}\n"
            f"利用者: {member_name or active.member_id}\n\n"
            "返却処理を行いますか？"
        ):
            return

        self.loan_mgr.return_item(active.loan_id)

        # 在庫数を加算
        total = rec.get("_qty_total", 1)
        new_avail = min(total, rec.get("_qty_available", 0) + 1)
        self.data_mgr.records[idx]["_qty_available"] = new_avail
        if new_avail > 0 and rec.get("_status") == "貸出中":
            # テンプレートのデフォルトステータスに戻す
            self.data_mgr.records[idx]["_status"] = self.template.default_status
        self.data_mgr.add_history(
            "返却",
            f"ID:{bid}  利用者:{member_name or active.member_id}",
        )
        self.data_mgr.save()
        self._refresh_table()
        messagebox.showinfo("完了", f"返却完了\nID: {bid}")

    # ---------------------------------------------------------------- 棚卸モード

    def _inventory_mode(self) -> None:
        InventoryDialog(self.winfo_toplevel(), self.data_mgr)

    # ---------------------------------------------------------------- 一括ラベル印刷

    def _bulk_label_print(self) -> None:
        sel = self.tree.selection()
        if sel:
            records = [
                self.data_mgr.records[int(s)]
                for s in sel
                if 0 <= int(s) < len(self.data_mgr.records)
            ]
            label = f"選択 {len(records)} 件"
        else:
            records = list(self.data_mgr.records)
            label   = f"全件 {len(records)} 件"

        if not records:
            messagebox.showinfo("情報", "印刷対象がありません。"); return
        if messagebox.askyesno("一括ラベル印刷", f"{label}のラベルを印刷しますか？"):
            LabelPrintDialog(self.winfo_toplevel(), records, self.data_mgr)

    # ---------------------------------------------------------------- レポート

    def _report_dialog(self) -> None:
        MonthlyReportDialog(
            self.winfo_toplevel(),
            self.data_mgr,
            self.loan_mgr,
            self.member_mgr,
            self.profile.name,
        )

    # ---------------------------------------------------------------- カラム設定

    def _column_settings(self) -> None:
        if not self.data_mgr.csv_columns:
            messagebox.showinfo("情報", "まず CSV を取り込んでください。"); return

        dlg = _make_modal_dialog(self.winfo_toplevel(), "カラム表示設定", "570x520")

        ttk.Label(dlg, text="表示順序・表示名・表示 / 非表示を設定",
                  font=FONTS["section"]).pack(padx=10, pady=(10, 5))

        main = ttk.Frame(dlg); main.pack(fill="both", expand=True, padx=10, pady=5)
        lf   = ttk.Frame(main); lf.pack(side="left", fill="both", expand=True)

        ct, _ = _make_treeview(lf, [
            ("vis", "表示", 45, "center"), ("orig", "元カラム名", 180),
            ("disp", "表示名（ダブルクリック編集）", 200),
        ], height=16)

        current_disp = self.data_mgr.get_display_columns()
        vis_set      = set(current_disp)
        ordered      = list(current_disp)
        for c in self.data_mgr.csv_columns:
            if c not in ordered:
                ordered.append(c)
        for col in ordered:
            ct.insert("", "end", iid=col,
                      values=("✓" if col in vis_set else "",
                              col,
                              self.data_mgr.get_column_display_name(col)))

        def on_dbl(event):
            if ct.identify_region(event.x, event.y) != "cell":
                return
            if ct.identify_column(event.x) != "#3":
                return
            item = ct.identify_row(event.y)
            if not item:
                return
            bbox = ct.bbox(item, column="disp")
            if not bbox:
                return
            x, y, w, h = bbox
            vals = ct.item(item, "values")
            ent  = tk.Entry(ct, font=FONTS["body"])
            ent.place(x=x, y=y, width=w, height=h)
            ent.insert(0, vals[2]); ent.select_range(0, tk.END); ent.focus_set()
            def finish(_e=None):
                nv = ent.get().strip()
                if nv:
                    ct.item(item, values=(vals[0], vals[1], nv))
                ent.destroy()
            ent.bind("<Return>", finish); ent.bind("<Escape>", lambda _: ent.destroy())
            ent.bind("<FocusOut>", finish)

        ct.bind("<Double-1>", on_dbl)

        bf = ttk.Frame(main); bf.pack(side="right", padx=(10, 0))

        def move(d):
            sel = ct.selection()
            if not sel:
                return
            idx = ct.index(sel[0])
            ni  = idx + d
            if 0 <= ni < len(ct.get_children()):
                ct.move(sel[0], "", ni)

        def toggle():
            for s in ct.selection():
                vs = ct.item(s, "values")
                ct.item(s, values=("" if vs[0]=="✓" else "✓", vs[1], vs[2]))

        def reset():
            for item in ct.get_children():
                ct.delete(item)
            for col in self.data_mgr.csv_columns:
                ct.insert("", "end", iid=col, values=("✓", col, col))

        def apply():
            new_disp, new_alias = [], {}
            for item in ct.get_children():
                vs = ct.item(item, "values")
                if vs[0] == "✓":
                    new_disp.append(vs[1])
                if vs[2] != vs[1]:
                    new_alias[vs[1]] = vs[2]
            self.data_mgr.display_columns  = new_disp
            self.data_mgr.column_aliases   = new_alias
            self.data_mgr.save()
            self._refresh_table()
            dlg.destroy()
            messagebox.showinfo("完了", "カラム表示設定を保存しました。")

        for text, cmd in [("▲ 上へ", lambda: move(-1)), ("▼ 下へ", lambda: move(1)),
                          ("表示切替", toggle)]:
            ttk.Button(bf, text=text, command=cmd, width=12).pack(pady=2)
        ttk.Separator(bf, orient="horizontal").pack(fill="x", pady=8)
        ttk.Button(bf, text="リセット",   command=reset,  width=12).pack(pady=2)
        ttk.Separator(bf, orient="horizontal").pack(fill="x", pady=8)
        ttk.Button(bf, text="✓ 適用",    command=apply,  width=12).pack(pady=2)
        ttk.Button(bf, text="キャンセル", command=dlg.destroy, width=12).pack(pady=2)


# ==============================================================================
# STEP 9 — App（メインウィンドウ）
# ==============================================================================

class App:
    """
    メインウィンドウ。
    ProfileManager でプロファイルを読み込み、ttk.Notebook に ManagerTab を展開する。
    """

    def __init__(self, root: tk.Tk) -> None:
        self.root        = root
        self.data_dir    = get_data_dir()
        self.prof_mgr    = ProfileManager(self.data_dir)
        self.license_mgr = LicenseManager(self.data_dir)
        self.member_mgr  = MemberManager(self.data_dir)
        self._tabs: Dict[str, ManagerTab] = {}   # profile.id → ManagerTab

        root.title(f"{APP_NAME}  v{APP_VERSION}")
        root.geometry("1340x820")
        root.minsize(1000, 620)
        root.configure(bg=COLORS["bg"])

        self._build_ui()

        # 初回起動チェック
        if self.prof_mgr.is_empty():
            wiz = SetupWizard(root, self.prof_mgr)
            if not wiz.created_profile:
                root.destroy()
                return

        self._load_tabs()
        self._check_overdue_on_startup()

    # ---------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        # ヘッダー
        hdr = tk.Frame(self.root, bg=COLORS["primary"], height=54)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text=f"  {APP_NAME}",
                 font=FONTS["h1"],
                 fg="white", bg=COLORS["primary"]).pack(side="left", padx=15, pady=8)
        tk.Label(hdr, text=f"v{APP_VERSION}",
                 font=FONTS["body_sm"],
                 fg=COLORS["accent_light"], bg=COLORS["primary"]).pack(side="left", pady=8)

        # ライセンス状態ラベル（右端）
        self._lic_label_var = tk.StringVar()
        self._update_lic_label()
        tk.Label(hdr, textvariable=self._lic_label_var,
                 font=FONTS["caption"],
                 fg=COLORS["badge_yellow"], bg=COLORS["primary"]).pack(side="right", padx=16, pady=8)

        # メニュー
        self._build_menu()

        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=6)

    def _update_lic_label(self) -> None:
        if self.license_mgr.is_licensed:
            self._lic_label_var.set("✅ ライセンス認証済み")
        else:
            self._lic_label_var.set(f"⚠ 体験版（{TRIAL_LIMIT} 件まで）　購入はヘルプ → ライセンス認証")

    def _check_overdue_on_startup(self) -> None:
        """起動時に全台帳の延滞アイテムを確認して警告ダイアログを表示する。"""
        overdue_lines = []
        for tab in self._tabs.values():
            for loan in tab.loan_mgr.get_overdue_loans():
                member = self.member_mgr.find_by_id(loan.member_id)
                m_name = member.name if member else loan.member_id
                overdue_lines.append(
                    f"• [{tab.profile.name}]  ID:{loan.barcode_id}"
                    f"  利用者:{m_name}  期限:{loan.due_date}"
                    f"  ({loan.days_overdue}日超過)"
                )
        if not overdue_lines:
            return
        msg = f"延滞アイテムが {len(overdue_lines)} 件あります:\n\n"
        msg += "\n".join(overdue_lines[:15])
        if len(overdue_lines) > 15:
            msg += f"\n... 他 {len(overdue_lines)-15} 件"
        messagebox.showwarning("⚠ 延滞アラート", msg)

    def _build_menu(self) -> None:
        mb = tk.Menu(self.root)
        self.root.config(menu=mb)

        fm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="ファイル", menu=fm)
        fm.add_command(label="台帳を追加...",      command=self._add_profile)
        fm.add_command(label="台帳を削除...",      command=self._remove_profile)
        fm.add_separator()
        fm.add_command(label="データをエクスポート (JSON)...", command=self._export_json)
        fm.add_command(label="履歴をエクスポート (CSV)...",   command=self._export_history)
        fm.add_separator()
        fm.add_command(label="全データクリア", command=self._clear_all)
        fm.add_separator()
        fm.add_command(label="終了", command=self.root.quit, accelerator="Ctrl+Q")

        em = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="編集", menu=em)
        em.add_command(label="レコード編集...", command=self._edit_cur,   accelerator="Ctrl+E")
        em.add_separator()
        em.add_command(label="選択削除",        command=self._delete_cur)

        sm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="設定", menu=sm)
        sm.add_command(label="バーコードカラム設定...", command=self._bc_col_setting)
        sm.add_command(label="データファイル場所...",   command=self._set_data_file)
        sm.add_command(label="カラム表示設定...",       command=self._col_settings)

        hm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="ヘルプ", menu=hm)
        hm.add_command(label="使い方", command=self._show_help)
        hm.add_separator()
        hm.add_command(label="ライセンス認証...", command=self._show_license_dialog)

        self.root.bind("<Control-q>", lambda _: self.root.quit())
        self.root.bind("<Control-e>", lambda _: self._edit_cur())
        self.root.bind("<Control-i>", lambda _: self._cur_tab()._import_csv()
                       if self._cur_tab() else None)
        self.root.bind("<Control-p>", lambda _: self._cur_tab()._open_label_print()
                       if self._cur_tab() else None)

    # ---------------------------------------------------------------- タブ管理

    def _load_tabs(self) -> None:
        """固定タブ（ダッシュボード・利用者管理）+ 各プロファイルをロード。"""
        # ── 固定タブ ──
        self._dashboard_tab = DashboardTab(
            self.notebook,
            self.prof_mgr,
            get_data_mgrs=lambda: [t.data_mgr for t in self._tabs.values()],
            get_loan_mgrs=lambda: [t.loan_mgr  for t in self._tabs.values()],
            member_mgr=self.member_mgr,
        )
        self.notebook.add(self._dashboard_tab, text="📊  ダッシュボード")

        self._member_tab = MemberTab(
            self.notebook,
            self.member_mgr,
            get_loan_mgrs=lambda: [t.loan_mgr for t in self._tabs.values()],
        )
        self.notebook.add(self._member_tab, text="👤  利用者管理")

        # ── プロファイルタブ ──
        for p in self.prof_mgr.profiles:
            self._add_tab(p)

    def _add_tab(self, profile: "Profile") -> None:
        data_mgr = DataManager(profile.data_file, profile.template)
        tab      = ManagerTab(self.notebook, data_mgr, profile,
                              license_mgr=self.license_mgr,
                              member_mgr=self.member_mgr)
        self.notebook.add(tab, text=f"{profile.template.icon}  {profile.name}")
        self._tabs[profile.id] = tab
        # ダッシュボードが存在すれば更新
        if hasattr(self, "_dashboard_tab"):
            self._dashboard_tab.refresh()

    def _cur_tab(self) -> Optional[ManagerTab]:
        try:
            return list(self._tabs.values())[self.notebook.index("current")]
        except (IndexError, tk.TclError):
            return None

    # ---------------------------------------------------------------- プロファイル追加・削除

    def _add_profile(self) -> None:
        dlg = _make_modal_dialog(self.root, "台帳を追加", "420x320")

        tk.Label(dlg, text="新しい管理台帳を追加",
                 font=FONTS["h5"]).pack(pady=(16, 8))
        tk.Label(dlg, text="テンプレート:").pack(anchor="w", padx=24)
        type_var = tk.StringVar(value="passport")
        for key, tpl in TEMPLATES.items():
            ttk.Radiobutton(dlg, text=f"{tpl.icon}  {tpl.label}",
                            variable=type_var, value=key).pack(anchor="w", padx=40, pady=2)
        tk.Label(dlg, text="台帳名:").pack(anchor="w", padx=24, pady=(10, 2))
        name_var = tk.StringVar()

        def on_type(*_):
            if not name_var.get() or name_var.get() in [t.label for t in TEMPLATES.values()]:
                name_var.set(TEMPLATES[type_var.get()].label)
        type_var.trace_add("write", on_type); on_type()

        ttk.Entry(dlg, textvariable=name_var, width=32,
                  font=FONTS["body"]).pack(padx=24, pady=2)

        def ok():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("入力エラー", "台帳名を入力してください。",
                                       parent=dlg); return
            p = self.prof_mgr.add_profile(type_var.get(), name)
            self._add_tab(p)
            dlg.destroy()
            self.notebook.select(len(self.notebook.tabs()) - 1)

        bf = ttk.Frame(dlg); bf.pack(pady=16)
        ttk.Button(bf, text="キャンセル", command=dlg.destroy).pack(side="right", padx=4)
        ttk.Button(bf, text="追加",       command=ok).pack(side="right", padx=4)

    def _remove_profile(self) -> None:
        if len(self.prof_mgr.profiles) <= 1:
            messagebox.showwarning("削除不可", "台帳は最低 1 つ必要です。"); return
        try:
            cur_idx = self.notebook.index("current")
            profile = self.prof_mgr.profiles[cur_idx]
        except (IndexError, tk.TclError):
            messagebox.showwarning("選択なし", "削除する台帳を選択してください。"); return
        if not messagebox.askyesno("確認",
                                   f"台帳「{profile.name}」を削除しますか？\n"
                                   f"（データファイルは残ります）"):
            return
        tab = self._tabs.pop(profile.id, None)
        if tab:
            self.notebook.forget(tab)
        self.prof_mgr.remove_profile(profile.id)

    # ---------------------------------------------------------------- メニューコマンド（委譲）

    def _edit_cur(self) -> None:
        t = self._cur_tab()
        if t:
            t._edit_selected()

    def _delete_cur(self) -> None:
        t = self._cur_tab()
        if t:
            t._delete_selected()

    def _bc_col_setting(self) -> None:
        t = self._cur_tab()
        if not t:
            return
        if not t.data_mgr.csv_columns:
            messagebox.showinfo("情報", "CSV を取り込んでください。"); return
        dlg = _make_modal_dialog(self.root, "バーコードカラム", "360x320")
        tk.Label(dlg, text="バーコード値に使うカラムを選択:",
                 font=FONTS["body_sm"]).pack(pady=10)
        v = tk.StringVar(value=t.data_mgr.barcode_column or "")
        for col in t.data_mgr.csv_columns:
            ttk.Radiobutton(dlg, text=col, variable=v, value=col).pack(anchor="w", padx=30)
        def apply():
            if v.get():
                t.bc_col_var.set(v.get())
                t._on_barcode_col_change()
            dlg.destroy()
        ttk.Button(dlg, text="適用", command=apply).pack(pady=10)

    def _col_settings(self) -> None:
        t = self._cur_tab()
        if t:
            t._column_settings()

    def _set_data_file(self) -> None:
        t = self._cur_tab()
        if not t:
            return
        fp = filedialog.asksaveasfilename(
            title="データファイル場所", defaultextension=".json",
            initialfile=os.path.basename(t.data_mgr.data_file),
            filetypes=[("JSON", "*.json")])
        if fp:
            t.data_mgr.data_file = fp
            t.data_mgr.save()

    def _export_json(self) -> None:
        t = self._cur_tab()
        if not t:
            return
        fp = filedialog.asksaveasfilename(
            title="JSON エクスポート", defaultextension=".json",
            initialfile="export.json", filetypes=[("JSON", "*.json")])
        if fp:
            try:
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump({
                        "records":     t.data_mgr.records,
                        "history":     t.data_mgr.history,
                        "exported_at": datetime.datetime.now().isoformat(),
                    }, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("完了", f"エクスポート完了:\n{fp}")
            except OSError as e:
                messagebox.showerror("エラー", str(e))

    def _export_history(self) -> None:
        t = self._cur_tab()
        if not t:
            return
        fp = filedialog.asksaveasfilename(
            title="履歴 CSV エクスポート", defaultextension=".csv",
            initialfile="history.csv", filetypes=[("CSV", "*.csv")])
        if fp:
            try:
                with open(fp, "w", encoding="utf-8-sig", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["日時", "操作", "詳細"])
                    for e in t.data_mgr.history:
                        w.writerow([e.get("timestamp",""), e.get("action",""), e.get("detail","")])
                messagebox.showinfo("完了", f"履歴 CSV エクスポート完了:\n{fp}")
            except OSError as e:
                messagebox.showerror("エラー", str(e))

    def _clear_all(self) -> None:
        t = self._cur_tab()
        if not t:
            return
        if messagebox.askyesno("確認", "現在の台帳のデータをすべて削除しますか？"):
            t.data_mgr.clear_all()
            t._refresh_table()
            t._refresh_history()

    def _show_license_dialog(self) -> None:
        """ライセンス認証ダイアログ。"""
        import webbrowser
        dlg = _make_modal_dialog(self.root, "ライセンス認証", "480x320", resizable=False)

        # ── 現在の状態表示 ──────────────────────────────────
        if self.license_mgr.is_licensed:
            status_text = "✅  ライセンス認証済みです。\nすべての機能を制限なく使用できます。"
            status_fg   = COLORS["success"]
        else:
            status_text = (f"⚠  現在は体験版です（{TRIAL_LIMIT} 件まで）。\n"
                           "ライセンスキーを入力して製品版に移行してください。")
            status_fg   = COLORS["warning"]

        tk.Label(dlg, text=status_text, fg=status_fg,
                 font=FONTS["body_sm"], justify="left",
                 wraplength=440).pack(padx=20, pady=18, anchor="w")

        ttk.Separator(dlg, orient="horizontal").pack(fill="x", padx=20)

        # ── キー入力 ────────────────────────────────────────
        tk.Label(dlg, text="ライセンスキー（BMGR-XXXX-XXXX-XXXX）:",
                 font=FONTS["caption"]).pack(anchor="w", padx=20, pady=(12, 2))
        key_var = tk.StringVar()
        entry   = ttk.Entry(dlg, textvariable=key_var, width=34,
                            font=FONTS["mono"])
        entry.pack(padx=20, pady=(0, 4))
        entry.focus_set()

        err_var = tk.StringVar()
        tk.Label(dlg, textvariable=err_var, fg=COLORS["danger"],
                 font=FONTS["caption"]).pack(anchor="w", padx=20)

        # ── ボタン行 ─────────────────────────────────────────
        bf = ttk.Frame(dlg)
        bf.pack(side="bottom", fill="x", padx=20, pady=14)

        def _activate() -> None:
            key = key_var.get().strip().upper()
            if not key:
                err_var.set("キーを入力してください。"); return
            if self.license_mgr.activate(key):
                self._update_lic_label()
                messagebox.showinfo("認証成功",
                                    "ライセンス認証が完了しました！\n"
                                    "すべての機能が利用可能になりました。",
                                    parent=dlg)
                dlg.destroy()
            else:
                err_var.set("キーが無効です。入力内容を確認してください。")

        def _open_store() -> None:
            webbrowser.open(PURCHASE_URL)

        ttk.Button(bf, text="購入ページを開く",
                   command=_open_store).pack(side="left")
        ttk.Button(bf, text="キャンセル",
                   command=dlg.destroy).pack(side="right", padx=(4, 0))
        ttk.Button(bf, text="認証する",
                   command=_activate).pack(side="right")

        dlg.bind("<Return>", lambda _: _activate())

    def _show_help(self) -> None:
        text = f"""{APP_NAME}  v{APP_VERSION}  使い方

■ プロファイル（台帳）
  ファイル > 台帳を追加 で新しい管理台帳（タブ）を追加できます。
  テンプレートは「パスポート管理」「書籍管理」「カスタム」から選べます。

■ CSV 取り込み（Ctrl+I）
  任意の CSV 構造に対応。BOM 付き UTF-8 / Shift-JIS なども自動吸収。
  重複バーコードは自動スキップし、件数を報告します。

■ カラム表示設定
  設定メニュー または ツールバー「カラム設定」から
  列の表示順・表示名・表示 / 非表示を変更できます。
  ヘッダーをドラッグ＆ドロップしても列を並べ替えられます。

■ テーブルソート
  ヘッダーをクリックすると昇順▲ / 降順▼ / 解除をトグルします。

■ ページネーション
  大量データ（{PAGE_SIZE} 件 / ページ）は前 / 次ボタンでページ移動。

■ スキャン（バーコードスキャナー対応）
  即時反映: スキャン直後にステータスを次の値へ切替
  一括モード: リストに蓄積 → 一括適用

■ バーコードラベル印刷（Ctrl+P）
  各カラムを「バーコード / テキスト / 非表示」に設定して印刷。
  印刷設定は自動保存されます。

■ キーボードショートカット
  Ctrl+I: CSV取り込み  Ctrl+P: ラベル印刷  Ctrl+E: 編集  Ctrl+Q: 終了
"""
        d = _make_modal_dialog(self.root, "使い方", "580x560", grab=False)
        t = tk.Text(d, wrap="word", font=FONTS["body_sm"], padx=15, pady=15)
        t.pack(fill="both", expand=True)
        t.insert("1.0", text); t.config(state="disabled")
        ttk.Button(d, text="閉じる", command=d.destroy).pack(pady=8)


# ==============================================================================
# STEP 10 — エントリーポイント & 補助ファイル生成
# ==============================================================================

def _ensure_sample_books(data_dir: str) -> None:
    """sample_books.csv がなければ生成する。"""
    dest = os.path.join(data_dir, "sample_books.csv")
    if os.path.exists(dest):
        return
    rows = [
        ["ISBN", "タイトル", "著者", "出版社", "発行年", "ジャンル"],
        ["9784101092058", "坊っちゃん",       "夏目漱石",   "新潮社",   "1906", "小説"],
        ["9784101010014", "吾輩は猫である",   "夏目漱石",   "新潮社",   "1905", "小説"],
        ["9784003101414", "舞姫",             "森鷗外",     "岩波書店", "1890", "小説"],
        ["9784003101513", "山月記",           "中島敦",     "岩波書店", "1942", "短編"],
        ["9784003203118", "羅生門",           "芥川龍之介", "岩波書店", "1915", "短編"],
        ["9784062935487", "君の名は。",       "新海誠",     "KADOKAWA", "2016", "小説"],
        ["9784048912433", "進撃の巨人1",      "諫山創",     "講談社",   "2009", "漫画"],
        ["9784088820897", "ONE PIECE Vol.1",  "尾田栄一郎", "集英社",   "1997", "漫画"],
        ["9784091280206", "NARUTO1",          "岸本斉史",   "集英社",   "1999", "漫画"],
        ["9784063842593", "鋼の錬金術師1",    "荒川弘",     "スクエニ", "2002", "漫画"],
    ]
    try:
        with open(dest, "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f).writerows(rows)
        logger.info("sample_books.csv を生成しました: %s", dest)
    except OSError as e:
        logger.warning("sample_books.csv 生成失敗: %s", e)


def main() -> None:
    if not HAS_PIL:
        print("エラー: Pillow が必要です。pip install Pillow を実行してください。")
        sys.exit(1)

    data_dir = get_data_dir()

    # バンドル時: サンプル CSV を初回コピー
    if getattr(sys, "frozen", False):
        for fname in ["sample_passports.csv", "sample_books.csv"]:
            dest = os.path.join(data_dir, fname)
            if not os.path.exists(dest):
                src = get_resource_path(fname)
                if os.path.exists(src):
                    shutil.copy2(src, dest)
    else:
        _ensure_sample_books(data_dir)

    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()





