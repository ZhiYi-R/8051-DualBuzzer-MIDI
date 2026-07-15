/**
 * AT89C51RC2 双蜂鸣器歌曲播放演示
 * 主蜂鸣器 P3.1，副蜂鸣器 P3.0，均经 ULN2003A 驱动
 * 晶振 12.000 MHz
 *
 * 注意：中断函数必须与 main() 位于同一文件，SDCC 4.5.x 才能生成中断向量表。
 */

#include <at89c51ed2.h>
#include <stdint.h>
#include "config.h"
#include "music.h"

/* 全局状态 */
static uint8_t PlaylistMode;            /* 0=单曲循环，1=列表循环 */
static volatile uint8_t  ProgressDirty;
static volatile uint16_t ProgressNote;
static volatile uint16_t ProgressTotal;

/* 共阳七段码（P0 输出，0 点亮） */
#define SEG_1  0xF9
#define SEG_2  0xA4
#define SEG_3  0xB0
#define SEG_4  0x99

static void UpdateSpectrum(uint16_t frequency) {
    uint8_t leds;

    if (frequency == 0) {
        leds = 0x00;            /* 休止：全部熄灭 */
    } else if (frequency < 180) {
        leds = 0x01;
    } else if (frequency < 240) {
        leds = 0x03;
    } else if (frequency < 300) {
        leds = 0x07;
    } else if (frequency < 360) {
        leds = 0x0F;
    } else if (frequency < 440) {
        leds = 0x1F;
    } else if (frequency < 550) {
        leds = 0x3F;
    } else if (frequency < 700) {
        leds = 0x7F;
    } else {
        leds = 0xFF;
    }
    P1 = leds;
}

static void DisplaySongNumber(uint8_t song) {
    uint8_t seg;
    switch (song) {
        case 0: seg = SEG_1; break;
        case 1: seg = SEG_2; break;
        case 2: seg = SEG_3; break;
        case 3: seg = SEG_4; break;
        default: seg = 0xFF; break;
    }
    if (PlaylistMode) {
        seg &= 0x7F;            /* 列表循环时点亮小数点 */
    }
    P0 = seg;
}

/* 播放器状态 */
static volatile uint8_t  Timer0ReloadHigh;
static volatile uint8_t  Timer0ReloadLow;
static volatile uint16_t DurationCounter;
static volatile uint16_t NoteIndex;
static volatile const Note __code *SongData;
static volatile uint16_t SongLength;
static volatile uint8_t  PlayerState = MusicStopped;
static volatile uint8_t  HasSecondTrack;    /* 1=双音轨播放中 */
static volatile uint16_t DurationCounter2;
static volatile uint16_t NoteIndex2;
static volatile const Note __code *SongData2;
static volatile uint16_t SongLength2;
static volatile uint8_t  Timer2ReloadHigh;
static volatile uint8_t  Timer2ReloadLow;

void MusicStop(void);
void MusicPause(void);
void MusicResume(void);
void MusicPlay(const Note __code *song, uint16_t length);
void MusicPlayDual(const Note __code *track1, uint16_t len1,
                   const Note __code *track2, uint16_t len2);
static void LoadNote(uint16_t index);

static uint8_t lastP34State;

static void PollPauseButton(void) {
    uint16_t _d;
    uint8_t p34 = P3_4;

    if (lastP34State == 1 && p34 == 0) {
        for (_d = 0; _d < 2000; _d++) { }  /* 消抖约 20 ms */
        if (P3_4 == 0) {
            if (PlayerState == MusicPlaying) {
                MusicPause();
            } else if (PlayerState == MusicPaused) {
                MusicResume();
            }
            while (P3_4 == 0) { }           /* 等待释放 */
        }
    }
    lastP34State = p34;
}

static uint8_t CurrentSongIndex;
#define SongCount  4

static void PlayCurrentSong(void) {
    switch (CurrentSongIndex) {
        case 0: MusicPlayDual(Numb_Track6, Numb_Track6Length,
                              Numb_Track9, Numb_Track9Length);  break;
        case 1: MusicPlayDual(Payphone_Track2, Payphone_Track2Length,
                              Payphone_Track4, Payphone_Track4Length);  break;
        case 2: MusicPlayDual(NewDivide_Track11, NewDivide_Track11Length,
                              NewDivide_Track13, NewDivide_Track13Length);  break;
        case 3: MusicPlayDual(WhatIveDone_Track3, WhatIveDone_Track3Length,
                              WhatIveDone_Track2, WhatIveDone_Track2Length);  break;
    }
}

