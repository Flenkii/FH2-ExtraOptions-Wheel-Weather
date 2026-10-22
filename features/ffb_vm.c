/* Xbox One wheel force feedback programs on the PC. See ffb_vm.h. */
#include "ffb_vm.h"

enum {
    K_NONE,
    K_IMM,   /* bits */
    K_L,     /* L0..L7 */
    K_E,     /* E0..E3 */
    K_LT,    /* Lt */
    K_ET,    /* Et */
    K_AD,    /* Ad */
    K_AF,    /* Af */
    K_AFADD, /* Af+ (destination only) */
    K_PARAM, /* {Name} */
};

enum {
    OP_NOP, OP_SKP, OP_SKPZ, OP_SKPN, OP_END, OP_ENDZ, OP_ENDN,
    OP_ADD, OP_SUB, OP_MUL, OP_DIV, OP_MOD,
    OP_POW2, OP_POW3, OP_SQRT, OP_SGN, OP_ABS, OP_INV,
    OP_AND, OP_OR, OP_NAND, OP_NOR, OP_XOR, OP_NOT, OP_NXOR,
    OP_GT, OP_GTE, OP_LT, OP_LTE, OP_EQ,
    OP_BAND, OP_BOR, OP_BXOR, OP_BNOT,
    OP_MOV, OP_TOFL, OP_TODW, OP_MOD_FL, OP_MOD_DW,
    OP_COUNT
};

/* name, operand count, index of the destination operand (-1 = none) */
static const struct {
    const char *name;
    unsigned char count;
    signed char destination;
} ops[OP_COUNT] = {
    [OP_NOP] = {"NOP", 0, -1},   [OP_SKP] = {"SKP", 1, -1},    [OP_SKPZ] = {"SKPZ", 2, -1},
    [OP_SKPN] = {"SKPN", 2, -1}, [OP_END] = {"END", 0, -1},    [OP_ENDZ] = {"ENDZ", 1, -1},
    [OP_ENDN] = {"ENDN", 1, -1}, [OP_ADD] = {"ADD", 3, 2},     [OP_SUB] = {"SUB", 3, 2},
    [OP_MUL] = {"MUL", 3, 2},    [OP_DIV] = {"DIV", 3, 2},     [OP_MOD] = {"MOD", 3, 2},
    [OP_POW2] = {"POW2", 2, 1},  [OP_POW3] = {"POW3", 2, 1},   [OP_SQRT] = {"SQRT", 2, 1},
    [OP_SGN] = {"SGN", 2, 1},    [OP_ABS] = {"ABS", 2, 1},     [OP_INV] = {"INV", 2, 1},
    [OP_AND] = {"AND", 3, 2},    [OP_OR] = {"OR", 3, 2},       [OP_NAND] = {"NAND", 3, 2},
    [OP_NOR] = {"NOR", 3, 2},    [OP_XOR] = {"XOR", 3, 2},     [OP_NOT] = {"NOT", 2, 1},
    [OP_NXOR] = {"NXOR", 3, 2},  [OP_GT] = {"GT", 3, 2},       [OP_GTE] = {"GTE", 3, 2},
    [OP_LT] = {"LT", 3, 2},      [OP_LTE] = {"LTE", 3, 2},     [OP_EQ] = {"EQ", 3, 2},
    [OP_BAND] = {"BAND", 3, 2},  [OP_BOR] = {"BOR", 3, 2},     [OP_BXOR] = {"BXOR", 3, 2},
    [OP_BNOT] = {"BNOT", 2, 1},  [OP_MOV] = {"MOV", 2, 1},     [OP_TOFL] = {"TOFL", 2, 1},
    [OP_TODW] = {"TODW", 2, 1},  [OP_MOD_FL] = {"MOD_FL", 3, 2}, [OP_MOD_DW] = {"MOD_DW", 3, 2},
};

static uint32_t f2b(float value) {
    union {
        float f;
        uint32_t u;
    } v;
    v.f = value;
    return v.u;
}

static float b2f(uint32_t bits) {
    union {
        float f;
        uint32_t u;
    } v;
    v.u = bits;
    return v.f;
}

static int finite(float value) {
    return (f2b(value) & 0x7f800000u) != 0x7f800000u;
}

static wchar_t upper(wchar_t c) {
    return c >= L'a' && c <= L'z' ? (wchar_t)(c - 32) : c;
}

