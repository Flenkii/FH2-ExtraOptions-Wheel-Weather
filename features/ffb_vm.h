#ifndef FH2_FFB_VM_H
#define FH2_FFB_VM_H
/* Force feedback programs of the Xbox One racing wheel ("Bristol"), run on the PC.

   FH2 does not compute wheel forces itself. Like every Xbox One racing game it uploads small
   programs to the wheel through Microsoft.Xbox.Input.Wheel.dll (IWheel slot 26) and then
   only updates named parameters every frame (IWheel slot 38, "Torque", "InRaceSpringScale",
   ...). The wheel's firmware runs the programs every tick and drives its motor with the result.

   This module is that firmware part: it compiles the program text the game hands over
   (e.g. "TOFL Lt E0 GT E0 L0 E0 ENDN E0 MOV {Torque} Af+") and executes it every 10 ms.

   Operands:  L0..L7  shared registers          E0..E3  registers of one program (kept)
              Lt      milliseconds (DWORD)       Et      milliseconds since the program was set
              Ad      wheel position (-1 .. 1 over the full rotation, + = right)
              Af      force output (-1 .. 1, + = push to the right), Af+ = add to it
              {Name}  game parameter             123 / 0X1F  DWORD   1.5f / 0.5  float
   Arithmetic and comparisons work on floats (TOFL / TODW convert), the result of a comparison
   is 1.0f or 0.0f. SKPZ/SKPN x n skip the next n instructions, END/ENDZ/ENDN end the program.

   Plain C without the C library, so it is also compiled and tested natively on Linux. */
#include <stddef.h>
#include <stdint.h>

#define FFB_VM_SLOTS 16
#define FFB_VM_PARAMS 32
#define FFB_VM_CODE 96
#define FFB_VM_NAME 48
#define FFB_VM_TICK_MS 10u

typedef struct {
    unsigned char kind, index;
    uint32_t bits; /* immediate value */
} FfbOperand;

typedef struct {
    unsigned char op, count;
    FfbOperand operand[3];
} FfbInstruction;

typedef struct {
    int loaded, broken;
    unsigned length;
    uint32_t e[4];
    uint32_t started;
    FfbInstruction code[FFB_VM_CODE];
} FfbProgram;

typedef struct {
    wchar_t name[FFB_VM_NAME];
    volatile uint32_t bits;
    float scale; /* applied when a program reads the parameter (e.g. rumble amount) */
} FfbParameter;

typedef struct {
    FfbProgram program[FFB_VM_SLOTS];
    FfbParameter param[FFB_VM_PARAMS];
    unsigned param_count;
    uint32_t l[8];
    uint32_t now;      /* Lt: milliseconds since ffb_vm_reset */
    float position;    /* Ad */
    float force;       /* Af */
    unsigned ticks;
} FfbVm;

void ffb_vm_reset(FfbVm *vm);
/* Index of a parameter, registering the name if it is new (-1 if the table is full). */
int ffb_vm_param(FfbVm *vm, const wchar_t *name, size_t length);
void ffb_vm_set_param(FfbVm *vm, int index, float value);
float ffb_vm_get_param(const FfbVm *vm, int index);
void ffb_vm_set_scale(FfbVm *vm, const wchar_t *name, float scale);
/* Compiles a program into a slot. Returns 1 on success; on failure the slot is cleared and
   *error_at (if given) receives the character position of the problem. */
int ffb_vm_load(FfbVm *vm, unsigned slot, const wchar_t *text, size_t length, size_t *error_at);
void ffb_vm_clear(FfbVm *vm, unsigned slot);
/* One tick: advances Lt by FFB_VM_TICK_MS, runs every loaded program in slot order and
   returns Af. */
float ffb_vm_tick(FfbVm *vm, float position);
unsigned ffb_vm_loaded(const FfbVm *vm);
#endif
