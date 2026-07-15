# MIDI 音轨乐器与角色分析报告

## 分析说明

- 使用 `rtmidi.midiconstants` 的常量自行解析 SMF（标准 MIDI 文件）。
- 乐器名称依据 General MIDI（GM）音色表映射。
- 判断规则：
  - **Bass 线**：Program 32–39，或音域整体偏低（最高音 ≤ E3 且平均音高 ≤ 48）。
  - **主旋律/人声线**：GM 主奏类乐器（钢琴/吉他/弦乐/木管/合成主奏），最高音 ≥ C4、平均音高 ≥ 55 且最大同时发声数 ≤ 2；或含有歌词 Meta 事件。
  - **打击乐**：通道 9（GM 标准打击乐通道）。
  - **和弦/伴奏**：主奏类乐器但多声部数 > 2。
  - **其他/伴奏**：不符合上述规则。

## 项目代码 `MusicPlayDual` 调用对照

| 歌曲 | 低音（第1参数） | 主旋律/人声（第2参数） |
|---|---|---|
| Numb | `Numb_Track6` | `Numb_Track9` |
| Payphone | `Payphone_Track2` | `Payphone_Track4` |
| NewDivide | `NewDivide_Track11` | `NewDivide_Track13` |
| WhatIveDone | `WhatIveDone_Track3` | `WhatIveDone_Track2` |

## NewDivide.mid

- SMF 格式：0（0=单音轨，1=多音轨，2=独立音轨）
- 音轨数量：1
- 分度值：192 ticks/四分音符
- 初始速度：500000 us/四分音符 ≈ 120.00 BPM
- 说明：Format 0 文件，所有事件合并在一个音轨内，因此按 MIDI 通道拆分分析。

| 音轨/通道 | 名称 | 乐器 | 音符数 | 音域 | 平均音高 | 多声部数 | 分类 | 判断依据 |
|---|---|---|---|---|---|---|---|---|
| Ch 0 | New Divide (Reloaded) / Ch 0 | Program 84 Lead 5 (charang) | 114 | F1-D#4 | 48.9 | 2 | 其他/伴奏 | 乐器 Lead 5 (charang)，音域 F1-D#4，平均音高 48.9 |
| Ch 1 | New Divide (Reloaded) / Ch 1 | Program 81 Lead 2 (sawtooth) | 180 | C#1-A#2 | 30.3 | 2 | Bass 线 | 乐器 Lead 2 (sawtooth)，音域 C#1-A#2，平均音高 30.3 |
| Ch 2 | New Divide (Reloaded) / Ch 2 | Program 35 Fretless Bass | 528 | C#1-A#2 | 33.7 | 2 | Bass 线 | 乐器 Fretless Bass，音域 C#1-A#2，平均音高 33.7 |
| Ch 3 | New Divide (Reloaded) / Ch 3 | Program 80 Lead 1 (square) | 13 | F1-F5 | 56.7 | 2 | 主旋律 | 乐器 Lead 1 (square)，音域 F1-F5，平均音高 56.7，多声部数 2 |
| Ch 4 | New Divide (Reloaded) / Ch 4 | Program 121 Breath Noise | 4196 | G1-F5 | 47.8 | 24 | 其他/伴奏 | 乐器 Breath Noise，音域 G1-F5，平均音高 47.8 |
| Ch 5 | New Divide (Reloaded) / Ch 5 | Program 122 Seashore | 4 | C#3-D#4 | 59.5 | 1 | 其他/伴奏 | 乐器 Seashore，音域 C#3-D#4，平均音高 59.5 |
| Ch 6 | New Divide (Reloaded) / Ch 6 | Program 118 Synth Drum | 81 | F#2-C#4 | 48.3 | 2 | 其他/伴奏 | 乐器 Synth Drum，音域 F#2-C#4，平均音高 48.3 |
| Ch 7 | New Divide (Reloaded) / Ch 7 | Program 51 Synth Strings 2 | 167 | D#1-F4 | 44.4 | 3 | 和弦/伴奏 | 乐器 Synth Strings 2，多声部数 3，属和弦/伴奏 |
| Ch 8 | New Divide (Reloaded) / Ch 8 | Program 80 Lead 1 (square) | 101 | G#3-G5 | 69.5 | 2 | 主旋律 | 乐器 Lead 1 (square)，音域 G#3-G5，平均音高 69.5，多声部数 2 |
| Ch 9 | New Divide (Reloaded) / Ch 9 | Program 16 Drawbar Organ | 1581 | D#1-A3 | 40.8 | 7 | 打击乐 | MIDI 通道 9 为通用打击乐通道 |
| Ch 10 | New Divide (Reloaded) / Ch 10 | Program 29 Overdriven Guitar | 1729 | C#2-A#3 | 47.6 | 4 | 和弦/伴奏 | 乐器 Overdriven Guitar，多声部数 4，属和弦/伴奏 |
| Ch 11 | New Divide (Reloaded) / Ch 11 | Program 33 Electric Bass (finger) | 603 | C#1-G#2 | 29.6 | 1 | Bass 线 | 乐器 Electric Bass (finger)，音域 C#1-G#2，平均音高 29.6 |
| Ch 12 | New Divide (Reloaded) / Ch 12 | Program 66 Tenor Sax | 313 | C4-A#5 | 76.2 | 2 | 主旋律 | 乐器 Tenor Sax，音域 C4-A#5，平均音高 76.2，多声部数 2 |
| Ch 13 | New Divide (Reloaded) / Ch 13 | Program 74 Recorder | 313 | C4-A#5 | 76.2 | 2 | 主旋律 | 乐器 Recorder，音域 C4-A#5，平均音高 76.2，多声部数 2 |
| Ch 14 | New Divide (Reloaded) / Ch 14 | Program 66 Tenor Sax | 313 | C4-A#5 | 76.2 | 2 | 主旋律 | 乐器 Tenor Sax，音域 C4-A#5，平均音高 76.2，多声部数 2 |
| Ch 15 | New Divide (Reloaded) / Ch 15 | Program 66 Tenor Sax | 180 | C3-F5 | 65.2 | 2 | 主旋律 | 乐器 Tenor Sax，音域 C3-F5，平均音高 65.2，多声部数 2 |