/* token equals an ASCII word (case-insensitive) */
static int word_is(const wchar_t *token, size_t length, const char *word) {
    size_t i = 0;
    for (; i < length && word[i]; ++i) {
        if (upper(token[i]) != (wchar_t)word[i]) return 0;
    }
    return i == length && !word[i];
}

/* ------------------------------------------------------------------ parameters */

void ffb_vm_reset(FfbVm *vm) {
    unsigned char *p = (unsigned char *)vm;
    for (size_t i = 0; i < sizeof(*vm); ++i) p[i] = 0;
}

int ffb_vm_param(FfbVm *vm, const wchar_t *name, size_t length) {
    if (!name || !length || length >= FFB_VM_NAME) return -1;
    for (unsigned i = 0; i < vm->param_count; ++i) {
        const wchar_t *n = vm->param[i].name;
        size_t k = 0;
        while (k < length && n[k] && upper(n[k]) == upper(name[k])) ++k;
        if (k == length && !n[k]) return (int)i;
    }
    if (vm->param_count >= FFB_VM_PARAMS) return -1;
    FfbParameter *p = &vm->param[vm->param_count];
    for (size_t k = 0; k < length; ++k) p->name[k] = name[k];
    p->name[length] = 0;
    p->bits = 0;
    p->scale = 1.0f;
    return (int)vm->param_count++;
}

void ffb_vm_set_param(FfbVm *vm, int index, float value) {
    if (index >= 0 && index < (int)vm->param_count && finite(value)) vm->param[index].bits = f2b(value);
}

float ffb_vm_get_param(const FfbVm *vm, int index) {
    return index >= 0 && index < (int)vm->param_count ? b2f(vm->param[index].bits) : 0.0f;
}

void ffb_vm_set_scale(FfbVm *vm, const wchar_t *name, float scale) {
    size_t length = 0;
    while (name[length]) ++length;
    int index = ffb_vm_param(vm, name, length);
    if (index >= 0 && finite(scale)) vm->param[index].scale = scale;
}

/* ------------------------------------------------------------------ compiler */

static int digit(wchar_t c) {
    return c >= L'0' && c <= L'9';
}

/* "12", "0X1F", "2500f", "0.5f", "100.0f", "-1" */
static int parse_number(const wchar_t *t, size_t n, uint32_t *bits) {
    size_t i = 0;
    int negative = 0;
    if (i < n && (t[i] == L'-' || t[i] == L'+')) negative = t[i++] == L'-';
    if (i >= n) return 0;
    if (n - i > 2 && t[i] == L'0' && upper(t[i + 1]) == L'X') {
        uint32_t v = 0;
        i += 2;
        if (i >= n) return 0;
        for (; i < n; ++i) {
            wchar_t c = upper(t[i]);
            unsigned d = digit(c) ? (unsigned)(c - L'0') : (c >= L'A' && c <= L'F') ? (unsigned)(c - L'A' + 10) : 99;
            if (d > 15) return 0;
            v = v * 16 + d;
        }
        *bits = negative ? (uint32_t)(0u - v) : v;
        return 1;
    }
    int is_float = 0;
    size_t end = n;
    if (upper(t[end - 1]) == L'F') {
        is_float = 1;
        --end;
    }
    if (i >= end) return 0;
    double whole = 0, fraction = 0, scale = 1;
    int any = 0, dot = 0;
    for (; i < end; ++i) {
        if (t[i] == L'.' && !dot) {
            dot = is_float = 1;
            continue;
        }
        if (!digit(t[i])) return 0;
        any = 1;
        if (dot) {
            scale /= 10.0;
            fraction += (double)(t[i] - L'0') * scale;
        } else {
            whole = whole * 10.0 + (double)(t[i] - L'0');
        }
    }
    if (!any) return 0;
    double value = whole + fraction;
    if (negative) value = -value;
    if (is_float) {
        *bits = f2b((float)value);
    } else {
        if (value > 4294967295.0 || value < -2147483648.0) return 0;
        *bits = value < 0 ? (uint32_t)(int32_t)value : (uint32_t)value;
    }
    return 1;
}