/* 外部中断0：P3.2 切歌键 */
void Int0ISR(void) __interrupt(IE0_VECTOR) {
    uint16_t delay;

    EX0 = 0;                            /* 消抖期间关闭中断 */
    for (delay = 0; delay < 3000; delay++) { }  /* 消抖约 20 ms */

    if (P3_2 == 0) {
        CurrentSongIndex++;
        if (CurrentSongIndex >= SongCount) {
            CurrentSongIndex = 0;
        }
        PlayCurrentSong();
        DisplaySongNumber(CurrentSongIndex);
    }

    IE0 = 0;
    EX0 = 1;
}

/* 外部中断1：P3.3 单曲/列表切换键 */
void Int1ISR(void) __interrupt(IE1_VECTOR) {
    uint16_t delay;

    EX1 = 0;
    for (delay = 0; delay < 3000; delay++) { }  /* 消抖 */

    if (P3_3 == 0) {
        PlaylistMode = !PlaylistMode;
        DisplaySongNumber(CurrentSongIndex);
    }

    IE1 = 0;
    EX1 = 1;
}

/* 设置 Timer0 频率，输出 P3.1；frequency=0 时关闭 */
static void ApplyFrequency(uint16_t frequency) {
    if (frequency == 0) {
        TR0  = 0;
        P3_1 = 0;                       /* 关闭蜂鸣器 */
        Timer0ReloadHigh = 0;
        Timer0ReloadLow  = 0;
        UpdateSpectrum(0);
        return;
    }

    uint32_t count = (FOSC / 24UL) / frequency;
    if (count > 65535UL) count = 65535UL;

    uint16_t reloadValue = (uint16_t)(65536UL - count);
    Timer0ReloadHigh = (uint8_t)(reloadValue >> 8);
    Timer0ReloadLow  = (uint8_t)(reloadValue & 0xFF);

    TR0 = 0;
    TH0 = Timer0ReloadHigh;
    TL0 = Timer0ReloadLow;
    TF0 = 0;
    TR0 = 1;

    UpdateSpectrum(frequency);
}

/* 设置 Timer2 频率，输出 P3.0；frequency=0 时关闭 */
static void ApplyFrequency2(uint16_t frequency) {
    uint32_t count;
    uint16_t reload;

    if (frequency == 0) {
        TR2  = 0;
        P3_0 = 0;                       /* 关闭蜂鸣器 */
        return;
    }

    count = (FOSC / 24UL) / frequency;
    if (count > 65535UL) count = 65535UL;
    reload = (uint16_t)(65536UL - count);
    Timer2ReloadHigh = (uint8_t)(reload >> 8);
    Timer2ReloadLow  = (uint8_t)(reload & 0xFF);

    RCAP2H = Timer2ReloadHigh;
    RCAP2L = Timer2ReloadLow;
    TH2 = Timer2ReloadHigh;
    TL2 = Timer2ReloadLow;
    T2CON |= 0x04;                      /* 启动 Timer2 */
    TF2 = 0;
    TR2 = 1;
}

/* 播放器接口 */

void MusicInit(void) {
    P3_1 = 0;                           /* 关闭主蜂鸣器 */

    TMOD &= 0xF0;
    TMOD |= 0x01;
    TMOD &= 0x0F;
    TMOD |= 0x10;

    TH1 = (uint8_t)((65536UL - (FOSC / 1200UL)) >> 8);
    TL1 = (uint8_t)((65536UL - (FOSC / 1200UL)) & 0xFF);

    TF0 = 0;
    TF1 = 0;

    ET0 = 1;
    ET1 = 1;
    ET2 = 1;

    PlayerState = MusicStopped;
}

