"""固件仿真测试用例（基于 ucsim s51）。

测试策略
--------
ucsim 0.9.7 的 *fetch 断点* 在 `run` 下不生效，但 *事件断点*（内存读/写）
可以可靠地停止仿真。每个用例都让固件从复位开始运行，在固件写入某个
SFR/IRAM 时停下，`step 1` 让写入完成，再读取该位置的值进行断言。

被测固件行为：
- MusicInit 配置 Timer0/1 为模式 1、使能 ET0/ET1/ET2；
- main 启动后 DisplaySongNumber(0) 写 P0=0xF9（共阳七段码“1”）；
- PlayCurrentSong 调用 MusicPlayDual，主音轨 Numb_Track9[0]={277,219}
  经 ApplyFrequency 写 TH0/TL0 并经 UpdateSpectrum 写 P1；
  副音轨 Numb_Track6[0]={92,308} 经 ApplyFrequency2 写 RCAP2H/L；
- INT0 (P3.2) 触发切歌，CurrentSongIndex 0→1，P0 变为 0xA4（“2”）；
- INT1 (P3.3) 触发单曲/列表切换，PlaylistMode 0→1，P0 点亮小数点；
- Timer1 中断按 10 ms 节拍推进音符，NoteIndex 递增；
- PollPauseButton 在 P3.4 按下时调用 MusicPause/MusicResume 切换状态。
"""

from __future__ import annotations

import os
import sys
import time
from typing import Callable, Dict, List, Tuple

# 让脚本无论从哪里启动都能导入同目录模块
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from s51_driver import (  # noqa: E402
    S51Driver,
    SFR,
    TCON_IE0,
    TCON_IE1,
    TCON_IT0,
    TCON_IT1,
    TCON_TR0,
    TCON_TR1,
    parse_sym,
)

# --------------------------------------------------------------------
# 固件常量
# --------------------------------------------------------------------
FOSC = 12_000_000

# 第一首歌（Numb）双音轨首个音符（见 src/music.c）
FIRST_NOTE_FREQ_MAIN = 277   # Numb_Track9[0].Frequency  -> Timer0 / P1
FIRST_NOTE_FREQ_SUB = 92     # Numb_Track6[0].Frequency  -> Timer2 / P3.0

# 共阳七段码（P0 输出，0 点亮）
SEG = {0: 0xF9, 1: 0xA4, 2: 0xB0, 3: 0x99}

# 播放器状态
MUSIC_STOPPED = 0
MUSIC_PLAYING = 1
MUSIC_PAUSED = 2

# IRAM 变量地址（来自 build/main.sym，运行时再用符号表校验）
IRAM_VARS = {
    "PlaylistMode": 0x00,
    "DurationCounter": 0x08,
    "NoteIndex": 0x0A,
    "Timer0ReloadHigh": 0x06,
    "Timer0ReloadLow": 0x07,
    "Timer2ReloadHigh": 0x1A,
    "Timer2ReloadLow": 0x1B,
    "HasSecondTrack": 0x11,
    "PlayerState": 0x10,
    "CurrentSongIndex": 0x1D,
    "lastP34State": 0x1C,
    "NoteIndex2": 0x14,
}