static int parse_operand(FfbVm *vm, const wchar_t *t, size_t n, FfbOperand *out) {
    out->kind = K_NONE;
    out->index = 0;
    out->bits = 0;
    if (n >= 3 && t[0] == L'{' && t[n - 1] == L'}') {
        int index = ffb_vm_param(vm, t + 1, n - 2);
        if (index < 0) return 0;
        out->kind = K_PARAM;
        out->index = (unsigned char)index;
        return 1;
    }
    if (n == 2 && upper(t[0]) == L'L' && t[1] >= L'0' && t[1] <= L'7') {
        out->kind = K_L;
        out->index = (unsigned char)(t[1] - L'0');
        return 1;
    }
    if (n == 2 && upper(t[0]) == L'E' && t[1] >= L'0' && t[1] <= L'3') {
        out->kind = K_E;
        out->index = (unsigned char)(t[1] - L'0');
        return 1;
    }
    if (word_is(t, n, "LT")) return out->kind = K_LT, 1;
    if (word_is(t, n, "ET")) return out->kind = K_ET, 1;
    if (word_is(t, n, "AD")) return out->kind = K_AD, 1;
    if (word_is(t, n, "AF")) return out->kind = K_AF, 1;
    if (word_is(t, n, "AF+")) return out->kind = K_AFADD, 1;
    if (parse_number(t, n, &out->bits)) return out->kind = K_IMM, 1;
    return 0;
}

static int space(wchar_t c) {
    return c == L' ' || c == L'\t' || c == L'\r' || c == L'\n';
}

static void next_token(const wchar_t *text, size_t length, size_t *at, size_t *start, size_t *n) {
    size_t i = *at;
    while (i < length && text[i] && space(text[i])) ++i;
    *start = i;
    while (i < length && text[i] && !space(text[i])) ++i;
    *n = i - *start;
    *at = i;
}

void ffb_vm_clear(FfbVm *vm, unsigned slot) {
    if (slot >= FFB_VM_SLOTS) return;
    FfbProgram *p = &vm->program[slot];
    p->loaded = 0;
    p->broken = 0;
    p->length = 0;
}

int ffb_vm_load(FfbVm *vm, unsigned slot, const wchar_t *text, size_t length, size_t *error_at) {
    if (slot >= FFB_VM_SLOTS) return 0;
    FfbProgram *p = &vm->program[slot];
    ffb_vm_clear(vm, slot);
    unsigned count = 0;
    size_t at = 0, start, n;
    for (;;) {
        next_token(text, length, &at, &start, &n);
        if (!n) break;
        int op = -1;
        for (int k = 0; k < OP_COUNT; ++k) {
            if (word_is(text + start, n, ops[k].name)) {
                op = k;
                break;
            }
        }
        if (op < 0 || count >= FFB_VM_CODE) {
            if (error_at) *error_at = start;
            p->broken = 1;
            return 0;
        }
        FfbInstruction *ins = &p->code[count];
        ins->op = (unsigned char)op;
        ins->count = ops[op].count;
        for (unsigned k = 0; k < ops[op].count; ++k) {
            next_token(text, length, &at, &start, &n);
            if (!n || !parse_operand(vm, text + start, n, &ins->operand[k]) ||
                (ins->operand[k].kind == K_AFADD && (int)k != ops[op].destination) ||
                ((int)k == ops[op].destination && ins->operand[k].kind == K_IMM)) {
                if (error_at) *error_at = start;
                p->broken = 1;
                return 0;
            }
        }
        ++count;
    }
    p->length = count;
    p->e[0] = p->e[1] = p->e[2] = p->e[3] = 0;
    p->started = vm->now;
    p->loaded = count > 0;
    return 1;
}

/* ------------------------------------------------------------------ execution */

static uint32_t read_bits(const FfbVm *vm, const FfbProgram *p, const FfbOperand *o) {
    switch (o->kind) {
        case K_IMM: return o->bits;
        case K_L: return vm->l[o->index];
        case K_E: return p->e[o->index];
        case K_LT: return vm->now;
        case K_ET: return vm->now - p->started;
        case K_AD: return f2b(vm->position);
        case K_AF: return f2b(vm->force);
        case K_PARAM: {
            const FfbParameter *q = &vm->param[o->index];
            float value = b2f(q->bits);
            return q->scale != 1.0f ? f2b(value * q->scale) : q->bits;
        }
    }
    return 0;
}

