"""S51Driver -- 通过 TCP 命令控制台驱动 ucsim 的 s51 仿真器。

ucsim 0.9.7 的 fetch 断点在 `run` 下不生效，但 *事件断点*（内存读/写）
可以可靠地停止仿真，因此本驱动围绕事件断点构建测试观测点：
在固件写入某 SFR/IRAM 时停下，再 `step 1` 让写入完成，最后读取该位置
的值进行断言。

典型用法::

    drv = S51Driver(s51_exe="D:/Tools/SDCC/bin/s51.exe",
                    ihx_path="Software/build/firmware.ihx")
    drv.run_to_write("sfr", "w", SFR.P0)   # 停在写 P0 的指令前
    drv.step(1)                            # 执行该写入
    assert drv.read_sfr(SFR.P0) == 0xF9
    drv.close()
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple


# --------------------------------------------------------------------
# MCS-51 特殊功能寄存器地址（AT89C51RC2 / 标准 8052）
# --------------------------------------------------------------------
class SFR:
    P0 = 0x80
    SP = 0x81
    DPL = 0x82
    DPH = 0x83
    PCON = 0x87
    TCON = 0x88
    TMOD = 0x89
    TL0 = 0x8A
    TL1 = 0x8B
    TH0 = 0x8C
    TH1 = 0x8D
    P1 = 0x90
    SCON = 0x98
    SBUF = 0x99
    P2 = 0xA0
    IE = 0xA8
    P3 = 0xB0
    IP = 0xB8
    PSW = 0xD0
    ACC = 0xE0
    B = 0xF0
    # 8052 增加的寄存器
    T2CON = 0xC8
    RCAP2L = 0xCA
    RCAP2H = 0xCB
    TL2 = 0xCC
    TH2 = 0xCD


# TCON 位
TCON_TF1 = 0x80
TCON_TR1 = 0x40
TCON_TF0 = 0x20
TCON_TR0 = 0x10
TCON_IE1 = 0x08
TCON_IT1 = 0x04
TCON_IE0 = 0x02
TCON_IT0 = 0x01

# IE 位
IE_EA = 0x80
IE_ET2 = 0x20
IE_ES = 0x10
IE_ET1 = 0x08
IE_EX1 = 0x04
IE_ET0 = 0x02
IE_EX0 = 0x01


_STOP_RE = re.compile(r"Stop at 0x([0-9a-fA-F]+): \((\d+)\)\s*(.*)")
_HEX_BYTE_RE = re.compile(r"^[0-9a-fA-F]{2}$")
_PROMPT_RE = re.compile(r"\d+>\s*$")


class S51Error(RuntimeError):
    """s51 交互失败。"""


class S51Driver:
    """驱动一个 s51 仿真进程。

    Parameters
    ----------
    s51_exe:
        s51.exe 的路径。
    ihx_path:
        要加载的 Intel HEX 固件路径。
    xtal:
        晶振频率，传给 s51 的 -X 参数（默认 "12M"）。
    cpu:
        CPU 型号，传给 -t（默认 "51"）。
    port:
        命令控制台 TCP 端口；0 表示由系统分配一个空闲端口。
    """

    def __init__(
        self,
        s51_exe: str,
        ihx_path: str,
        xtal: str = "12M",
        cpu: str = "51",
        port: int = 0,
    ) -> None:
        self.s51_exe = s51_exe
        self.ihx_path = os.path.abspath(ihx_path)
        self.xtal = xtal
        self.cpu = cpu
        self.port = self._spawn(port)
        self._sock = self._connect(self.port)
        self._bp_counter = 0
        self._bps: List[Tuple[str, str, int]] = []
        # 丢弃启动 banner
        self._drain(timeout=0.5)

    # ----------------------------------------------------------------
    # 进程与连接
    # ----------------------------------------------------------------
    def _spawn(self, port: int) -> int:
        if port == 0:
            port = self._free_port()
        # -b 黑白无 ANSI；-z portnum 开 TCP 命令控制台；-X 晶振；-t CPU
        cmd = [
            self.s51_exe,
            "-t", self.cpu,
            "-X", self.xtal,
            "-b",
            "-z", str(port),
            self.ihx_path,
        ]
        creationflags = 0
        if os.name == "nt":
            # 避免弹黑框，并能在退出时整组结束
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        # 等待端口就绪
        deadline = time.time() + 5
        while time.time() < deadline:
            if self._proc.poll() is not None:
                raise S51Error("s51 进程启动后立即退出")
            try:
                sock = socket.create_connection(("127.0.0.1", port), timeout=0.5)
                sock.close()
                break
            except OSError:
                time.sleep(0.05)
        else:
            raise S51Error(f"无法在端口 {port} 连接到 s51")
        return port

    @staticmethod
    def _free_port() -> int:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port

    def _connect(self, port: int) -> socket.socket:
        sock = socket.socket()
        sock.connect(("127.0.0.1", port))
        sock.settimeout(0.5)
        return sock

    # ----------------------------------------------------------------
    # 底层 IO
    # ----------------------------------------------------------------
    def _drain(self, timeout: float = 0.3) -> str:
        data = b""
        self._sock.settimeout(timeout)
        try:
            while True:
                chunk = self._sock.recv(4096)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass
        except OSError:
            pass
        return data.decode(errors="replace")

    def _send(self, cmd: str, wait: float = 0.2) -> str:
        self._sock.sendall((cmd + "\n").encode())
        time.sleep(wait)
        return self._drain(timeout=0.3)

    def _send_no_wait(self, cmd: str) -> None:
        self._sock.sendall((cmd + "\n").encode())

    def _expect_prompt(self, timeout: float = 5.0) -> str:
        """读取输出直到出现命令提示符 `N> `。"""
        data = ""
        deadline = time.time() + timeout
        while time.time() < deadline:
            data += self._drain(timeout=0.2)
            if _PROMPT_RE.search(data):
                break
        return data

    # ----------------------------------------------------------------
    # 断点管理
    # ----------------------------------------------------------------
    def clear_breaks(self) -> None:
        # ucsim 0.9.7 的 `clear` 只删除 *fetch* 断点，对事件断点无效；
        # `delete`（无参数）才删除所有断点（含事件断点）。
        self._send("delete", wait=0.1)
        self._bps.clear()

    def add_event_bp(self, mem_type: str, rw: str, addr: int) -> None:
        """添加一个事件断点（内存读/写）。"""
        cmd = f"break {mem_type} {rw} {addr:#x}"
        out = self._send(cmd, wait=0.15)
        # ucsim 对事件断点不打印额外确认，忽略即可
        self._bps.append((mem_type, rw, addr))

    # ----------------------------------------------------------------
    # 运行控制
    # ----------------------------------------------------------------
    def reset(self) -> None:
        """复位 CPU。断点不受影响。"""
        self._send("reset", wait=0.2)

    def run_until_stop(self, timeout: float = 15.0) -> Dict:
        """执行 `run`，阻塞直到仿真停止（事件断点/用户停止/步进）。

        返回 dict: {"addr": int, "code": int, "reason": str, "raw": str}
        """
        self._send_no_wait("run")
        data = ""
        deadline = time.time() + timeout
        while time.time() < deadline:
            data += self._drain(timeout=0.2)
            m = _STOP_RE.search(data)
            if m:
                return {
                    "addr": int(m.group(1), 16),
                    "code": int(m.group(2)),
                    "reason": m.group(3).strip(),
                    "raw": data,
                }
        raise S51Error(f"run 在 {timeout}s 内未停止。已收到:\n{data}")

    def run_to_write(self, mem_type: str, rw: str, addr: int,
                     timeout: float = 15.0) -> Dict:
        """确保存在对 `addr` 的事件断点，然后运行直到该断点触发。"""
        if (mem_type, rw, addr) not in self._bps:
            self.add_event_bp(mem_type, rw, addr)
        return self.run_until_stop(timeout=timeout)

    def step(self, n: int = 1) -> Dict:
        """执行 n 条指令。返回停止信息。"""
        out = self._send(f"step {n}", wait=0.2 if n < 1000 else 1.0)
        m = _STOP_RE.search(out)
        if not m:
            # 步进输出有时不带 "Stop at"，退而求其次
            return {"addr": -1, "code": 0, "reason": "stepped", "raw": out}
        return {
            "addr": int(m.group(1), 16),
            "code": int(m.group(2)),
            "reason": m.group(3).strip(),
            "raw": out,
        }

    def run_for_ticks(self, ticks: int) -> None:
        """用 `tick` 推进时钟周期（硬件/定时器更新但不执行指令）。"""
        self._send(f"tick {ticks}", wait=0.3)

    # ----------------------------------------------------------------
    # 内存读写
    # ----------------------------------------------------------------
    @staticmethod
    def _parse_dump(out: str) -> List[int]:
        bytes_found: List[int] = []
        for line in out.splitlines():
            tokens = line.split()
            if not tokens or not tokens[0].startswith("0x"):
                continue
            for tok in tokens[1:]:
                if _HEX_BYTE_RE.match(tok):
                    bytes_found.append(int(tok, 16))
                else:
                    # 一旦遇到非十六进制 token（ASCII 区），结束本行
                    break
        return bytes_found

    def read_sfr(self, addr: int) -> int:
        out = self._send(f"ds {addr:#x} {addr:#x}", wait=0.15)
        bs = self._parse_dump(out)
        if not bs:
            raise S51Error(f"无法读取 SFR {addr:#x}:\n{out!r}")
        return bs[0]

    def read_sfr_range(self, start: int, end: int) -> bytes:
        out = self._send(f"ds {start:#x} {end:#x}", wait=0.15)
        return bytes(self._parse_dump(out))

    def read_iram(self, addr: int) -> int:
        out = self._send(f"di {addr:#x} {addr:#x}", wait=0.15)
        bs = self._parse_dump(out)
        if not bs:
            raise S51Error(f"无法读取 IRAM {addr:#x}:\n{out!r}")
        return bs[0]

    def read_iram_range(self, start: int, end: int) -> bytes:
        out = self._send(f"di {start:#x} {end:#x}", wait=0.15)
        return bytes(self._parse_dump(out))

    def read_iram_u16(self, addr: int) -> int:
        """读取 IRAM 中以小端存储的 16 位整数（SDCC mcs51 约定）。"""
        lo = self.read_iram(addr)
        hi = self.read_iram(addr + 1)
        return lo | (hi << 8)

    def write_sfr(self, addr: int, val: int) -> None:
        self._send(f"set memory sfr {addr:#x} {val & 0xFF:#x}", wait=0.15)

    def write_iram(self, addr: int, val: int) -> None:
        self._send(f"set memory iram {addr:#x} {val & 0xFF:#x}", wait=0.15)

    def write_sfr_bits(self, addr: int, mask: int, value: int) -> None:
        """按位写入：result = (old & ~mask) | (value & mask)。"""
        old = self.read_sfr(addr)
        new = (old & ~mask) | (value & mask)
        self.write_sfr(addr, new)

    # ----------------------------------------------------------------
    # 便捷：触发外部中断
    # ----------------------------------------------------------------
    def trigger_int0(self, pin_low: bool = True) -> None:
        """模拟 INT0 (P3.2) 下降沿：置 IE0 标志，并按需拉低 P3.2。"""
        if pin_low:
            self.write_sfr_bits(SFR.P3, 0x04, 0x00)  # 清 P3.2
        self.write_sfr_bits(SFR.TCON, TCON_IE0, TCON_IE0)  # 置 IE0

    def trigger_int1(self, pin_low: bool = True) -> None:
        """模拟 INT1 (P3.3) 下降沿。"""
        if pin_low:
            self.write_sfr_bits(SFR.P3, 0x08, 0x00)  # 清 P3.3
        self.write_sfr_bits(SFR.TCON, TCON_IE1, TCON_IE1)

    # ----------------------------------------------------------------
    # 生命周期
    # ----------------------------------------------------------------
    def close(self) -> None:
        try:
            self._send_no_wait("kill")
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def __enter__(self) -> "S51Driver":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# --------------------------------------------------------------------
# 固件符号表解析
# --------------------------------------------------------------------
def parse_sym(path: str) -> Dict[str, int]:
    """解析 SDCC .sym 文件，返回 {符号名: 段内相对地址}。

    注意：CODE 段符号的地址是链接后的绝对地址；但 DSEG（IRAM 数据段）
    符号的地址是 *段内相对地址*，需要加上 DSEG 的链接基址才是真实 IRAM
    地址。请用 `resolve_variables` 获取 IRAM 变量的绝对地址。

    .sym 每行形如::

        19 _MusicInit                                                 00030B GR
        6 _PlayerState                                                000010 R
    """
    syms: Dict[str, int] = {}
    if not os.path.exists(path):
        return syms
    with open(path, "r", errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            name = parts[1]
            if not name.startswith("_"):
                continue
            try:
                addr = int(parts[-2], 16)
            except ValueError:
                continue
            syms[name[1:]] = addr
    return syms


def parse_map_areas(map_path: str) -> Dict[str, Dict[str, int]]:
    """解析 SDCC 链接器 .map 文件，返回 {段名: {符号名: 绝对地址}}。

    仅提取公共（global）符号的绝对地址，用于推算段基址。
    """
    areas: Dict[str, Dict[str, int]] = {}
    if not os.path.exists(map_path):
        return areas
    area_header = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s*=")
    sym_line = re.compile(r"^\s*([0-9A-Fa-f]+)\s+(_\S+)\s+\S+")
    current: Optional[str] = None
    with open(map_path, "r", errors="replace") as f:
        for line in f:
            m = area_header.match(line)
            if m:
                current = m.group(1)
                areas[current] = {}
                continue
            if current is None:
                continue
            sm = sym_line.match(line)
            if sm:
                addr = int(sm.group(1), 16)
                name = sm.group(2)[1:]  # 去掉前导下划线
                areas[current][name] = addr
    return areas


def resolve_variables(sym_path: str, map_path: str) -> Dict[str, int]:
    """返回 IRAM 变量的绝对地址。

    SDCC 的 .sym 文件中 DSEG 段符号是段内相对地址，需要加上 DSEG 的
    链接基址。基址通过 .map 中公共符号的绝对地址与 .sym 中的相对地址
    之差求得。
    """
    rel = parse_sym(sym_path)
    if not rel:
        return {}
    areas = parse_map_areas(map_path)
    dseg_pub = areas.get("DSEG", {})
    base = 0
    if dseg_pub:
        for name, abs_addr in dseg_pub.items():
            if name in rel:
                base = abs_addr - rel[name]
                break
    return {name: addr + base for name, addr in rel.items()}
