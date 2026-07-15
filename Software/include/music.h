/**
 * music.h -- 音符结构与歌曲声明
 */

#ifndef MUSIC_H
#define MUSIC_H

#include <stdint.h>

typedef struct {
    uint16_t Frequency;
    uint16_t Duration;
} Note;

#define SongEnd  {0, 0}

#define MusicStopped  0
#define MusicPlaying  1
#define MusicPaused   2

#pragma disable_warning 336

extern const Note __code Numb_Track6[];
extern const uint16_t Numb_Track6Length;

extern const Note __code Numb_Track9[];
extern const uint16_t Numb_Track9Length;

extern const Note __code Payphone_Track2[];
extern const uint16_t Payphone_Track2Length;

extern const Note __code Payphone_Track4[];
extern const uint16_t Payphone_Track4Length;

extern const Note __code NewDivide_Track11[];
extern const uint16_t NewDivide_Track11Length;

extern const Note __code NewDivide_Track13[];
extern const uint16_t NewDivide_Track13Length;

extern const Note __code WhatIveDone_Track2[];
extern const uint16_t WhatIveDone_Track2Length;

extern const Note __code WhatIveDone_Track3[];
extern const uint16_t WhatIveDone_Track3Length;

#endif /* MUSIC_H */