# --------------------------------------------------------------------
# 期望值计算（与固件 src/main.c 中的逻辑保持一致）
# --------------------------------------------------------------------
def timer_reload(frequency: int) -> int:
    """ApplyFrequency / ApplyFrequency2 的 16 位重载值。"""
    count = (FOSC // 24) // frequency
    if count > 65535:
        count = 65535
    return 65536 - count


def reload_to_frequency(reload: int) -> float:
    """由 16 位重载值反推蜂鸣器频率（Hz）。

    Timer 在模式 1 下每个机器周期（FOSC/12）自增，P3.x 在每次中断翻转，
    故半周期 = reload 个机器周期，频率 = (FOSC/12) / (2*reload) = FOSC/24/reload。
    """
    count = 65536 - reload
    if count <= 0:
        return 0.0
    return (FOSC / 24) / count


def assert_freq_close(reload: int, expected: int, tol_pct: float = 1.0) -> None:
    actual = reload_to_frequency(reload)
    assert abs(actual - expected) <= expected * tol_pct / 100, \
        f"频率 {actual:.2f} Hz 偏离期望 {expected} Hz 超过 {tol_pct}%"


def spectrum_leds(frequency: int) -> int:
    if frequency == 0:
        return 0x00
    bounds = [(180, 0x01), (240, 0x03), (300, 0x07), (360, 0x0F),
              (440, 0x1F), (550, 0x3F), (700, 0x7F)]
    leds = 0xFF
    for bound, val in bounds:
        if frequency < bound:
            leds = val
            break
    return leds


def display_seg(song: int, playlist_mode: int) -> int:
    seg = SEG.get(song, 0xFF)
    if playlist_mode:
        seg &= 0x7F  # 点亮小数点
    return seg


# --------------------------------------------------------------------
# 检查点辅助
# --------------------------------------------------------------------
def _vars(syms: Dict[str, int]) -> Dict[str, int]:
    """用符号表校验 IRAM 变量地址，缺失则回退到硬编码。"""
    out = dict(IRAM_VARS)
    for name in out:
        if name in syms:
            out[name] = syms[name]
    return out


def run_to_playing(drv: S51Driver, v: Dict[str, int]) -> None:
    """从复位运行到“第一首歌开始播放”状态。

    停在 UpdateSpectrum 写 P1 之后再走一步，使 P1 写入完成；此时
    MusicInit、DisplaySongNumber(0)、PlayCurrentSong 的前半段都已执行，
    中断 (EX0/EX1/EA) 已使能。
    """
    drv.reset()
    drv.clear_breaks()
    drv.run_to_write("sfr", "w", SFR.P1)   # UpdateSpectrum: P1 = leds
    drv.step(1)


def run_to_player_playing(drv: S51Driver, v: Dict[str, int]) -> None:
    """进一步运行到 PlayerState = MusicPlaying 写入完成。"""
    run_to_playing(drv, v)
    # P1 写入之后，紧接着 ApplyFrequency2、TR1=1，然后 PlayerState=Playing
    drv.run_to_write("iram", "w", v["PlayerState"])
    drv.step(1)


# --------------------------------------------------------------------
# 测试用例
# --------------------------------------------------------------------
def test_music_init(drv: S51Driver, v: Dict[str, int]) -> None:
    """MusicInit 应将 Timer0/1 设为模式 1，并使能 ET0/ET1/ET2；
    main 还应使能 EA、EX0、EX1。"""
    run_to_playing(drv, v)
    assert drv.read_sfr(SFR.TMOD) == 0x11, \
        f"TMOD 应为 0x11，实际 0x{drv.read_sfr(SFR.TMOD):02x}"
    ie = drv.read_sfr(SFR.IE)
    # EA + ET2 + ET1 + EX1 + ET0 + EX0 = 0x80+0x20+0x08+0x04+0x02+0x01
    assert ie == 0xAF, f"IE 应为 0xAF，实际 0x{ie:02x}"
    # IT0/IT1 为下降沿触发
    tcon = drv.read_sfr(SFR.TCON)
    assert tcon & TCON_IT0, "IT0 应为 1（下降沿触发）"
    assert tcon & TCON_IT1, "IT1 应为 1（下降沿触发）"


def test_display_song_number(drv: S51Driver, v: Dict[str, int]) -> None:
    """开机显示第 1 首歌：P0 = SEG_1 = 0xF9。"""
    drv.reset()
    drv.clear_breaks()
    drv.run_to_write("sfr", "w", SFR.P0)   # DisplaySongNumber: P0 = seg
    drv.step(1)
    assert drv.read_sfr(SFR.P0) == SEG[0], \
        f"P0 应为 0x{SEG[0]:02x}，实际 0x{drv.read_sfr(SFR.P0):02x}"


def test_spectrum_first_note(drv: S51Driver, v: Dict[str, int]) -> None:
    """主音轨首个音符 277 Hz 对应频谱 LED = 0x07。"""
    run_to_playing(drv, v)
    expected = spectrum_leds(FIRST_NOTE_FREQ_MAIN)
    assert drv.read_sfr(SFR.P1) == expected, \
        f"P1 应为 0x{expected:02x}，实际 0x{drv.read_sfr(SFR.P1):02x}"


def test_timer0_reload_first_note(drv: S51Driver, v: Dict[str, int]) -> None:
    """ApplyFrequency(277) 应将 TH0/TL0 设为主音轨首音对应的重载值，
    且 SFR 与 IRAM 缓存一致，反推频率应接近 277 Hz。"""
    drv.reset()
    drv.clear_breaks()
    # 停在 ApplyFrequency 写 TL0 的指令前（此时 TR0 尚未置 1，TH0/TL0 静止）
    drv.run_to_write("sfr", "w", SFR.TL0)
    drv.step(1)
    th0 = drv.read_sfr(SFR.TH0)
    tl0 = drv.read_sfr(SFR.TL0)
    cache_h = drv.read_iram(v["Timer0ReloadHigh"])
    cache_l = drv.read_iram(v["Timer0ReloadLow"])
    assert th0 == cache_h, \
        f"TH0(0x{th0:02x}) 应与缓存 Timer0ReloadHigh(0x{cache_h:02x}) 一致"
    assert tl0 == cache_l, \
        f"TL0(0x{tl0:02x}) 应与缓存 Timer0ReloadLow(0x{cache_l:02x}) 一致"
    assert_freq_close((th0 << 8) | tl0, FIRST_NOTE_FREQ_MAIN)


def test_timer2_reload_first_note(drv: S51Driver, v: Dict[str, int]) -> None:
    """ApplyFrequency2(92) 应将 RCAP2H/RCAP2L 设为副音轨首音对应的重载值，
    反推频率应接近 92 Hz。"""
    drv.reset()
    drv.clear_breaks()
    drv.run_to_write("sfr", "w", SFR.RCAP2L)
    drv.step(1)
    rcap2h = drv.read_sfr(SFR.RCAP2H)
    rcap2l = drv.read_sfr(SFR.RCAP2L)
    cache_h = drv.read_iram(v["Timer2ReloadHigh"])
    cache_l = drv.read_iram(v["Timer2ReloadLow"])
    assert rcap2h == cache_h, \
        f"RCAP2H(0x{rcap2h:02x}) 应与缓存 Timer2ReloadHigh(0x{cache_h:02x}) 一致"
    assert rcap2l == cache_l, \
        f"RCAP2L(0x{rcap2l:02x}) 应与缓存 Timer2ReloadLow(0x{cache_l:02x}) 一致"
    assert_freq_close((rcap2h << 8) | rcap2l, FIRST_NOTE_FREQ_SUB)


def test_player_state_playing(drv: S51Driver, v: Dict[str, int]) -> None:
    """PlayCurrentSong 后 PlayerState = MusicPlaying，HasSecondTrack = 1。"""
    run_to_player_playing(drv, v)
    assert drv.read_iram(v["PlayerState"]) == MUSIC_PLAYING
    assert drv.read_iram(v["HasSecondTrack"]) == 1


def test_int0_song_switch(drv: S51Driver, v: Dict[str, int]) -> None:
    """INT0 触发切歌：CurrentSongIndex 0→1，P0 = SEG_2 = 0xA4。"""
    run_to_player_playing(drv, v)
    drv.clear_breaks()
    drv.trigger_int0(pin_low=True)
    drv.run_to_write("sfr", "w", SFR.P0)   # Int0ISR -> DisplaySongNumber
    drv.step(1)
    assert drv.read_iram(v["CurrentSongIndex"]) == 1, "CurrentSongIndex 应为 1"
    assert drv.read_sfr(SFR.P0) == SEG[1], \
        f"P0 应为 0x{SEG[1]:02x}，实际 0x{drv.read_sfr(SFR.P0):02x}"


def test_int1_playlist_toggle(drv: S51Driver, v: Dict[str, int]) -> None:
    """INT1 触发单曲/列表切换：PlaylistMode 0→1，P0 点亮小数点。"""
    run_to_player_playing(drv, v)
    drv.clear_breaks()
    drv.trigger_int1(pin_low=True)
    drv.run_to_write("sfr", "w", SFR.P0)   # Int1ISR -> DisplaySongNumber
    drv.step(1)
    assert drv.read_iram(v["PlaylistMode"]) == 1, "PlaylistMode 应为 1"
    expected = display_seg(song=0, playlist_mode=1)
    assert drv.read_sfr(SFR.P0) == expected, \
        f"P0 应为 0x{expected:02x}（带小数点），实际 0x{drv.read_sfr(SFR.P0):02x}"


def test_timer1_note_advance(drv: S51Driver, v: Dict[str, int]) -> None:
    """Timer1 中断应推进主音轨音符：NoteIndex 0→1。"""
    run_to_player_playing(drv, v)
    drv.clear_breaks()
    # NoteIndex 在 PlayCurrentSong 中已被写为 0；此处捕获下一次写入（Timer1ISR）
    drv.run_to_write("iram", "w", v["NoteIndex"])
    drv.step(1)
    assert drv.read_iram_u16(v["NoteIndex"]) == 1, "NoteIndex 应递增到 1"


def test_pause_via_button(drv: S51Driver, v: Dict[str, int]) -> None:
    """P3.4 按下（预置 lastP34State=1）应触发 MusicPause：
    PlayerState=Paused，TR0=0，TR1=0。"""
    run_to_player_playing(drv, v)
    drv.clear_breaks()
    # 预置“上一次 P3.4=1”，本次 P3.4=0，模拟下降沿按下
    drv.write_iram(v["lastP34State"], 1)
    drv.write_sfr_bits(SFR.P3, 0x10, 0x00)  # P3.4 = 0
    drv.run_to_write("iram", "w", v["PlayerState"])  # MusicPause 写 PlayerState
    drv.step(1)
    assert drv.read_iram(v["PlayerState"]) == MUSIC_PAUSED, "PlayerState 应为 Paused"
    assert not (drv.read_sfr(SFR.TCON) & TCON_TR0), "暂停后 TR0 应为 0"
    assert not (drv.read_sfr(SFR.TCON) & TCON_TR1), "暂停后 TR1 应为 0"


def test_resume_via_button(drv: S51Driver, v: Dict[str, int]) -> None:
    """在 Paused 状态下按下 P3.4 应触发 MusicResume：
    PlayerState=Playing，TR0=1，TR1=1。

    为避免按钮释放时序问题，直接注入 Paused 状态（清 TR0/TR1），
    再用预置 lastP34State=1 + P3.4=0 触发 PollPauseButton 走 MusicResume 分支。
    """
    run_to_player_playing(drv, v)
    drv.clear_breaks()
    # 注入 Paused 状态：PlayerState=Paused，并清 TR0/TR1 模拟暂停
    drv.write_iram(v["PlayerState"], MUSIC_PAUSED)
    drv.write_sfr_bits(SFR.TCON, TCON_TR0 | TCON_TR1, 0x00)
    # 预置按下条件
    drv.write_iram(v["lastP34State"], 1)
    drv.write_sfr_bits(SFR.P3, 0x10, 0x00)  # P3.4 = 0
    drv.run_to_write("iram", "w", v["PlayerState"])  # MusicResume 写 PlayerState
    drv.step(1)
    assert drv.read_iram(v["PlayerState"]) == MUSIC_PLAYING, "PlayerState 应为 Playing"
    assert drv.read_sfr(SFR.TCON) & TCON_TR0, "恢复后 TR0 应为 1"
    assert drv.read_sfr(SFR.TCON) & TCON_TR1, "恢复后 TR1 应为 1"


# --------------------------------------------------------------------
# 测试注册表
# --------------------------------------------------------------------
TESTS: List[Tuple[str, Callable[[S51Driver, Dict[str, int]], None]]] = [
    ("test_music_init", test_music_init),
    ("test_display_song_number", test_display_song_number),
    ("test_spectrum_first_note", test_spectrum_first_note),
    ("test_timer0_reload_first_note", test_timer0_reload_first_note),
    ("test_timer2_reload_first_note", test_timer2_reload_first_note),
    ("test_player_state_playing", test_player_state_playing),
    ("test_int0_song_switch", test_int0_song_switch),
    ("test_int1_playlist_toggle", test_int1_playlist_toggle),
    ("test_timer1_note_advance", test_timer1_note_advance),
    ("test_pause_via_button", test_pause_via_button),
    ("test_resume_via_button", test_resume_via_button),
]