static float read_float(const FfbVm *vm, const FfbProgram *p, const FfbOperand *o) {
    float value = b2f(read_bits(vm, p, o));
    return finite(value) ? value : 0.0f;
}

static void write_bits(FfbVm *vm, FfbProgram *p, const FfbOperand *o, uint32_t bits) {
    switch (o->kind) {
        case K_L: vm->l[o->index] = bits; break;
        case K_E: p->e[o->index] = bits; break;
        case K_AF: vm->force = finite(b2f(bits)) ? b2f(bits) : 0.0f; break;
        case K_AFADD:
            if (finite(b2f(bits))) vm->force += b2f(bits);
            break;
        case K_PARAM: vm->param[o->index].bits = bits; break;
        default: break; /* Lt, Et, Ad and numbers are read-only */
    }
}

static float square_root(float a) {
    float r;
    __asm__("sqrtss %1, %0" : "=x"(r) : "x"(a));
    return r;
}

static float fmodulo(float a, float b) {
    if (b == 0.0f) return 0.0f;
    float q = a / b;
    if (!(q < 8388608.0f && q > -8388608.0f)) return 0.0f;
    long long whole = (long long)q; /* truncation towards zero, like fmodf */
    return a - (float)whole * b;
}

static uint32_t truth(int value) {
    return f2b(value ? 1.0f : 0.0f);
}

