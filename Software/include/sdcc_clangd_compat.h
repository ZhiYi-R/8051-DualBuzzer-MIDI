/**
 * sdcc_clangd_compat.h
 *
 * Dummy header that maps SDCC-specific keywords to standard C constructs
 * so that clangd can parse 8051 source code for language services.
 *
 * This file is automatically included by clangd via .clangd's CompileFlags.Add.
 * It is NOT used by the real SDCC compiler.
 */

#ifndef SDCC_CLANGD_COMPAT_H
#define SDCC_CLANGD_COMPAT_H

/* ------------------------------------------------------------------ */
/* Memory qualifiers -- strip to let clangd see the underlying type    */
/* ------------------------------------------------------------------ */
#define __data
#define __xdata
#define __idata
#define __pdata
#define __code
#define __near
#define __far
#define __banked
#define __reentrant

/* ------------------------------------------------------------------ */
/* Special-function register / bit keywords                           */
/* ------------------------------------------------------------------ */
#define __sfr  volatile unsigned char
#define __sfr16 volatile unsigned short
#define __sfr32 volatile unsigned int

/* sbit -- SDCC keyword for bit-addressable SFR bits                  */
#define __sbit volatile unsigned char
#define sbit   __sbit

/* ------------------------------------------------------------------ */
/* Bit type (1-bit storage) -- clangd has no 1-bit type, use uchar    */
/* ------------------------------------------------------------------ */
#define __bit  unsigned char
#define bit    __bit

/* ------------------------------------------------------------------ */
/* Function qualifiers                                                */
/* ------------------------------------------------------------------ */
#define __interrupt(n)
#define __using(n)
#define __critical
#define __naked
#define __noreturn

/* ------------------------------------------------------------------ */
/* Absolute address placement                                         */
/* ------------------------------------------------------------------ */
#define __at(x)

/* ------------------------------------------------------------------ */
/* Inline assembly (SDCC: __asm ... __endasm)                         */
/* clangd will silently skip __asm blocks if parsing fails            */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/* Built-in function declarations for clangd                          */
/* ------------------------------------------------------------------ */
void __delay_cycles(unsigned long __cycles);

/* ------------------------------------------------------------------ */
/* Ensure standard headers available for clangd                       */
/* ------------------------------------------------------------------ */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#endif /* SDCC_CLANGD_COMPAT_H */
