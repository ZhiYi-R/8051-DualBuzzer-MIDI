/**
 * config.h -- AT89C51RC2 目标配置
 */

#ifndef CONFIG_H
#define CONFIG_H

#define FOSC 12000000UL         /* 晶振 12 MHz */

#if defined(__SDCC_MODEL_SMALL)
#  define MemoryModel "small"
#elif defined(__SDCC_MODEL_LARGE)
#  define MemoryModel "large"
#else
#  define MemoryModel "small"
#endif

typedef unsigned char  U8;
typedef unsigned int   U16;
typedef unsigned long  U32;

#endif /* CONFIG_H */
