#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
keygen.py — バーコード管理システム v2.0  ライセンスキー生成ツール
==================================================================
販売者専用スクリプトです。絶対にユーザーへ配布しないでください。

使い方:
  python keygen.py                  # 1件生成（シリアル自動採番）
  python keygen.py --serial 42      # シリアル番号を指定して生成
  python keygen.py --bulk 10        # 10件まとめて生成
  python keygen.py --check BMGR-... # キーを検証

キー形式:
  BMGR-{SERIAL_HEX(4)}-{HMAC[0:4]}-{HMAC[4:8]}
  例) BMGR-002A-E7F3-91B4
"""

import argparse
import hashlib
import hmac
import os
import sys

# ★ manager_app.py の _APP_SECRET と必ず一致させること ★
_APP_SECRET = b"BM2024-XKJQ-9173-RSVP"

_SERIAL_FILE = os.path.join(os.path.dirname(__file__), ".keygen_serial")


# ==============================================================================
# コア関数
# ==============================================================================

def _load_serial() -> int:
    """前回のシリアル番号を読み込む（なければ 0）。"""
    try:
        with open(_SERIAL_FILE, "r") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


def _save_serial(n: int) -> None:
    """最後に使ったシリアル番号を保存する。"""
    with open(_SERIAL_FILE, "w") as f:
        f.write(str(n))


def generate_key(serial: int) -> str:
    """
    シリアル番号からライセンスキーを生成する。

    Parameters
    ----------
    serial : int   0 〜 65535 (0xFFFF) の整数

    Returns
    -------
    str   "BMGR-XXXX-YYYY-ZZZZ" 形式のキー
    """
    if not (0 <= serial <= 0xFFFF):
        raise ValueError(f"シリアルは 0〜65535 の範囲で指定してください: {serial}")

    serial_hex = f"{serial:04X}"
    msg        = f"BMGR{serial_hex}".encode()
    digest     = hmac.new(_APP_SECRET, msg, hashlib.sha256).hexdigest().upper()
    return f"BMGR-{serial_hex}-{digest[0:4]}-{digest[4:8]}"


def validate_key(key: str) -> bool:
    """
    ライセンスキーの正当性を検証する。
    manager_app.py の LicenseManager._validate() と同じロジック。
    """
    parts = key.strip().upper().split("-")
    if len(parts) != 4 or parts[0] != "BMGR":
        return False
    try:
        serial_hex = parts[1]
        int(serial_hex, 16)          # 16進数チェック
        msg    = f"BMGR{serial_hex}".encode()
        digest = hmac.new(_APP_SECRET, msg, hashlib.sha256).hexdigest().upper()
        expected = digest[0:4] + digest[4:8]
        given    = parts[2] + parts[3]
        return hmac.compare_digest(expected, given)
    except Exception:
        return False


# ==============================================================================
# CLI
# ==============================================================================

def _cmd_generate(serial: int | None, bulk: int) -> None:
    """キーを生成して表示する。"""
    last = _load_serial()

    keys = []
    for i in range(bulk):
        if serial is not None:
            s = serial + i
        else:
            s = last + i + 1
        key = generate_key(s)
        keys.append((s, key))

    # 最終シリアルを保存（bulk/serialモードともに）
    last_used = keys[-1][0]
    if serial is None:
        _save_serial(last_used)

    print()
    print("=" * 52)
    print("  バーコード管理システム  ライセンスキー")
    print("=" * 52)
    for s, k in keys:
        valid_mark = "✓" if validate_key(k) else "✗"
        print(f"  [{valid_mark}] Serial {s:5d} (0x{s:04X})  →  {k}")
    print("=" * 52)
    if len(keys) == 1:
        print(f"  ↑ このキーをユーザーに配布してください")
    else:
        print(f"  ↑ {len(keys)} 件生成しました")
    print()


def _cmd_check(key: str) -> None:
    """キーを検証して結果を表示する。"""
    result = validate_key(key)
    print()
    if result:
        print(f"  ✅  有効なキーです: {key.upper()}")
    else:
        print(f"  ❌  無効なキーです: {key}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="バーコード管理システム ライセンスキー生成ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--serial", type=int, default=None,
                        help="シリアル番号を指定 (0〜65535)")
    parser.add_argument("--bulk",   type=int, default=1,
                        help="生成件数 (デフォルト: 1)")
    parser.add_argument("--check",  type=str, default=None,
                        help="指定キーを検証する")

    args = parser.parse_args()

    if args.check:
        _cmd_check(args.check)
        sys.exit(0)

    if args.serial is not None and args.serial < 0:
        print("エラー: シリアルは 0 以上を指定してください。", file=sys.stderr)
        sys.exit(1)
    if args.bulk < 1:
        print("エラー: --bulk は 1 以上を指定してください。", file=sys.stderr)
        sys.exit(1)

    _cmd_generate(args.serial, args.bulk)


if __name__ == "__main__":
    main()