void MusicPlayDual(
    const Note __code *track1, uint16_t len1,
    const Note __code *track2, uint16_t len2)
{
    if (PlayerState == MusicPlaying) {
        MusicStop();
    }

    T2CON = 0x00;                       /* Timer2 16位自动重载 */

    SongData2   = track1;
    SongLength2 = len1;
    NoteIndex2  = 0;

    SongData   = track2;
    SongLength = len2;
    NoteIndex  = 0;

    HasSecondTrack = 1;

    Note n2 = SongData[0];
    DurationCounter = n2.Duration;
    ApplyFrequency(n2.Frequency);

    Note n1 = SongData2[0];
    DurationCounter2 = n1.Duration;
    ApplyFrequency2(n1.Frequency);

    TR1 = 1;
    PlayerState = MusicPlaying;
}

void MusicStop(void) {
    TR0  = 0;
    TR1  = 0;
    TR2  = 0;
    P3_1 = 0;
    P3_0 = 0;
    HasSecondTrack = 0;
    PlayerState = MusicStopped;
}

void MusicPause(void) {
    if (PlayerState != MusicPlaying) return;
    TR0 = 0;
    TR1 = 0;
    P3_1 = 0;
    PlayerState = MusicPaused;
}

void MusicResume(void) {
    if (PlayerState != MusicPaused) return;
    TR0 = 1;
    TR1 = 1;
    PlayerState = MusicPlaying;
}

uint8_t MusicStatus(void) {
    return PlayerState;
}

void MusicPlay(const Note __code *song, uint16_t length) {
    if (PlayerState == MusicPlaying) {
        MusicStop();
    }

    SongData   = song;
    SongLength = length;
    NoteIndex  = 0;

    LoadNote(0);
    TR1 = 1;

    PlayerState = MusicPlaying;
}

/* 加载指定索引的音符 */
static void LoadNote(uint16_t index) {
    if (index >= SongLength) {
        MusicStop();
        return;
    }

    Note currentNote = SongData[index];
    DurationCounter = currentNote.Duration;
    ApplyFrequency(currentNote.Frequency);
}

/* 定时器0 中断：按频率翻转 P3.1 */
void Timer0ISR(void) __interrupt(TF0_VECTOR) {
    P3_1 = !P3_1;
    TH0  = Timer0ReloadHigh;
    TL0  = Timer0ReloadLow;
    TF0  = 0;
}

/* 定时器2 中断：按频率翻转 P3.0 */
void Timer2ISR(void) __interrupt(TF2_VECTOR) {
    P3_0 = !P3_0;
    TF2 = 0;
}

/* 定时器1 中断：10 ms 节拍，推进音符 */
void Timer1ISR(void) __interrupt(TF1_VECTOR) {
    TH1 = (uint8_t)((65536UL - (FOSC / 1200UL)) >> 8);
    TL1 = (uint8_t)((65536UL - (FOSC / 1200UL)) & 0xFF);

    if (DurationCounter > 10) {
        DurationCounter -= 10;
    } else {
        NoteIndex++;
        LoadNote(NoteIndex);
    }

    if (HasSecondTrack) {
        if (DurationCounter2 > 10) {
            DurationCounter2 -= 10;
        } else {
            NoteIndex2++;
            if (NoteIndex2 < SongLength2) {
                Note currentNote2 = SongData2[NoteIndex2];
                DurationCounter2 = currentNote2.Duration;
                ApplyFrequency2(currentNote2.Frequency);
            }
        }
    }

    TF1 = 0;
}

/* 主函数 */
int main(void) {
    uint16_t index;

    MusicInit();
    EA = 1;

    for (index = 0; index < 50000; index++) {     /* 启动前短暂延时 */
    }

    IT0 = 1;
    IT1 = 1;
    EX0 = 1;
    EX1 = 1;
    PlaylistMode = 0;

    CurrentSongIndex = 0;
    DisplaySongNumber(CurrentSongIndex);
    PlayCurrentSong();

    while (1) {
        while (MusicStatus() == MusicPlaying) {
            PollPauseButton();
        }
        PollPauseButton();

        if (MusicStatus() == MusicPaused || MusicStatus() == MusicPlaying) {
            continue;                           /* 暂停或刚恢复，不重播 */
        }

        /* 歌曲结束：下一首或重新播放 */
        if (PlaylistMode) {
            CurrentSongIndex++;
            if (CurrentSongIndex >= SongCount) {
                CurrentSongIndex = 0;
            }
        }
        DisplaySongNumber(CurrentSongIndex);
        PlayCurrentSong();
    }
}
