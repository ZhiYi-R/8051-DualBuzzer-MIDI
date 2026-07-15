"""固件仿真测试运行器。

用法（在仓库根目录或 Software/tests 目录下）::

    uv run python Software/tests/run_tests.py
    uv run python Software/tests/run_tests.py --s51 D:/Tools/SDCC/bin/s51.exe
    uv run python Software/tests/run_tests.py --build   # 强制重新编译固件
    uv run python Software/tests/run_tests.py -k timer  # 只运行名字含 "timer" 的用例

环境变量：
    SDCC_HOME  SDCC 安装根目录（用于定位 s51.exe 与 scons 构建）
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import traceback
from typing import Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from s51_driver import S51Driver, S51Error, resolve_variables  # noqa: E402
import test_firmware  # noqa: E402

# --------------------------------------------------------------------
# 路径与工具链发现
# --------------------------------------------------------------------
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
SOFTWARE_DIR = os.path.join(REPO_ROOT, "Software")
BUILD_DIR = os.path.join(SOFTWARE_DIR, "build")
IHX_PATH = os.path.join(BUILD_DIR, "firmware.ihx")
SYM_PATH = os.path.join(BUILD_DIR, "main.sym")
MAP_PATH = os.path.join(BUILD_DIR, "firmware.map")


def find_s51(explicit: str | None) -> str:
    if explicit:
        if os.path.isfile(explicit):
            return os.path.abspath(explicit)
        raise FileNotFoundError(f"未找到 s51: {explicit}")
    sdcc_home = os.environ.get("SDCC_HOME", "").strip()
    candidates: List[str] = []
    if sdcc_home:
        candidates.append(os.path.join(sdcc_home, "bin", "s51.exe"))
    candidates.append(r"D:\Tools\SDCC\bin\s51.exe")
    found = shutil.which("s51.exe") or shutil.which("s51")
    if found:
        candidates.append(found)
    for c in candidates:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    raise FileNotFoundError(
        "未找到 s51.exe。请用 --s51 指定，或设置 SDCC_HOME，"
        "或将其加入 PATH。"
    )


def ensure_firmware(force_build: bool) -> None:
    """确保 build/firmware.ihx 存在；缺失或强制时用 scons 构建。"""
    if os.path.isfile(IHX_PATH) and not force_build:
        return
    print("[build] 固件不存在或要求强制构建，执行 scons ...")
    sdcc_home = os.environ.get("SDCC_HOME", "").strip()
    cmd = ["uv", "run", "scons"]
    if sdcc_home:
        cmd.append(f"SDCC_HOME={sdcc_home}")
    elif os.path.isdir(r"D:\Tools\SDCC"):
        cmd.append(r"SDCC_HOME=D:/Tools/SDCC")
    result = subprocess.run(cmd, cwd=SOFTWARE_DIR)
    if result.returncode != 0:
        raise RuntimeError("scons 构建失败")
    if not os.path.isfile(IHX_PATH):
        raise RuntimeError(f"构建后仍未找到 {IHX_PATH}")


# --------------------------------------------------------------------
# 运行
# --------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="运行 8051 固件 ucsim 仿真测试")
    parser.add_argument("--s51", default=None, help="s51.exe 路径")
    parser.add_argument("--build", action="store_true", help="运行前强制 scons 构建")
    parser.add_argument("-k", "--filter", default=None,
                        help="只运行名字包含该子串的用例")
    parser.add_argument("--ihx", default=None, help="指定固件 .ihx 路径")
    args = parser.parse_args()

    s51_exe = find_s51(args.s51)
    ihx = os.path.abspath(args.ihx) if args.ihx else IHX_PATH
    if args.ihx is None:
        ensure_firmware(args.build)

    syms = resolve_variables(SYM_PATH, MAP_PATH) if os.path.isfile(SYM_PATH) else {}
    if not syms:
        print(f"[warn] 未找到符号表 {SYM_PATH}，变量地址使用硬编码回退值")
    variables = _resolve_variables(syms)

    tests = test_firmware.TESTS
    if args.filter:
        tests = [(n, f) for n, f in tests if args.filter.lower() in n.lower()]
    if not tests:
        print("没有匹配的测试用例")
        return 1

    print(f"s51      : {s51_exe}")
    print(f"firmware : {ihx}")
    print(f"tests    : {len(tests)} 个\n")

    passed = 0
    failed = 0
    for name, fn in tests:
        ok, detail = _run_one(name, fn, s51_exe, ihx, variables)
        if ok:
            passed += 1
            print(f"  [PASS] {name}  ({detail})")
        else:
            failed += 1
            print(f"  [FAIL] {name}\n{detail}\n")

    print(f"\n结果: {passed} 通过, {failed} 失败, 共 {passed + failed} 项")
    return 0 if failed == 0 else 1


def _resolve_variables(syms: Dict[str, int]) -> Dict[str, int]:
    out = dict(test_firmware.IRAM_VARS)
    for name in out:
        if name in syms:
            out[name] = syms[name]
    return out


def _run_one(name, fn, s51_exe, ihx, variables) -> Tuple[bool, str]:
    t0 = time.time()
    try:
        drv = S51Driver(s51_exe=s51_exe, ihx_path=ihx)
    except Exception as e:  # noqa: BLE001
        return False, f"    启动 s51 失败: {e}"
    try:
        fn(drv, variables)
        return True, f"{time.time() - t0:.2f}s"
    except AssertionError as e:
        return False, f"    断言失败: {e}"
    except S51Error as e:
        return False, f"    仿真器错误: {e}"
    except Exception:  # noqa: BLE001
        return False, traceback.format_exc().rstrip()
    finally:
        drv.close()


if __name__ == "__main__":
    sys.exit(main())
