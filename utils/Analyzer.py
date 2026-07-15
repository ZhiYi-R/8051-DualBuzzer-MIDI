#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MIDI 文件字面分析报告生成器

rtmidi 是实时 MIDI I/O 库，不直接提供读取 .mid 文件的接口；
本脚本使用 rtmidi.midiconstants 中的常量识别 MIDI 事件，并自行实现 SMF 解析器。
"""

import argparse
import re
import struct
from collections import defaultdict, Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import rtmidi.midiconstants as mc

DEFAULT_INPUT_DIR = "Resources"
DEFAULT_OUTPUT_FILE = "utils/midi_analysis_report.txt"

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

GM_INSTRUMENTS = dict(enumerate([
    "Acoustic Grand Piano",           "Bright Acoustic Piano",         "Electric Grand Piano",
    "Honky-tonk Piano",               "Electric Piano 1",              "Electric Piano 2",
    "Harpsichord",                    "Clavinet",                      "Celesta",
    "Glockenspiel",                   "Music Box",                     "Vibraphone",
    "Marimba",                        "Xylophone",                     "Tubular Bells",
    "Dulcimer",                       "Drawbar Organ",                 "Percussive Organ",
    "Rock Organ",                     "Church Organ",                  "Reed Organ",
    "Accordion",                      "Harmonica",                     "Tango Accordion",
    "Acoustic Guitar (nylon)",        "Acoustic Guitar (steel)",       "Electric Guitar (jazz)",
    "Electric Guitar (clean)",        "Electric Guitar (muted)",       "Overdriven Guitar",
    "Distortion Guitar",              "Guitar Harmonics",              "Acoustic Bass",
    "Electric Bass (finger)",         "Electric Bass (pick)",          "Fretless Bass",
    "Slap Bass 1",                    "Slap Bass 2",                   "Synth Bass 1",
    "Synth Bass 2",                   "Violin",                        "Viola",
    "Cello",                          "Contrabass",                    "Tremolo Strings",
    "Pizzicato Strings",              "Orchestral Harp",               "Timpani",
    "String Ensemble 1",              "String Ensemble 2",             "Synth Strings 1",
    "Synth Strings 2",                "Choir Aahs",                    "Voice Oohs",
    "Synth Voice",                    "Orchestra Hit",                 "Trumpet",
    "Trombone",                       "Tuba",                          "Muted Trumpet",
    "French Horn",                    "Brass Section",                 "Synth Brass 1",
    "Synth Brass 2",                  "Soprano Sax",                   "Alto Sax",
    "Tenor Sax",                      "Baritone Sax",                  "Oboe",
    "English Horn",                   "Bassoon",                       "Clarinet",
    "Piccolo",                        "Flute",                         "Recorder",
    "Pan Flute",                      "Blown Bottle",                  "Shakuhachi",
    "Whistle",                        "Ocarina",                       "Lead 1 (square)",
    "Lead 2 (sawtooth)",              "Lead 3 (calliope)",             "Lead 4 (chiff)",
    "Lead 5 (charang)",               "Lead 6 (voice)",                "Lead 7 (fifths)",
    "Lead 8 (bass + lead)",           "Pad 1 (new age)",               "Pad 2 (warm)",
    "Pad 3 (polysynth)",              "Pad 4 (choir)",                 "Pad 5 (bowed)",
    "Pad 6 (metallic)",               "Pad 7 (halo)",                  "Pad 8 (sweep)",
    "FX 1 (rain)",                    "FX 2 (soundtrack)",             "FX 3 (crystal)",
    "FX 4 (atmosphere)",              "FX 5 (brightness)",             "FX 6 (goblins)",
    "FX 7 (echoes)",                  "FX 8 (sci-fi)",                 "Sitar",
    "Banjo",                          "Shamisen",                      "Koto",
    "Kalimba",                        "Bag Pipe",                      "Fiddle",
    "Shanai",                         "Tinkle Bell",                   "Agogo",
    "Steel Drums",                    "Woodblock",                     "Taiko Drum",
    "Melodic Tom",                    "Synth Drum",                    "Reverse Cymbal",
    "Guitar Fret Noise",              "Breath Noise",                  "Seashore",
    "Bird Tweet",                     "Telephone Ring",                "Helicopter",
    "Applause",                       "Gunshot",
]))

TEXT_META_TYPES = {
    mc.TEXT,
    mc.COPYRIGHT,
    mc.SEQUENCE_NAME,
    mc.INSTRUMENT_NAME,
    mc.LYRIC,
    mc.MARKER,
    mc.CUEPOINT,
    mc.PROGRAM_NAME,
    mc.DEVICE_NAME,
}

META_NAME_CN: Dict[int, str] = {
    0x00: "序列编号",
    0x01: "文本",
    0x02: "版权",
    0x03: "音轨名称",
    0x04: "乐器名称",
    0x05: "歌词",
    0x06: "标记",
    0x07: "提示点",
    0x08: "程序名称",
    0x09: "设备名称",
    0x20: "MIDI 通道前缀",
    0x21: "MIDI 端口",
    0x2F: "音轨结束",
    0x51: "速度",
    0x54: "SMPTE 偏移",
    0x58: "拍号",
    0x59: "调号",
    0x7F: "序列器特定",
}


class MidiEvent:
    """单个 MIDI 事件"""

    __slots__ = (
        "abs_tick",
        "delta",
        "status",
        "channel",
        "data1",
        "data2",
        "meta_type",
        "meta_data",
        "sysex",
    )

    def __init__(
        self,
        abs_tick: int,
        delta: int,
        status: int,
        channel: Optional[int] = None,
        data1: Optional[int] = None,
        data2: Optional[int] = None,
        meta_type: Optional[int] = None,
        meta_data: Optional[bytes] = None,
        sysex: bool = False,
    ) -> None:
        self.abs_tick = abs_tick
        self.delta = delta
        self.status = status
        self.channel = channel
        self.data1 = data1
        self.data2 = data2
        self.meta_type = meta_type
        self.meta_data = meta_data or b""
        self.sysex = sysex


def note_name(note_num: int) -> str:
    """MIDI 音高编号转音名"""
    return f"{NOTE_NAMES[note_num % 12]}{(note_num // 12) - 1}"


def note_frequency(note_num: int) -> float:
    """MIDI 音高编号转频率（A4=440Hz 等程律）"""
    return 440.0 * (2.0 ** ((note_num - 69) / 12.0))


def key_signature_str(sf: int, mi: int) -> str:
    """调号 Meta 事件转字符串（sf 为有符号数）"""
    # sf 为 8 位有符号数：正为升号数，负为降号数
    if sf > 127:
        sf -= 256
    major_minor = "大调" if mi == 0 else "小调"
    if sf == 0:
        return f"0 个升降号，{major_minor}"
    if sf > 0:
        return f"{sf} 个升号，{major_minor}"
    return f"{-sf} 个降号，{major_minor}"


def instrument_name(program_num: int) -> str:
    """根据 General MIDI 程序号返回乐器名称"""
    return GM_INSTRUMENTS.get(program_num, f"Unknown Program {program_num}")


def max_polyphony(notes: List[Dict[str, Any]]) -> int:
    """根据音符起止时间计算最大同时发声数"""
    if not notes:
        return 0
    events = []
    for n in notes:
        events.append((n["start"], 1))
        events.append((n["end"], -1))
    # 同一 tick 先结束再开始，避免边界重叠
    events.sort(key=lambda x: (x[0], x[1]))
    active = 0
    peak = 0
    for _, delta in events:
        active += delta
        if active > peak:
            peak = active
    return peak


def classify_track(
    channel: Optional[int],
    program: Optional[int],
    note_count: int,
    min_note: Optional[int],
    max_note: Optional[int],
    avg_note: Optional[float],
    lyric_count: int,
    polyphony: int,
    distinct_notes: int,
) -> Tuple[str, str]:
    """根据音轨特征判断乐器角色，返回 (role, reason)"""
    if note_count == 0:
        return "silent", "无音符"

    if channel == 9:
        return "drums", "MIDI 通道 9 为通用打击乐通道"

    if lyric_count > 0:
        instr = instrument_name(program) if program is not None else "未知乐器"
        return "vocal", f"含 {lyric_count} 个歌词 Meta 事件，乐器 {instr}"

    # 低音判断：GM 贝斯类或音域整体偏低
    is_bass_program = program is not None and 32 <= program <= 39
    low_range = max_note is not None and max_note <= 55 and avg_note is not None and avg_note <= 48
    if is_bass_program or low_range:
        instr = instrument_name(program) if program is not None else "未知乐器"
        return "bass", f"乐器 {instr}，音域 {note_name(min_note)}-{note_name(max_note)}，平均音高 {avg_note:.1f}"

    # 主旋律候选：GM 主奏/独奏类乐器、音域中等偏高且单声部
    lead_programs = set(range(0, 8)) | set(range(24, 32)) | set(range(40, 56)) | set(range(64, 88))
    is_lead = program is not None and program in lead_programs
    is_main_range = max_note is not None and max_note >= 60 and avg_note is not None and avg_note >= 55
    is_main_poly = polyphony <= 2 or (distinct_notes <= 6 and polyphony <= 4)
    if is_lead and is_main_range and is_main_poly:
        instr = instrument_name(program) if program is not None else "未知乐器"
        return "main", f"乐器 {instr}，音域 {note_name(min_note)}-{note_name(max_note)}，平均音高 {avg_note:.1f}，多声部数 {polyphony}"

    if is_lead and polyphony > 2:
        instr = instrument_name(program) if program is not None else "未知乐器"
        return "chords", f"乐器 {instr}，多声部数 {polyphony}，属和弦/伴奏"

    instr = instrument_name(program) if program is not None else "未知乐器"
    return "other", f"乐器 {instr}，音域 {note_name(min_note)}-{note_name(max_note)}，平均音高 {avg_note:.1f}"


ROLE_DISPLAY = {
    "silent": "静音",
    "drums": "打击乐",
    "vocal": "人声/主旋律",
    "bass": "Bass 线",
    "main": "主旋律",
    "chords": "和弦/伴奏",
    "other": "其他/伴奏",
}


def decode_text(data: bytes) -> str:
    """解码 Meta 事件文本，兼容 Latin-1 避免解析失败"""
    return data.decode("latin-1", errors="replace").strip()


def read_var_length(data: bytes, pos: int) -> Tuple[int, int]:
    """读取可变长度值（VLQ）"""
    value = 0
    while True:
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 0x7F)
        if not (byte & 0x80):
            break
    return value, pos


def get_all_midi(root_directory: Path) -> List[Path]:
    """递归扫描目录，返回所有 .mid 文件路径"""
    if not root_directory.exists():
        raise FileNotFoundError(f"目录 {root_directory} 不存在")
    if not root_directory.is_dir():
        raise NotADirectoryError(f"{root_directory} 不是目录")
    files = {p.resolve() for p in root_directory.rglob("*.mid")} | {p.resolve() for p in root_directory.rglob("*.MID")}
    return sorted(files)


def parse_midi_file(path: Path) -> Dict[str, Any]:
    """解析标准 MIDI 文件，返回文件头与原始事件列表"""
    data = path.read_bytes()
    pos = 0

    if data[0:4] != mc.FILE_HEADER.encode("ascii"):
        raise ValueError(f"{path} 不是标准 MIDI 文件")

    header_len, fmt, num_tracks, division = struct.unpack_from(">4sIHHH", data, 0)[1:]
    # 上面使用 >4sIHHH 解包：4s MThd + I 长度 + H H H
    pos = 8 + header_len

    tracks: List[List[MidiEvent]] = []
    for track_index in range(num_tracks):
        if data[pos : pos + 4] != mc.TRACK_HEADER.encode("ascii"):
            raise ValueError(f"{path} 音轨 {track_index} 头错误")
        track_len = struct.unpack_from(">I", data, pos + 4)[0]
        track_data = data[pos + 8 : pos + 8 + track_len]
        pos += 8 + track_len
        tracks.append(parse_track(track_data, track_index))

    return {
        "path": path,
        "format": fmt,
        "num_tracks": num_tracks,
        "division": division,
        "tracks": tracks,
    }


def parse_track(track_data: bytes, track_index: int) -> List[MidiEvent]:
    """解析单个音轨的所有事件"""
    events: List[MidiEvent] = []
    pos = 0
    end = len(track_data)
    running_status = 0
    abs_tick = 0

    while pos < end:
        delta, pos = read_var_length(track_data, pos)
        abs_tick += delta

        byte = track_data[pos]
        pos += 1

        if byte < 0x80:
            status = running_status
            data1 = byte
            if status == 0:
                raise ValueError(f"音轨 {track_index} 在 tick {abs_tick} 处缺少运行状态")
        else:
            status = byte
            # 只有通道声部消息（0x80-0xEF）才更新运行状态
            if 0x80 <= status <= 0xEF:
                running_status = status
            data1 = None

        # Meta 事件
        if status == 0xFF:
            meta_type = track_data[pos]
            pos += 1
            length, pos = read_var_length(track_data, pos)
            meta_data = track_data[pos : pos + length]
            pos += length
            events.append(
                MidiEvent(
                    abs_tick,
                    delta,
                    status,
                    meta_type=meta_type,
                    meta_data=meta_data,
                )
            )
            continue

        # 系统专属消息（SysEx）
        if status in (0xF0, 0xF7):
            length, pos = read_var_length(track_data, pos)
            sysex_data = track_data[pos : pos + length]
            pos += length
            events.append(
                MidiEvent(
                    abs_tick,
                    delta,
                    status,
                    meta_data=sysex_data,
                    sysex=True,
                )
            )
            continue

        # 其他系统消息（在 SMF 中极少出现，直接跳过对应数据字节）
        if status >= 0xF1:
            if status in (0xF1, 0xF3):
                pos += 1
            elif status == 0xF2:
                pos += 2
            continue

        # 通道声部消息
        hi = status & 0xF0
        channel = status & 0x0F

        if data1 is None:
            data1 = track_data[pos]
            pos += 1

        if hi in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
            data2 = track_data[pos]
            pos += 1
            events.append(
                MidiEvent(
                    abs_tick,
                    delta,
                    status,
                    channel=channel,
                    data1=data1,
                    data2=data2,
                )
            )
        elif hi in (0xC0, 0xD0):
            events.append(
                MidiEvent(
                    abs_tick,
                    delta,
                    status,
                    channel=channel,
                    data1=data1,
                )
            )

    return events


def build_tempo_map(file_info: Dict[str, Any]) -> List[Tuple[int, int]]:
    """从所有音轨的速度事件中构建时间-速度映射表"""
    tempos: List[Tuple[int, int]] = []
    for track in file_info["tracks"]:
        for ev in track:
            if ev.status == 0xFF and ev.meta_type == mc.TEMPO and len(ev.meta_data) == 3:
                us_per_qn = (ev.meta_data[0] << 16) | (ev.meta_data[1] << 8) | ev.meta_data[2]
                tempos.append((ev.abs_tick, us_per_qn))
    if not tempos:
        tempos.append((0, 500000))  # 默认 120 BPM
    tempos.sort(key=lambda x: x[0])
    return tempos


def tick_to_ms(tick: int, tempo_map: List[Tuple[int, int]], division: int) -> float:
    """根据速度映射表把 tick 转换为毫秒"""
    if division == 0:
        return 0.0

    ms = 0.0
    current_tick = 0
    current_us_per_qn = 500000

    for t, us_per_qn in tempo_map:
        if t >= tick:
            break
        ms += (t - current_tick) * (current_us_per_qn / division / 1000.0)
        current_tick = t
        current_us_per_qn = us_per_qn

    ms += (tick - current_tick) * (current_us_per_qn / division / 1000.0)
    return ms


def analyze_track(
    track: List[MidiEvent],
    track_index: int,
    tempo_map: List[Tuple[int, int]],
    division: int,
) -> Dict[str, Any]:
    """对单个音轨进行统计分析"""
    channels: set = set()
    programs: List[Tuple[int, int, int]] = []  # (tick, channel, program)
    control_counts: Dict[Tuple[int, int], int] = defaultdict(int)
    event_counts: Dict[str, int] = defaultdict(int)
    meta_list: List[Tuple[int, str, str]] = []  # (tick, 类型名, 内容)

    track_name: Optional[str] = None
    instrument_name: Optional[str] = None

    active_notes: Dict[Tuple[int, int], List[Tuple[int, int]]] = defaultdict(list)
    notes: List[Dict[str, Any]] = []
    unmatched_note_offs: int = 0

    for ev in track:
        if ev.status == 0xFF:
            name = META_NAME_CN.get(ev.meta_type, f"Meta 0x{ev.meta_type:02X}")
            text = ""
            if ev.meta_type in TEXT_META_TYPES:
                text = decode_text(ev.meta_data)
                if ev.meta_type == mc.SEQUENCE_NAME and track_name is None:
                    track_name = text
                if ev.meta_type == mc.INSTRUMENT_NAME and instrument_name is None:
                    instrument_name = text
            elif ev.meta_type == mc.TEMPO and len(ev.meta_data) == 3:
                us_per_qn = (ev.meta_data[0] << 16) | (ev.meta_data[1] << 8) | ev.meta_data[2]
                bpm = 60000000.0 / us_per_qn
                text = f"{us_per_qn} us/四分音符，约 {bpm:.2f} BPM"
            elif ev.meta_type == mc.TIME_SIGNATURE and len(ev.meta_data) == 4:
                nn, dd, cc, bb = ev.meta_data
                text = f"{nn}/{2 ** dd}，每四分音符 {cc} 个 MIDI 时钟，每 24 个时钟 {bb} 个 32 分音符"
            elif ev.meta_type == mc.KEY_SIGNATURE and len(ev.meta_data) == 2:
                sf, mi = ev.meta_data
                text = key_signature_str(sf, mi)
            meta_list.append((ev.abs_tick, name, text))
            event_counts[f"Meta:{name}"] += 1

        elif ev.sysex:
            event_counts["SysEx"] += 1

        else:
            hi = ev.status & 0xF0
            ch = ev.channel
            if ch is not None:
                channels.add(ch)

            if hi == mc.NOTE_ON:
                if ev.data2 and ev.data2 > 0:
                    event_counts["NoteOn"] += 1
                    active_notes[(ch, ev.data1)].append((ev.abs_tick, ev.data2))
                else:
                    event_counts["NoteOff(vel=0)"] += 1
                    key = (ch, ev.data1)
                    if active_notes[key]:
                        start_tick, velocity = active_notes[key].pop()
                        notes.append(
                            {
                                "note": ev.data1,
                                "start": start_tick,
                                "end": ev.abs_tick,
                                "velocity": velocity,
                                "channel": ch,
                            }
                        )
                    else:
                        unmatched_note_offs += 1

            elif hi == mc.NOTE_OFF:
                event_counts["NoteOff"] += 1
                key = (ch, ev.data1)
                if active_notes[key]:
                    start_tick, velocity = active_notes[key].pop()
                    notes.append(
                        {
                            "note": ev.data1,
                            "start": start_tick,
                            "end": ev.abs_tick,
                            "velocity": velocity,
                            "channel": ch,
                        }
                    )
                else:
                    unmatched_note_offs += 1

            elif hi == mc.PROGRAM_CHANGE:
                event_counts["ProgramChange"] += 1
                programs.append((ev.abs_tick, ch, ev.data1))

            elif hi == mc.CONTROL_CHANGE:
                event_counts["ControlChange"] += 1
                control_counts[(ch, ev.data1)] += 1

            elif hi == mc.PITCH_BEND:
                event_counts["PitchBend"] += 1

            elif hi == mc.POLY_AFTERTOUCH:
                event_counts["PolyAftertouch"] += 1

            elif hi == mc.CHANNEL_AFTERTOUCH:
                event_counts["ChannelAftertouch"] += 1

            else:
                event_counts[f"0x{ev.status:02X}"] += 1

    # 未匹配的 NoteOn 按音轨结束时间收尾
    end_tick = track[-1].abs_tick if track else 0
    for (ch, note), stack in active_notes.items():
        for start_tick, velocity in stack:
            notes.append(
                {
                    "note": note,
                    "start": start_tick,
                    "end": end_tick,
                    "velocity": velocity,
                    "channel": ch,
                }
            )

    notes.sort(key=lambda x: x["start"])

    note_numbers = [n["note"] for n in notes]
    min_note = min(note_numbers) if note_numbers else None
    max_note = max(note_numbers) if note_numbers else None
    unique_notes = sorted(set(note_numbers)) if note_numbers else []

    return {
        "index": track_index,
        "name": track_name or instrument_name or "未命名",
        "instrument": instrument_name,
        "channels": sorted(channels),
        "programs": programs,
        "control_counts": dict(control_counts),
        "event_counts": dict(event_counts),
        "meta_list": meta_list,
        "notes": notes,
        "note_count": len(notes),
        "min_note": min_note,
        "max_note": max_note,
        "unique_notes": unique_notes,
        "unmatched_note_offs": unmatched_note_offs,
        "length_ticks": end_tick,
    }


def analyze_file(file_info: Dict[str, Any]) -> Dict[str, Any]:
    """分析整个 MIDI 文件"""
    tempo_map = build_tempo_map(file_info)
    track_infos = [
        analyze_track(track, i, tempo_map, file_info["division"])
        for i, track in enumerate(file_info["tracks"])
    ]

    tempos = []
    for tick, us_per_qn in tempo_map:
        bpm = 60000000.0 / us_per_qn
        tempos.append((tick, us_per_qn, bpm))

    time_sigs = []
    key_sigs = []
    for track in file_info["tracks"]:
        for ev in track:
            if ev.status == 0xFF and ev.meta_type == mc.TIME_SIGNATURE and len(ev.meta_data) == 4:
                time_sigs.append((ev.abs_tick, ev.meta_data))
            elif ev.status == 0xFF and ev.meta_type == mc.KEY_SIGNATURE and len(ev.meta_data) == 2:
                key_sigs.append((ev.abs_tick, ev.meta_data))

    return {
        "path": file_info["path"],
        "format": file_info["format"],
        "num_tracks": file_info["num_tracks"],
        "division": file_info["division"],
        "tempos": tempos,
        "time_signatures": time_sigs,
        "key_signatures": key_sigs,
        "tracks": track_infos,
    }


def format_file_report(
    info: Dict[str, Any], note_list: bool = False, max_notes: int = 0
) -> str:
    """格式化单个 MIDI 文件的分析报告"""
    lines: List[str] = []
    p = info["path"]
    tempo_map = [(t, us) for t, us, _ in info["tempos"]]
    lines.append("=" * 80)
    lines.append(f"文件：{p.name}")
    lines.append(f"完整路径：{p.resolve().as_posix()}")
    lines.append(f"SMF 格式：{info['format']}（0=单音轨，1=多音轨，2=独立音轨）")
    lines.append(f"音轨数量：{info['num_tracks']}")
    lines.append(f"分度值（Ticks/四分音符）：{info['division']}")

    lines.append("-" * 80)
    lines.append("速度事件（Tempo）：")
    if info["tempos"]:
        for tick, us_per_qn, bpm in info["tempos"]:
            lines.append(f"  tick {tick:>8} : {us_per_qn} us/四分音符 ≈ {bpm:.2f} BPM")
    else:
        lines.append("  无速度事件，使用默认 120 BPM")

    if info["time_signatures"]:
        lines.append("拍号事件：")
        for tick, data in info["time_signatures"]:
            nn, dd, cc, bb = data
            lines.append(f"  tick {tick:>8} : {nn}/{2 ** dd}")

    if info["key_signatures"]:
        lines.append("调号事件：")
        for tick, data in info["key_signatures"]:
            sf, mi = data
            lines.append(f"  tick {tick:>8} : {key_signature_str(sf, mi)}")

    for track in info["tracks"]:
        lines.append("-" * 80)
        lines.append(f"音轨 {track['index']}: {track['name']}")
        if track["instrument"]:
            lines.append(f"  乐器名称：{track['instrument']}")
        lines.append(f"  通道：{track['channels'] if track['channels'] else '无'}")
        lines.append(f"  音轨时长：{track['length_ticks']} ticks")

        if track["programs"]:
            lines.append("  程序变更：")
            for tick, ch, prog in track["programs"]:
                lines.append(f"    tick {tick:>8} : 通道 {ch} -> Program {prog}")

        if track["control_counts"]:
            lines.append("  控制器使用（通道, 控制器编号 : 次数）：")
            for (ch, ctrl), cnt in track["control_counts"].items():
                lines.append(f"    通道 {ch}, 控制器 {ctrl} : {cnt} 次")

        event_counts = track["event_counts"]
        if event_counts:
            lines.append("  事件统计：")
            for name, cnt in sorted(event_counts.items(), key=lambda x: -x[1]):
                lines.append(f"    {name}: {cnt}")

        lines.append(f"  音符数量：{track['note_count']}")
        if track["note_count"]:
            lines.append(
                f"  音域：{note_name(track['min_note'])} ({track['min_note']}) "
                f"~ {note_name(track['max_note'])} ({track['max_note']})"
            )
            lines.append(f"  不同音高数量：{len(track['unique_notes'])}")

        if track["unmatched_note_offs"]:
            lines.append(f"  未匹配的 NoteOff/NoteOn(vel=0)：{track['unmatched_note_offs']}")

        if track["note_count"]:
            notes = track["notes"]
            if note_list:
                lines.append("  音符列表：")
                display = notes
                if max_notes and len(notes) > max_notes:
                    display = notes[:max_notes]
                    lines.append(f"  （仅显示前 {max_notes} 个，共 {len(notes)} 个）")
                for n in display:
                    start_ms = tick_to_ms(n["start"], tempo_map, info["division"])
                    end_ms = tick_to_ms(n["end"], tempo_map, info["division"])
                    duration_ms = end_ms - start_ms
                    lines.append(
                        f"    tick {n['start']:>8} ~ {n['end']:<8} | "
                        f"{duration_ms:>7.1f} ms | "
                        f"{note_name(n['note']):>3} ({n['note']:>3}) "
                        f"{note_frequency(n['note']):>8.2f} Hz | "
                        f"vel {n['velocity']:>3} | ch {n['channel']}"
                    )
            else:
                lines.append("  前 10 个音符：")
                for n in notes[:10]:
                    start_ms = tick_to_ms(n["start"], tempo_map, info["division"])
                    end_ms = tick_to_ms(n["end"], tempo_map, info["division"])
                    duration_ms = end_ms - start_ms
                    lines.append(
                        f"    tick {n['start']:>8} ~ {n['end']:<8} | "
                        f"{duration_ms:>7.1f} ms | "
                        f"{note_name(n['note']):>3} ({n['note']:>3}) "
                        f"{note_frequency(n['note']):>8.2f} Hz | "
                        f"vel {n['velocity']:>3} | ch {n['channel']}"
                    )

    return "\n".join(lines) + "\n"


def parse_main_c(path: Path) -> Dict[str, Tuple[str, str]]:
    """从 main.c 的 MusicPlayDual 调用中提取项目使用的 Track 组合"""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(
        r"MusicPlayDual\s*\(\s*"
        r"(?P<bass>\w+)\s*,\s*\w+\s*,\s*"
        r"(?P<main>\w+)\s*,\s*\w+\s*\)",
        re.MULTILINE,
    )
    result = {}
    for match in pattern.finditer(text):
        bass = match.group("bass")
        main = match.group("main")
        song = bass.split("_")[0] if "_" in bass else ""
        if song:
            result[song] = (bass, main)
    return result


def write_markdown_report(
    infos: List[Dict[str, Any]],
    output_path: Path,
    main_c_path: Optional[Path] = None,
) -> None:
    """生成以乐器与角色判断为主的 Markdown 报告"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    project_map = parse_main_c(main_c_path) if main_c_path else {}

    def active_program(start_tick: int, program_changes: List[Tuple[int, int, int]]) -> Optional[int]:
        """返回 start_tick 时生效的 Program 号"""
        prog = None
        for tick, _, p in program_changes:
            if tick <= start_tick:
                prog = p
            else:
                break
        return prog

    def sub_units_for_file(info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """把文件拆分为可分析的子单元：Format 1 按音轨，Format 0 按通道"""
        units = []
        for track in info["tracks"]:
            track_notes = track["notes"]
            if not track_notes:
                continue
            by_channel: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
            for n in track_notes:
                by_channel[n["channel"]].append(n)
            for ch, notes in sorted(by_channel.items()):
                program_changes = [p for p in track["programs"] if p[1] == ch]
                program_counts = Counter()
                for n in notes:
                    prog = active_program(n["start"], program_changes)
                    if prog is not None:
                        program_counts[prog] += 1
                most_common_program = program_counts.most_common(1)[0][0] if program_counts else None
                first_program = program_changes[0][2] if program_changes else None
                program = most_common_program if most_common_program is not None else first_program

                note_nums = [n["note"] for n in notes]
                min_note = min(note_nums)
                max_note = max(note_nums)
                avg_note = sum(note_nums) / len(note_nums)
                polyphony = max_polyphony(notes)
                distinct = len(set(note_nums))

                # Format 0 文件里不单独拆分歌词，Meta 事件无通道
                lyric_count = 0
                if info["format"] != 0:
                    lyric_count = track["event_counts"].get("Meta:歌词", 0)

                role, reason = classify_track(
                    channel=ch,
                    program=program,
                    note_count=len(notes),
                    min_note=min_note,
                    max_note=max_note,
                    avg_note=avg_note,
                    lyric_count=lyric_count,
                    polyphony=polyphony,
                    distinct_notes=distinct,
                )

                name = track["name"]
                if info["format"] == 0:
                    name = f"{name} / Ch {ch}"

                units.append(
                    {
                        "track_index": track["index"],
                        "channel": ch,
                        "name": name,
                        "program": program,
                        "note_count": len(notes),
                        "min_note": min_note,
                        "max_note": max_note,
                        "avg_note": avg_note,
                        "distinct_notes": distinct,
                        "polyphony": polyphony,
                        "lyric_count": lyric_count,
                        "role": role,
                        "reason": reason,
                        "song": info["path"].stem,
                    }
                )
        return units

    lines = []
    lines.append("# MIDI 音轨乐器与角色分析报告")
    lines.append("")
    lines.append("## 分析说明")
    lines.append("")
    lines.append("- 使用 `rtmidi.midiconstants` 的常量自行解析 SMF（标准 MIDI 文件）。")
    lines.append("- 乐器名称依据 General MIDI（GM）音色表映射。")
    lines.append("- 判断规则：")
    lines.append("  - **Bass 线**：Program 32–39，或音域整体偏低（最高音 ≤ E3 且平均音高 ≤ 48）。")
    lines.append("  - **主旋律/人声线**：GM 主奏类乐器（钢琴/吉他/弦乐/木管/合成主奏），最高音 ≥ C4、平均音高 ≥ 55 且最大同时发声数 ≤ 2；或含有歌词 Meta 事件。")
    lines.append("  - **打击乐**：通道 9（GM 标准打击乐通道）。")
    lines.append("  - **和弦/伴奏**：主奏类乐器但多声部数 > 2。")
    lines.append("  - **其他/伴奏**：不符合上述规则。")
    lines.append("")

    if project_map:
        lines.append("## 项目代码 `MusicPlayDual` 调用对照")
        lines.append("")
        lines.append("| 歌曲 | 低音（第1参数） | 主旋律/人声（第2参数） |")
        lines.append("|---|---|---|")
        for song in ["Numb", "Payphone", "NewDivide", "WhatIveDone"]:
            if song in project_map:
                bass, main = project_map[song]
                lines.append(f"| {song} | `{bass}` | `{main}` |")
        lines.append("")

    summary = []
    for info in infos:
        p = info["path"]
        lines.append(f"## {p.name}")
        lines.append("")
        lines.append(f"- SMF 格式：{info['format']}（0=单音轨，1=多音轨，2=独立音轨）")
        lines.append(f"- 音轨数量：{info['num_tracks']}")
        lines.append(f"- 分度值：{info['division']} ticks/四分音符")
        if info["tempos"]:
            first_tempo = info["tempos"][0][1]
            first_bpm = info["tempos"][0][2]
            lines.append(f"- 初始速度：{first_tempo} us/四分音符 ≈ {first_bpm:.2f} BPM")
        if info["format"] == 0:
            lines.append("- 说明：Format 0 文件，所有事件合并在一个音轨内，因此按 MIDI 通道拆分分析。")
        lines.append("")

        units = sub_units_for_file(info)
        lines.append("| 音轨/通道 | 名称 | 乐器 | 音符数 | 音域 | 平均音高 | 多声部数 | 分类 | 判断依据 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for u in units:
            prog_str = "-"
            if u["program"] is not None:
                prog_str = f"Program {u['program']} {instrument_name(u['program'])}"
            range_str = f"{note_name(u['min_note'])}-{note_name(u['max_note'])}"
            lines.append(
                f"| {u['track_index'] if info['format'] != 0 else 'Ch ' + str(u['channel'])} | "
                f"{u['name']} | {prog_str} | {u['note_count']} | {range_str} | "
                f"{u['avg_note']:.1f} | {u['polyphony']} | {ROLE_DISPLAY.get(u['role'], u['role'])} | {u['reason']} |"
            )

        lines.append("")

        bass = None
        main = None
        bass_candidates = [u for u in units if u["role"] == "bass"]
        if bass_candidates:
            bass_candidates.sort(
                key=lambda u: (
                    not (32 <= u["program"] <= 39) if u["program"] is not None else True,
                    -u["note_count"],
                    u["avg_note"],
                )
            )
            bass = bass_candidates[0]

        main_candidates = [u for u in units if u["role"] in ("vocal", "main")]
        if main_candidates:
            vocal = [u for u in main_candidates if u["role"] == "vocal"]
            if vocal:
                vocal.sort(key=lambda u: (-u["lyric_count"], -u["note_count"], u["avg_note"]))
                main = vocal[0]
            else:
                prog_counter = Counter(u["program"] for u in main_candidates if u["program"] is not None)
                main_candidates.sort(
                    key=lambda u: (
                        -u["note_count"],
                        prog_counter.get(u["program"], 0) if u["program"] is not None else 999,
                        -u["avg_note"],
                    )
                )
                main = main_candidates[0]

        if bass or main:
            lines.append("### 判断结论")
            lines.append("")
            if bass:
                lines.append(f"- **Bass 线**：`{bass['name']}`（Program {bass['program']} {instrument_name(bass['program'])}, {bass['note_count']} 个音符，音域 {note_name(bass['min_note'])}-{note_name(bass['max_note'])}, 平均音高 {bass['avg_note']:.1f}）")
            if main:
                lines.append(f"- **主旋律/人声线**：`{main['name']}`（Program {main['program']} {instrument_name(main['program'])}, {main['note_count']} 个音符，音域 {note_name(main['min_note'])}-{note_name(main['max_note'])}, 平均音高 {main['avg_note']:.1f}）")
            lines.append("")

            summary.append(
                (info["path"].name, bass, main, info["format"])
            )

    lines.append("## 汇总")
    lines.append("")
    lines.append("| 文件 | 格式 | Bass 线 | 主旋律/人声线 |")
    lines.append("|---|---|---|---|")
    for filename, bass, main, fmt in summary:
        bass_str = "-"
        if bass:
            bass_str = f"`{bass['name']}` Program {bass['program']} {instrument_name(bass['program'])}"
        main_str = "-"
        if main:
            main_str = f"`{main['name']}` Program {main['program']} {instrument_name(main['program'])}"
        lines.append(f"| {filename} | {fmt} | {bass_str} | {main_str} |")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="解析 MIDI 文件并生成字面分析报告")
    parser.add_argument(
        "-i",
        "--input",
        default=DEFAULT_INPUT_DIR,
        help=f"输入目录（默认：{DEFAULT_INPUT_DIR}）",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT_FILE,
        help=f"输出报告路径（默认：{DEFAULT_OUTPUT_FILE}）",
    )
    parser.add_argument(
        "--note-list",
        action="store_true",
        help="输出每个音轨的完整音符列表（默认只输出前 10 个）",
    )
    parser.add_argument(
        "--max-notes",
        type=int,
        default=0,
        help="完整音符列表时每个音轨最多输出多少个（0 表示不限制）",
    )
    parser.add_argument(
        "--md-output",
        default="",
        help="输出 Markdown 乐器与角色报告路径（默认不生成）",
    )
    parser.add_argument(
        "--main-c",
        default="Software/src/main.c",
        help="main.c 路径，用于对照 MusicPlayDual 调用（默认：Software/src/main.c）",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    midi_files = get_all_midi(input_dir)
    if not midi_files:
        raise FileNotFoundError(f"在 {input_dir} 中没有找到 .mid 文件")

    infos = []
    with output_path.open("w", encoding="utf-8") as f:
        f.write("MIDI 文件字面分析报告\n")
        f.write("=" * 80 + "\n\n")
        for midi_path in midi_files:
            file_info = parse_midi_file(midi_path)
            info = analyze_file(file_info)
            infos.append(info)
            report = format_file_report(info, note_list=args.note_list, max_notes=args.max_notes)
            f.write(report)

    print(f"报告已生成：{output_path.resolve()}")

    if args.md_output:
        md_path = Path(args.md_output)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        main_c_path = Path(args.main_c) if args.main_c else None
        write_markdown_report(infos, md_path, main_c_path)
        print(f"Markdown 报告已生成：{md_path.resolve()}")


if __name__ == "__main__":
    main()