### 判断结论

- **Bass 线**：`New Divide (Reloaded) / Ch 11`（Program 33 Electric Bass (finger), 603 个音符，音域 C#1-G#2, 平均音高 29.6）
- **主旋律/人声线**：`New Divide (Reloaded) / Ch 13`（Program 74 Recorder, 313 个音符，音域 C4-A#5, 平均音高 76.2）

## Numb.mid

- SMF 格式：1（0=单音轨，1=多音轨，2=独立音轨）
- 音轨数量：11
- 分度值：960 ticks/四分音符
- 初始速度：545455 us/四分音符 ≈ 110.00 BPM

| 音轨/通道 | 名称 | 乐器 | 音符数 | 音域 | 平均音高 | 多声部数 | 分类 | 判断依据 |
|---|---|---|---|---|---|---|---|---|
| 1 | Track 1 | Program 82 Lead 3 (calliope) | 64 | C#5-A5 | 76.6 | 1 | 主旋律 | 乐器 Lead 3 (calliope)，音域 C#5-A5，平均音高 76.6，多声部数 1 |
| 2 | Track 2 | Program 48 String Ensemble 1 | 89 | D2-F#6 | 44.7 | 2 | 其他/伴奏 | 乐器 String Ensemble 1，音域 D2-F#6，平均音高 44.7 |
| 3 | Track 3 | Program 0 Acoustic Grand Piano | 1865 | B1-A#4 | 49.9 | 4 | 打击乐 | MIDI 通道 9 为通用打击乐通道 |
| 4 | Track 4 | Program 29 Overdriven Guitar | 102 | C#2-A3 | 47.1 | 2 | 其他/伴奏 | 乐器 Overdriven Guitar，音域 C#2-A3，平均音高 47.1 |
| 5 | Track 5 | Program 30 Distortion Guitar | 100 | C#2-A3 | 47.0 | 2 | 其他/伴奏 | 乐器 Distortion Guitar，音域 C#2-A3，平均音高 47.0 |
| 6 | Track 6 | Program 33 Electric Bass (finger) | 326 | C#2-A2 | 41.0 | 1 | Bass 线 | 乐器 Electric Bass (finger)，音域 C#2-A2，平均音高 41.0 |
| 7 | Track 7 | Program 0 Acoustic Grand Piano | 392 | D2-D5 | 67.3 | 2 | 主旋律 | 乐器 Acoustic Grand Piano，音域 D2-D5，平均音高 67.3，多声部数 2 |
| 8 | Track 8 | Program 53 Voice Oohs | 43 | D4-A4 | 65.6 | 1 | 主旋律 | 乐器 Voice Oohs，音域 D4-A4，平均音高 65.6，多声部数 1 |
| 9 | Chester Bennington | Program 66 Tenor Sax | 318 | F#3-A4 | 63.9 | 2 | 人声/主旋律 | 含 307 个歌词 Meta 事件，乐器 Tenor Sax |
| 10 | Track 10 | Program 27 Electric Guitar (clean) | 28 | F#4-C#5 | 69.5 | 1 | 主旋律 | 乐器 Electric Guitar (clean)，音域 F#4-C#5，平均音高 69.5，多声部数 1 |

