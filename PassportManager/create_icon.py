#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
create_icon.py — バーコード管理システム アイコン生成スクリプト
=============================================================
Pillow を使って app.ico（マルチサイズ ICO）を作成します。
ICO は PNG 圧縮内包方式（Modern ICO）で生成するため
Windows Vista 以降のすべてのサイズ（16〜256px）が有効です。

使い方:
  python create_icon.py          # → app.ico を生成
  python create_icon.py --png    # → app.ico + app_256.png を生成
"""

import argparse
import io
import os
import struct
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("エラー: Pillow が必要です。  pip install Pillow")
    sys.exit(1)


# ==============================================================================
# アイコン描画
# ==============================================================================

def _draw_icon(size: int) -> Image.Image:
    """
    指定サイズのアイコン画像を描画して返す。

    デザイン:
      - 角丸の濃いブルー背景
      - 横 7 本の細いバーコードバー（白・幅比バリエーション）
      - バーの下に "BC" テキスト（白・太字）
    """
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── 角丸背景 ────────────────────────────────────────────
    radius   = max(size // 7, 4)
    bg_color = (30, 64, 175, 255)       # #1E40AF（メインブルー）

    # Pillow 9.2 以降: draw.rounded_rectangle が使えるが
    # 後方互換のため ellipse + rectangle 合成で描く
    draw.rectangle([radius, 0,          size - radius, size         ], fill=bg_color)
    draw.rectangle([0,      radius,     size,          size - radius], fill=bg_color)
    draw.ellipse  ([0,                  0,          radius * 2, radius * 2      ], fill=bg_color)
    draw.ellipse  ([size - radius * 2,  0,          size,       radius * 2      ], fill=bg_color)
    draw.ellipse  ([0,                  size - radius * 2, radius * 2,  size    ], fill=bg_color)
    draw.ellipse  ([size - radius * 2,  size - radius * 2, size,        size    ], fill=bg_color)

    # ── バーコードバー ──────────────────────────────────────
    white      = (255, 255, 255, 255)
    margin     = size * 0.18
    bar_top    = size * 0.20
    bar_bottom = size * 0.62

    # 幅比パターン（7 本） + 間隔は 0.5 ユニット
    pattern    = [1.0, 0.5, 1.5, 0.5, 2.0, 0.5, 1.0]
    gap        = 0.5
    total_u    = sum(pattern) + gap * (len(pattern) - 1)
    unit       = (size - margin * 2) / total_u
    x = margin
    for i, w in enumerate(pattern):
        draw.rectangle([x, bar_top, x + unit * w, bar_bottom], fill=white)
        x += unit * w + (unit * gap if i < len(pattern) - 1 else 0)

    # ── "BC" テキスト ────────────────────────────────────────
    text_y    = bar_bottom + size * 0.04
    font_size = max(int(size * 0.22), 8)
    font      = None
    for face in [
        "arialbd.ttf",
        "Arial Bold.ttf",
        "DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]:
        try:
            font = ImageFont.truetype(face, font_size)
            break
        except (OSError, IOError):
            continue
    if font is None:
        font = ImageFont.load_default()

    text = "BC"
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw   = bbox[2] - bbox[0]
    except AttributeError:
        tw, _ = draw.textsize(text, font=font)   # Pillow < 9 fallback
    draw.text(((size - tw) / 2, text_y), text, fill=white, font=font)

    return img


# ==============================================================================
# ICO ファイル手動生成（PNG 圧縮内包方式）
# ==============================================================================
# Pillow の ICO プラグインはマルチサイズ書き込みが不安定なため、
# ICO コンテナを直接 struct で組み立てる。
# 参考仕様: https://en.wikipedia.org/wiki/ICO_(file_format)

def _build_ico_bytes(images_dict: dict) -> bytes:
    """
    {size: PIL.Image} からマルチサイズ ICO バイト列を組み立てる。
    各サイズは PNG 圧縮で内包（Modern ICO）。
    """
    sizes     = sorted(images_dict.keys())
    n         = len(sizes)

    # 各サイズを PNG バイト列に変換
    png_datas = []
    for s in sizes:
        img = images_dict[s].convert("RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_datas.append(buf.getvalue())

    # ヘッダー(6B) + ディレクトリエントリ(16B×n) + 各 PNG データ
    dir_offset = 6 + 16 * n
    out = io.BytesIO()

    # ICONDIR
    out.write(struct.pack("<HHH", 0, 1, n))  # reserved=0, type=ICO=1, count=n

    # ICONDIRENTRY×n
    offset = dir_offset
    for i, s in enumerate(sizes):
        w = s if s < 256 else 0   # 256px は 0 で表す（ICO 仕様）
        h = s if s < 256 else 0
        out.write(struct.pack("<BBBBHHII",
            w, h,              # 幅・高さ（0 = 256px）
            0,                 # 色数（True Color は 0）
            0,                 # 予約済み
            1,                 # カラープレーン数
            32,                # bpp
            len(png_datas[i]), # 画像データサイズ
            offset,            # ファイル先頭からのオフセット
        ))
        offset += len(png_datas[i])

    # 画像データ本体
    for png_data in png_datas:
        out.write(png_data)

    return out.getvalue()


# ==============================================================================
# エントリーポイント
# ==============================================================================

ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]


def build_ico(out_path: str = "app.ico", extra_png: bool = False) -> None:
    """
    マルチサイズ ICO ファイルを生成する。

    Parameters
    ----------
    out_path  : str   出力先パス（デフォルト: app.ico）
    extra_png : bool  256px PNG も同時に生成するか
    """
    images = {s: _draw_icon(s) for s in ICON_SIZES}

    ico_data = _build_ico_bytes(images)
    with open(out_path, "wb") as f:
        f.write(ico_data)

    print(f"✅  アイコン生成完了: {out_path}")
    print(f"    収録サイズ: {', '.join(str(s) for s in ICON_SIZES)}")
    print(f"    ファイルサイズ: {len(ico_data):,} bytes")

    if extra_png:
        png_path = os.path.splitext(out_path)[0] + "_256.png"
        images[256].save(png_path, format="PNG")
        print(f"✅  PNG 生成完了:     {png_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="バーコード管理システム アイコン生成スクリプト"
    )
    parser.add_argument("--out", default="app.ico",
                        help="出力ファイルパス（デフォルト: app.ico）")
    parser.add_argument("--png", action="store_true",
                        help="256px PNG ファイルも生成する")
    args = parser.parse_args()

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    build_ico(out, extra_png=args.png)


if __name__ == "__main__":
    main()
