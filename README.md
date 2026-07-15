# MCU 双蜂鸣器歌曲播放系统

这是基于 **AT89C51RC2** 单片机的课程设计项目，用双蜂鸣器播放 MIDI 曲目。仓库里包含硬件仿真、8051 固件、MIDI 分析脚本和课程报告。

## 功能特性

- 主控为 **AT89C51RC2**，晶振 12 MHz。
- 双蜂鸣器输出：主蜂鸣器 `P3.1`、副蜂鸣器 `P3.0`，由 ULN2003A 驱动。
- 内置 4 首歌曲（`Numb`、`Payphone`、`NewDivide`、`WhatIveDone`），用双音轨播放。
- 交互控制：
  - `P3.2` 切换歌曲（外部中断 0）。
  - `P3.3` 切换单曲循环 / 列表循环（外部中断 1）。
  - `P3.4` 暂停 / 继续播放。
- 数码管在 `P0` 显示当前歌曲编号，频谱 LED 在 `P1`。
- Python 脚本 `Analyzer.py` 用于提取音轨、乐器角色与频率信息。

## 仓库结构

```
.
├── Proteus/                    # Proteus 8 硬件仿真工程
│   └── Hardware.pdsprj
├── Software/                   # 8051 固件源码
│   ├── SConstruct              # SCons 构建脚本
│   ├── src/
│   │   ├── main.c              # 主程序与中断控制
│   │   └── music.c             # 歌曲音符数据
│   └── include/
│       ├── config.h            # 目标配置（晶振、类型别名）
│       ├── music.h             # 音符结构与歌曲声明
│       └── sdcc_clangd_compat.h# clangd 兼容性头文件
├── Resources/                  # 原始 MIDI 资源
│   ├── NewDivide.mid
│   ├── Numb.mid
│   ├── Payphone.mid
│   └── WhatIveDone.mid
├── utils/                      # 辅助脚本
│   ├── Analyzer.py             # MIDI 解析与报告生成
│   ├── midi_analysis_report.txt
│   └── midi_track_instruments.md
├── fonts/                      # 第三方字体子模块
│   └── LxgwWenKai/             # 霞鹜文楷（OFL-1.1 许可证）
├── report.tex                  # 课程报告 LaTeX 源文件
├── .gitignore                  # 仓库忽略规则
└── .gitmodules                 # Git 子模块配置
```

## 硬件设计

硬件仿真在 `Proteus/Hardware.pdsprj` 里，包括：

- **AT89C51RC2** 单片机
- **ULN2003A** 驱动双蜂鸣器
- 数码管与 8 位 LED 频谱显示
- 按键：切歌、模式切换、暂停/继续

## 软件构建

### 依赖

- [SDCC](https://sdcc.sourceforge.net/)（Small Device C Compiler）
- [SCons](https://scons.org/)（Python 构建工具）
- Python 3（用于 `utils/Analyzer.py`）

### 编译

在 `Software/` 目录下运行：

```bash
scons
```

编译产物是 `Software/build/firmware.hex`。如果 SDCC 没添加到 PATH，可以指定安装路径：

```bash
scons SDCC_HOME=D:/Tools/SDCC
```

清理构建产物：

```bash
scons -c
```

构建脚本同时生成 `compile_commands.json`，供 `clangd` 语言服务器补全。

## 烧录

1. 使用 USB 转串口或 ISP 烧录器连接目标板。
2. 打开 STC-ISP 或相应烧录软件。
3. 选择 `Software/build/firmware.hex`。
4. 设置晶振为 12 MHz，执行烧录。

## MIDI 分析

`utils/Analyzer.py` 用于解析 `Resources/` 中的 MIDI 文件，并生成：

- 字面分析报告：`utils/midi_analysis_report.txt`
- Markdown 乐器角色报告：`utils/midi_track_instruments.md`

运行示例：

```bash
cd utils
python Analyzer.py
python Analyzer.py --md-output midi_track_instruments.md
```

分析报告会指出每个 MIDI 文件的 Bass 线和主旋律，供 `main.c` 中的 `MusicPlayDual` 参考。

## 报告

课程报告源文件是 `report.tex`，用 `xelatex` 或 `lualatex` 编译：

```bash
xelatex report.tex
```

如果报告用了 `fonts/LxgwWenKai` 字体，先拉取子模块：

```bash
git submodule update --init --recursive
```

## 第三方资源与许可证

- **霞鹜文楷（LxgwWenKai）**：位于 `fonts/LxgwWenKai`，使用 [SIL Open Font License 1.1](fonts/LxgwWenKai/OFL.txt) 授权。
  - 字体不得单独销售。
  - 若重新分发字体或修改版本，需保留版权声明与 OFL 许可证。
  - 修改版本不得使用保留字体名（`霞鹜`、`霞鶩`、`落霞孤鹜`、`落霞孤鶩`、`LXGW`），除非获得作者书面许可。

项目其余代码是课程设计原创，没有单独声明许可证。

## 注意事项

- 首次克隆后执行 `git submodule update --init --recursive` 拉取字体子模块。
- 构建前请确保 SDCC 已安装并加入 PATH，或者设置 `SDCC_HOME` 环境变量。
- 中断服务程序和 `main()` 放在同一文件里，以满足 SDCC 4.5.x 中断向量表生成要求。