### 判断结论

- **Bass 线**：`Track 6`（Program 33 Electric Bass (finger), 326 个音符，音域 C#2-A2, 平均音高 41.0）
- **主旋律/人声线**：`Chester Bennington`（Program 66 Tenor Sax, 318 个音符，音域 F#3-A4, 平均音高 63.9）

## Payphone.mid

- SMF 格式：1（0=单音轨，1=多音轨，2=独立音轨）
- 音轨数量：17
- 分度值：480 ticks/四分音符
- 初始速度：545455 us/四分音符 ≈ 110.00 BPM

| 音轨/通道 | 名称 | 乐器 | 音符数 | 音域 | 平均音高 | 多声部数 | 分类 | 判断依据 |
|---|---|---|---|---|---|---|---|---|
| 2 | 未命名 | Program 33 Electric Bass (finger) | 855 | C1-E3 | 43.4 | 2 | Bass 线 | 乐器 Electric Bass (finger)，音域 C1-E3，平均音高 43.4 |
| 3 | 未命名 | Program 0 Acoustic Grand Piano | 581 | B2-F#6 | 70.5 | 8 | 和弦/伴奏 | 乐器 Acoustic Grand Piano，多声部数 8，属和弦/伴奏 |
| 4 | 未命名 | Program 73 Flute | 497 | F#3-C#5 | 63.2 | 2 | 人声/主旋律 | 含 604 个歌词 Meta 事件，乐器 Flute |
| 5 | 未命名 | Program 0 Acoustic Grand Piano | 300 | A#3-G#4 | 62.8 | 6 | 和弦/伴奏 | 乐器 Acoustic Grand Piano，多声部数 6，属和弦/伴奏 |
| 6 | 未命名 | Program 26 Electric Guitar (jazz) | 741 | E3-F#5 | 65.5 | 8 | 和弦/伴奏 | 乐器 Electric Guitar (jazz)，多声部数 8，属和弦/伴奏 |
| 10 | 未命名 | Program 25 Acoustic Guitar (steel) | 1918 | C2-B3 | 39.9 | 8 | 打击乐 | MIDI 通道 9 为通用打击乐通道 |
| 13 | 未命名 | Program 27 Electric Guitar (clean) | 559 | B2-B4 | 64.2 | 10 | 和弦/伴奏 | 乐器 Electric Guitar (clean)，多声部数 10，属和弦/伴奏 |
| 15 | 未命名 | Program 119 Reverse Cymbal | 3 | C#3-C#3 | 49.0 | 1 | 其他/伴奏 | 乐器 Reverse Cymbal，音域 C#3-C#3，平均音高 49.0 |

### 判断结论

- **Bass 线**：`未命名`（Program 33 Electric Bass (finger), 855 个音符，音域 C1-E3, 平均音高 43.4）
- **主旋律/人声线**：`未命名`（Program 73 Flute, 497 个音符，音域 F#3-C#5, 平均音高 63.2）

## WhatIveDone.mid

