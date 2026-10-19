/* compat2: null guard for the game's TransitionToLoadingComplete handler.
 * At game+0xe8ccd8 the handler dereferences the player-profile smart pointer
 * ([rsp+0x28]) without the null check that its sibling branch performs.
 * Under Azimuth 0.9.10 the profile can still be null when the boot loading
 * screen completes, which crashes with "game+0xe8cce3 reading 0x50".
 * The guard jumps to a trampoline that adds the missing check and takes the
 * handler's existing default path (game+0xe8cd27) when the pointer is null. */
#include "azimuth_host.h"
#include "logging.h"
#include "support.h"

#define GUARD_RVA 0xe8ccd8u
#define GUARD_CONTINUE_RVA 0xe8cceau
#define GUARD_DEFAULT_RVA 0xe8cd27u

static const unsigned char guard_original[18] = {
    0x80, 0x7f, 0x2b, 0x00,             /* cmp byte [rdi+0x2b],0 */
    0x74, 0x49,                         /* je  +0x49 (0xe8cd27)  */
    0x48, 0x8b, 0x44, 0x24, 0x28,       /* mov rax,[rsp+0x28]    */
    0x48, 0x8b, 0x48, 0x50,             /* mov rcx,[rax+0x50]    */
    0x48, 0x8b, 0x01};                  /* mov rax,[rcx]         */
static const unsigned char guard_sibling[8] = {0x48, 0x8b, 0x7c, 0x24, 0x28, 0x48, 0x85, 0xff};
static const unsigned char guard_after[5] = {0xba, 0x06, 0x00, 0x00, 0x00};

uintptr_t fh2_guard_continue;
uintptr_t fh2_guard_default;
void fh2_loading_guard(void);

__asm__(".text\n"
        ".globl fh2_loading_guard\n"
        "fh2_loading_guard:\n"
        "  cmpb $0, 0x2b(%rdi)\n"
        "  je 1f\n"
        "  movq 0x28(%rsp), %rax\n"
        "  testq %rax, %rax\n"
        "  je 1f\n"
        "  movq 0x50(%rax), %rcx\n"
        "  testq %rcx, %rcx\n"
        "  je 1f\n"
        "  movq (%rcx), %rax\n"
        "  jmpq *fh2_guard_continue(%rip)\n"
        "1:\n"
        "  jmpq *fh2_guard_default(%rip)\n");

void azimuth_apply_loading_guard(unsigned char *base) {
    unsigned char *site = base + GUARD_RVA;
    unsigned char current[18];
    if (!memory_read(site, current, sizeof(current))) {
        log_append("GUARD: loading-complete guard skipped; code not readable.\r\n");
        return;
    }
    if (current[0] == 0xff && current[1] == 0x25) {
        log_append("GUARD: loading-complete guard already present.\r\n");
        return;
    }
    if (!memory_equal(current, guard_original, sizeof(guard_original)) ||
        !memory_equal(base + 0xe8cc6au, guard_sibling, sizeof(guard_sibling)) ||
        !memory_equal(base + GUARD_CONTINUE_RVA, guard_after, sizeof(guard_after))) {
        log_append("GUARD: loading-complete guard skipped; unexpected code bytes.\r\n");
        return;
    }
    fh2_guard_continue = (uintptr_t)(base + GUARD_CONTINUE_RVA);
    fh2_guard_default = (uintptr_t)(base + GUARD_DEFAULT_RVA);
    unsigned char patch[18];
    uintptr_t target = (uintptr_t)&fh2_loading_guard;
    patch[0] = 0xff; patch[1] = 0x25;
    patch[2] = patch[3] = patch[4] = patch[5] = 0;
    memory_copy(patch + 6, &target, sizeof(target));
    patch[14] = patch[15] = patch[16] = patch[17] = 0xcc;
    DWORD old, ignored;
    if (!VirtualProtect(site, sizeof(patch), PAGE_EXECUTE_READWRITE, &old)) {
        log_append("GUARD: loading-complete guard skipped; page protection refused.\r\n");
        return;
    }
    memory_copy(site, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), site, sizeof(patch));
    VirtualProtect(site, sizeof(patch), old, &ignored);
    log_append("GUARD: loading-complete null guard installed (game+0xe8ccd8).\r\n");
}