static void run(FfbVm *vm, FfbProgram *p) {
    unsigned budget = 4 * FFB_VM_CODE; /* programs only skip forward, but be safe */
    for (unsigned pc = 0; pc < p->length && budget--;) {
        const FfbInstruction *ins = &p->code[pc++];
        const FfbOperand *o = ins->operand;
        float a, b;
        switch (ins->op) {
            case OP_NOP: break;
            case OP_SKP: pc += read_bits(vm, p, &o[0]); break;
            case OP_SKPZ:
                if (read_bits(vm, p, &o[0]) == 0 || read_float(vm, p, &o[0]) == 0.0f) pc += read_bits(vm, p, &o[1]);
                break;
            case OP_SKPN:
                if (!(read_bits(vm, p, &o[0]) == 0 || read_float(vm, p, &o[0]) == 0.0f)) pc += read_bits(vm, p, &o[1]);
                break;
            case OP_END: return;
            case OP_ENDZ:
                if (read_bits(vm, p, &o[0]) == 0 || read_float(vm, p, &o[0]) == 0.0f) return;
                break;
            case OP_ENDN:
                if (!(read_bits(vm, p, &o[0]) == 0 || read_float(vm, p, &o[0]) == 0.0f)) return;
                break;
            case OP_ADD: write_bits(vm, p, &o[2], f2b(read_float(vm, p, &o[0]) + read_float(vm, p, &o[1]))); break;
            case OP_SUB: write_bits(vm, p, &o[2], f2b(read_float(vm, p, &o[0]) - read_float(vm, p, &o[1]))); break;
            case OP_MUL: write_bits(vm, p, &o[2], f2b(read_float(vm, p, &o[0]) * read_float(vm, p, &o[1]))); break;
            case OP_DIV:
                b = read_float(vm, p, &o[1]);
                write_bits(vm, p, &o[2], f2b(b != 0.0f ? read_float(vm, p, &o[0]) / b : 0.0f));
                break;
            case OP_MOD:
            case OP_MOD_FL:
                write_bits(vm, p, &o[2], f2b(fmodulo(read_float(vm, p, &o[0]), read_float(vm, p, &o[1]))));
                break;
            case OP_MOD_DW: {
                uint32_t d = read_bits(vm, p, &o[1]);
                write_bits(vm, p, &o[2], d ? read_bits(vm, p, &o[0]) % d : 0);
                break;
            }
            case OP_POW2: a = read_float(vm, p, &o[0]); write_bits(vm, p, &o[1], f2b(a * a)); break;
            case OP_POW3: a = read_float(vm, p, &o[0]); write_bits(vm, p, &o[1], f2b(a * a * a)); break;
            case OP_SQRT:
                a = read_float(vm, p, &o[0]);
                write_bits(vm, p, &o[1], f2b(a > 0.0f ? square_root(a) : 0.0f));
                break;
            case OP_SGN:
                a = read_float(vm, p, &o[0]);
                write_bits(vm, p, &o[1], f2b(a > 0.0f ? 1.0f : a < 0.0f ? -1.0f : 0.0f));
                break;
            case OP_ABS: a = read_float(vm, p, &o[0]); write_bits(vm, p, &o[1], f2b(a < 0.0f ? -a : a)); break;
            case OP_INV:
                a = read_float(vm, p, &o[0]);
                write_bits(vm, p, &o[1], f2b(a != 0.0f ? 1.0f / a : 0.0f));
                break;
            case OP_AND: write_bits(vm, p, &o[2], truth(read_float(vm, p, &o[0]) != 0.0f && read_float(vm, p, &o[1]) != 0.0f)); break;
            case OP_OR: write_bits(vm, p, &o[2], truth(read_float(vm, p, &o[0]) != 0.0f || read_float(vm, p, &o[1]) != 0.0f)); break;
            case OP_NAND: write_bits(vm, p, &o[2], truth(!(read_float(vm, p, &o[0]) != 0.0f && read_float(vm, p, &o[1]) != 0.0f))); break;
            case OP_NOR: write_bits(vm, p, &o[2], truth(!(read_float(vm, p, &o[0]) != 0.0f || read_float(vm, p, &o[1]) != 0.0f))); break;
            case OP_XOR: write_bits(vm, p, &o[2], truth((read_float(vm, p, &o[0]) != 0.0f) != (read_float(vm, p, &o[1]) != 0.0f))); break;
            case OP_NXOR: write_bits(vm, p, &o[2], truth((read_float(vm, p, &o[0]) != 0.0f) == (read_float(vm, p, &o[1]) != 0.0f))); break;
            case OP_NOT: write_bits(vm, p, &o[1], truth(read_float(vm, p, &o[0]) == 0.0f)); break;
            case OP_GT: write_bits(vm, p, &o[2], truth(read_float(vm, p, &o[0]) > read_float(vm, p, &o[1]))); break;
            case OP_GTE: write_bits(vm, p, &o[2], truth(read_float(vm, p, &o[0]) >= read_float(vm, p, &o[1]))); break;
            case OP_LT: write_bits(vm, p, &o[2], truth(read_float(vm, p, &o[0]) < read_float(vm, p, &o[1]))); break;
            case OP_LTE: write_bits(vm, p, &o[2], truth(read_float(vm, p, &o[0]) <= read_float(vm, p, &o[1]))); break;
            case OP_EQ: write_bits(vm, p, &o[2], truth(read_float(vm, p, &o[0]) == read_float(vm, p, &o[1]))); break;
            case OP_BAND: write_bits(vm, p, &o[2], read_bits(vm, p, &o[0]) & read_bits(vm, p, &o[1])); break;
            case OP_BOR: write_bits(vm, p, &o[2], read_bits(vm, p, &o[0]) | read_bits(vm, p, &o[1])); break;
            case OP_BXOR: write_bits(vm, p, &o[2], read_bits(vm, p, &o[0]) ^ read_bits(vm, p, &o[1])); break;
            case OP_BNOT: write_bits(vm, p, &o[1], ~read_bits(vm, p, &o[0])); break;
            case OP_MOV: write_bits(vm, p, &o[1], read_bits(vm, p, &o[0])); break;
            case OP_TOFL: write_bits(vm, p, &o[1], f2b((float)read_bits(vm, p, &o[0]))); break;
            case OP_TODW: {
                a = read_float(vm, p, &o[0]);
                uint32_t v = a <= 0.0f ? 0 : a >= 4294967040.0f ? 0xffffffffu : (uint32_t)a;
                write_bits(vm, p, &o[1], v);
                break;
            }
        }
    }
}

float ffb_vm_tick(FfbVm *vm, float position) {
    vm->now += FFB_VM_TICK_MS;
    vm->position = finite(position) ? position : 0.0f;
    vm->force = 0.0f;
    for (unsigned slot = 0; slot < FFB_VM_SLOTS; ++slot) {
        FfbProgram *p = &vm->program[slot];
        if (p->loaded && !p->broken) run(vm, p);
    }
    ++vm->ticks;
    return finite(vm->force) ? vm->force : 0.0f;
}

unsigned ffb_vm_loaded(const FfbVm *vm) {
    unsigned n = 0;
    for (unsigned slot = 0; slot < FFB_VM_SLOTS; ++slot) n += vm->program[slot].loaded && !vm->program[slot].broken;
    return n;
}