- SMF 格式：1（0=单音轨，1=多音轨，2=独立音轨）
- 音轨数量：12
- 分度值：120 ticks/四分音符
- 初始速度：500000 us/四分音符 ≈ 120.00 BPM

| 音轨/通道 | 名称 | 乐器 | 音符数 | 音域 | 平均音高 | 多声部数 | 分类 | 判断依据 |
|---|---|---|---|---|---|---|---|---|
| 0 | 1 | Program 0 Acoustic Grand Piano | 2095 | C2-B3 | 44.2 | 5 | 打击乐 | MIDI 通道 9 为通用打击乐通道 |
| 1 | 2 | Program 1 Bright Acoustic Piano | 184 | G2-D5 | 55.2 | 3 | 和弦/伴奏 | 乐器 Bright Acoustic Piano，多声部数 3，属和弦/伴奏 |
| 2 | 3 | Program 2 Electric Grand Piano | 657 | G4-D#5 | 71.5 | 3 | 主旋律 | 乐器 Electric Grand Piano，音域 G4-D#5，平均音高 71.5，多声部数 3 |
| 3 | 4 | Program 33 Electric Bass (finger) | 423 | F1-F2 | 32.8 | 1 | Bass 线 | 乐器 Electric Bass (finger)，音域 F1-F2，平均音高 32.8 |
| 4 | 5 | Program 28 Electric Guitar (muted) | 1924 | G2-G5 | 59.0 | 5 | 和弦/伴奏 | 乐器 Electric Guitar (muted)，多声部数 5，属和弦/伴奏 |
| 5 | 6 | Program 30 Distortion Guitar | 493 | G2-G5 | 57.4 | 4 | 和弦/伴奏 | 乐器 Distortion Guitar，多声部数 4，属和弦/伴奏 |
| 6 | 7 | Program 51 Synth Strings 2 | 16 | F2-C3 | 44.5 | 1 | Bass 线 | 乐器 Synth Strings 2，音域 F2-C3，平均音高 44.5 |
| 7 | 8 | Program 69 English Horn | 169 | G3-G4 | 61.9 | 1 | 主旋律 | 乐器 English Horn，音域 G3-G4，平均音高 61.9，多声部数 1 |
| 8 | 9 | Program 122 Seashore | 1 | D4-D4 | 62.0 | 1 | 其他/伴奏 | 乐器 Seashore，音域 D4-D4，平均音高 62.0 |
| 9 | 10 | Program 27 Electric Guitar (clean) | 50 | D4-A#4 | 64.9 | 2 | 主旋律 | 乐器 Electric Guitar (clean)，音域 D4-A#4，平均音高 64.9，多声部数 2 |
| 10 | 11 | Program 52 Choir Aahs | 48 | G3-D#4 | 60.5 | 1 | 主旋律 | 乐器 Choir Aahs，音域 G3-D#4，平均音高 60.5，多声部数 1 |
| 11 | 12 | Program 30 Distortion Guitar | 50 | D4-A#4 | 64.9 | 2 | 主旋律 | 乐器 Distortion Guitar，音域 D4-A#4，平均音高 64.9，多声部数 2 |

### 判断结论

- **Bass 线**：`4`（Program 33 Electric Bass (finger), 423 个音符，音域 F1-F2, 平均音高 32.8）
- **主旋律/人声线**：`3`（Program 2 Electric Grand Piano, 657 个音符，音域 G4-D#5, 平均音高 71.5）

## 汇总

| 文件 | 格式 | Bass 线 | 主旋律/人声线 |
|---|---|---|---|
| NewDivide.mid | 0 | `New Divide (Reloaded) / Ch 11` Program 33 Electric Bass (finger) | `New Divide (Reloaded) / Ch 13` Program 74 Recorder |
| Numb.mid | 1 | `Track 6` Program 33 Electric Bass (finger) | `Chester Bennington` Program 66 Tenor Sax |
| Payphone.mid | 1 | `未命名` Program 33 Electric Bass (finger) | `未命名` Program 73 Flute |
| WhatIveDone.mid | 1 | `4` Program 33 Electric Bass (finger) | `3` Program 2 Electric Grand Piano |
