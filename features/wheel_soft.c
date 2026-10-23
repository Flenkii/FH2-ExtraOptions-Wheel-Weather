/* Own implementation of Microsoft.Xbox.Input.Wheel - see wheel_soft.h.

   Byte layout of the reports (payload after the 0x14 byte GIP header), as Microsoft's DLL reads it:
     input report 0x20 (17 bytes)
       [0]  bit2 Menu, bit3 View, bit4 A, bit5 B, bit6 X, bit7 Y
       [1]  bit0-3 d-pad up/down/left/right, bit4 left paddle, bit5 right paddle
       [2..3] wheel  [4..5] throttle  [6..7] brake  [8..9] clutch  [0xa] handbrake
       [0xb] bit0-4 pattern shifter, bit5-7 shifter type  [0xc] gear  [0xd..e] rotation in degrees
       [0xf] force feedback strength (0..255)  [0x10] bit3..7 flags
     static configuration 0x21 (11 bytes)
       [0..4] bits of wheel/throttle/brake/clutch/handbrake  [5..6] min, [7..8] max rotation
       [9] force feedback  [0xa] flags (bit7, bit6, bit3, bit0-2 shifter type) */
#include "wheel_soft.h"

#include <stdint.h>

typedef HRESULT(WINAPI *QIFn)(void *, const GUID *, void **);
typedef ULONG(WINAPI *RefFn)(void *);
#define VT(p) (*(void ***)(p))

static const GUID IID_Unknown_ = {0x00000000, 0x0000, 0x0000, {0xc0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46}};
static const GUID IID_Inspectable_ = {0xaf86e2e0, 0xb12d, 0x4c6a, {0x9c, 0x5a, 0xd7, 0xaa, 0x65, 0x10, 0x1e, 0x90}};
static const GUID IID_Agile_ = {0x94ea2b94, 0xe9cc, 0x49e0, {0xc0, 0xff, 0xee, 0x64, 0xca, 0x8f, 0x5b, 0x90}};
static const GUID IID_Wheel_ = {0x646979cf, 0x6b71, 0x4e96, {0x8d, 0xf9, 0x59, 0xe3, 0x98, 0xd7, 0x42, 0x0c}};
static const GUID IID_WheelReading_ = {0x15198dca, 0xa85c, 0x455d, {0xa2, 0xab, 0xd1, 0xcb, 0x90, 0x7f, 0xc6, 0xd0}};
static const GUID IID_WheelConfig_ = {0xd45f6e0b, 0xffb6, 0x425f, {0xb1, 0xd9, 0x33, 0x6d, 0xd5, 0xf8, 0xae, 0xbb}};
static const GUID IID_NavController_ = {0xb8f31fe7, 0x7386, 0x40e9, {0xa9, 0xf8, 0x2f, 0x21, 0x26, 0x3a, 0xcf, 0xb7}};
static const GUID IID_InputHandler_ = {0x1c529a33, 0x97f3, 0x4a0f, {0x86, 0x6a, 0x87, 0xb1, 0xdb, 0x9c, 0xc1, 0x78}};
static const GUID IID_DeviceInfo_ = {0x568e38dc, 0xe9c8, 0x4f00, {0x92, 0x3c, 0x09, 0x01, 0x86, 0xde, 0x11, 0x44}};

#define REPORT_SIZE 0x11
#define CONFIG_SIZE 0x0b

static int same_guid(const GUID *a, const GUID *b) {
    const unsigned char *x = (const unsigned char *)a, *y = (const unsigned char *)b;
    for (int i = 0; i < 16; ++i)
        if (x[i] != y[i]) return 0;
    return 1;
}
static void copy_bytes(void *to, const void *from, size_t n) {
    volatile unsigned char *t = to;
    const unsigned char *f = from;
    while (n--) *t++ = *f++;
}
static void clear_bytes(void *to, size_t n) {
    volatile unsigned char *t = to;
    while (n--) *t++ = 0;
}

/* ------------------------------------------------------------------ the wheel object */

typedef struct Snapshot Snapshot;
static struct {
    void **wheel_vtbl; /* IWheel */
    void **nav_vtbl;   /* INavigationController */
    void **input_vtbl; /* IInputHandler */
    void **inner_vtbl; /* non-delegating IInspectable */
    void *outer;
    WheelSoftEnv env;
    SRWLOCK lock;
    unsigned char report[REPORT_SIZE], config[CONFIG_SIZE];
    int have_config;
    uint64_t stamp; /* local FILETIME of the last report, like the DLL */
    Snapshot *reading;
    volatile LONG tokens;
} wheel;

/* reading and static configuration: immutable copies, reference counted */
struct Snapshot {
    void **vtbl;
    volatile LONG refs;
    unsigned char r[REPORT_SIZE], c[CONFIG_SIZE];
    uint64_t stamp;
};

static Snapshot *snapshot_new(void **vtbl) {
    Snapshot *s = HeapAlloc(GetProcessHeap(), 0, sizeof(Snapshot));
    if (!s) return NULL;
    clear_bytes(s, sizeof(*s));
    s->vtbl = vtbl;
    s->refs = 1;
    copy_bytes(s->r, wheel.report, REPORT_SIZE);
    copy_bytes(s->c, wheel.config, CONFIG_SIZE);
    s->stamp = wheel.stamp;
    return s;
}
static ULONG WINAPI snap_addref(Snapshot *s) {
    return (ULONG)InterlockedIncrement(&s->refs);
}
static ULONG WINAPI snap_release(Snapshot *s) {
    LONG n = InterlockedDecrement(&s->refs);
    if (!n) HeapFree(GetProcessHeap(), 0, s);
    return (ULONG)n;
}
static HRESULT snap_qi(Snapshot *s, const GUID *iid, void **out, const GUID *own) {
    if (!out) return E_POINTER;
    if (same_guid(iid, &IID_Unknown_) || same_guid(iid, &IID_Inspectable_) || same_guid(iid, &IID_Agile_) ||
        same_guid(iid, own)) {
        snap_addref(s);
        *out = s;
        return S_OK;
    }
    *out = NULL;
    return E_NOINTERFACE;
}
static HRESULT WINAPI any_iids(void *self, ULONG *count, GUID **iids) {
    (void)self;
    if (count) *count = 0;
    if (iids) *iids = NULL;
    return S_OK;
}
static HRESULT class_name(void **out, const wchar_t *name) {
    if (!out) return E_POINTER;
    *out = wheel.env.make_string ? wheel.env.make_string(name) : NULL;
    return *out ? S_OK : E_OUTOFMEMORY;
}
static HRESULT WINAPI any_trust(void *self, int *level) {
    (void)self;
    if (!level) return E_POINTER;
    *level = 0;
    return S_OK;
}

/* IWheelReading */
static HRESULT WINAPI rd_qi(Snapshot *s, const GUID *iid, void **out) {
    return snap_qi(s, iid, out, &IID_WheelReading_);
}
static HRESULT WINAPI rd_name(void *self, void **out) {
    (void)self;
    return class_name(out, L"Microsoft.Xbox.Input.WheelReading");
}
#define BIT_GETTER(fn, byte, bit) \
    static HRESULT WINAPI fn(Snapshot *s, unsigned char *out) { \
        if (!out) return E_POINTER; \
        *out = (unsigned char)((s->r[byte] >> (bit)) & 1); \
        return S_OK; \
    }
BIT_GETTER(rd_a, 0, 4)
BIT_GETTER(rd_b, 0, 5)
BIT_GETTER(rd_x, 0, 6)
BIT_GETTER(rd_y, 0, 7)
BIT_GETTER(rd_view, 0, 3)
BIT_GETTER(rd_menu, 0, 2)
BIT_GETTER(rd_up, 1, 0)
BIT_GETTER(rd_down, 1, 1)
BIT_GETTER(rd_left, 1, 2)
BIT_GETTER(rd_right, 1, 3)
BIT_GETTER(rd_flag3, 0x10, 3)
BIT_GETTER(rd_flag7, 0x10, 7)
BIT_GETTER(rd_flag6, 0x10, 6)
BIT_GETTER(rd_flag5, 0x10, 5)
BIT_GETTER(rd_flag4, 0x10, 4)
BIT_GETTER(rd_paddle_left, 1, 4)
BIT_GETTER(rd_paddle_right, 1, 5)

static float axis_value(unsigned raw, unsigned bits) {
    if (bits < 1 || bits > 16) return 0.0f;
    return (float)raw / (float)((1u << bits) - 1);
}
static unsigned u16_at(const unsigned char *p) {
    return p[0] | (unsigned)p[1] << 8;
}
static HRESULT WINAPI rd_wheel(Snapshot *s, float *out) {
    if (!out) return E_POINTER;
    unsigned bits = s->c[0];
    *out = bits >= 1 && bits <= 16 ? (float)u16_at(s->r + 2) * 2.0f / (float)((1u << bits) - 1) - 1.0f : 0.0f;
    return S_OK;
}
static HRESULT WINAPI rd_rotation(Snapshot *s, UINT32 *out) {
    if (!out) return E_POINTER;
    *out = u16_at(s->r + 0xd);
    return S_OK;
}
static HRESULT WINAPI rd_throttle(Snapshot *s, float *out) {
    if (!out) return E_POINTER;
    *out = axis_value(u16_at(s->r + 4), s->c[1]);
    return S_OK;
}
static HRESULT WINAPI rd_brake(Snapshot *s, float *out) {
    if (!out) return E_POINTER;
    *out = axis_value(u16_at(s->r + 6), s->c[2]);
    return S_OK;
}
static HRESULT WINAPI rd_clutch(Snapshot *s, float *out) {
    if (!out) return E_POINTER;
    *out = axis_value(u16_at(s->r + 8), s->c[3]);
    return S_OK;
}
static HRESULT WINAPI rd_handbrake(Snapshot *s, float *out) {
    if (!out) return E_POINTER;
    *out = axis_value(s->r[0xa], s->c[4]);
    return S_OK;
}
static HRESULT WINAPI rd_ffb(Snapshot *s, float *out) {
    if (!out) return E_POINTER;
    *out = (float)s->r[0xf] * (1.0f / 255.0f);
    return S_OK;
}
static HRESULT WINAPI rd_shifter_type(Snapshot *s, INT32 *out) {
    if (!out) return E_POINTER;
    unsigned v = s->r[0xb] >> 5;
    *out = (INT32)(v > 6 ? 6 : v);
    return S_OK;
}
static HRESULT WINAPI rd_pattern(Snapshot *s, unsigned char *out) {
    if (!out) return E_POINTER;
    *out = (unsigned char)(s->r[0xb] & 0x1f);
    return S_OK;
}
static HRESULT WINAPI rd_gear(Snapshot *s, unsigned char *out) {
    if (!out) return E_POINTER;
    *out = s->r[0xc];
    return S_OK;
}
static HRESULT WINAPI rd_time(Snapshot *s, uint64_t *out) {
    if (!out) return E_POINTER;
    *out = s->stamp;
    return S_OK;
}
static void *reading_vtbl[34] = {
    (void *)rd_qi,        (void *)snap_addref,     (void *)snap_release,     (void *)any_iids,
    (void *)rd_name,      (void *)any_trust,       (void *)rd_a,             (void *)rd_b,
    (void *)rd_x,         (void *)rd_y,            (void *)rd_view,          (void *)rd_menu,
    (void *)rd_up,        (void *)rd_down,         (void *)rd_left,          (void *)rd_right,
    (void *)rd_wheel,     (void *)rd_rotation,     (void *)rd_throttle,      (void *)rd_brake,
    (void *)rd_clutch,    (void *)rd_handbrake,    (void *)rd_ffb,           (void *)rd_flag3,
    (void *)rd_flag7,     (void *)rd_flag6,        (void *)rd_flag5,         (void *)rd_flag4,
    (void *)rd_paddle_left, (void *)rd_paddle_right, (void *)rd_shifter_type, (void *)rd_pattern,
    (void *)rd_gear,      (void *)rd_time};

/* IWheelStaticConfiguration */
static HRESULT WINAPI cf_qi(Snapshot *s, const GUID *iid, void **out) {
    return snap_qi(s, iid, out, &IID_WheelConfig_);
}
static HRESULT WINAPI cf_name(void *self, void **out) {
    (void)self;
    return class_name(out, L"Microsoft.Xbox.Input.WheelStaticConfiguration");
}
#define BYTE_GETTER(fn, byte) \
    static HRESULT WINAPI fn(Snapshot *s, unsigned char *out) { \
        if (!out) return E_POINTER; \
        *out = s->c[byte]; \
        return S_OK; \
    }
BYTE_GETTER(cf_wheel_bits, 0)
BYTE_GETTER(cf_throttle_bits, 1)
BYTE_GETTER(cf_brake_bits, 2)
BYTE_GETTER(cf_clutch_bits, 3)
BYTE_GETTER(cf_handbrake_bits, 4)
BYTE_GETTER(cf_ffb_byte, 9)
static HRESULT WINAPI cf_min_rotation(Snapshot *s, UINT32 *out) {
    if (!out) return E_POINTER;
    *out = u16_at(s->c + 5);
    return S_OK;
}
static HRESULT WINAPI cf_max_rotation(Snapshot *s, UINT32 *out) {
    if (!out) return E_POINTER;
    *out = u16_at(s->c + 7);
    return S_OK;
}
#define FLAG_GETTER(fn, expr) \
    static HRESULT WINAPI fn(Snapshot *s, unsigned char *out) { \
        if (!out) return E_POINTER; \
        *out = (unsigned char)(expr); \
        return S_OK; \
    }
FLAG_GETTER(cf_flag7, s->c[0xa] >> 7)
FLAG_GETTER(cf_flag6, (s->c[0xa] >> 6) & 1)
FLAG_GETTER(cf_has_clutch, s->c[3] != 0)
FLAG_GETTER(cf_has_handbrake, s->c[4] != 0)
FLAG_GETTER(cf_flag3, (s->c[0xa] >> 3) & 1)
FLAG_GETTER(cf_shifter, (s->c[0xa] & 7) == 1 || (s->c[0xa] & 7) == 3 ? 1 : (s->c[0xa] & 7) == 2 || (s->c[0xa] & 7) == 4 ? 2 : 0)
FLAG_GETTER(cf_shifter_hi, (unsigned char)((s->c[0xa] & 7) - 3) <= 1)
FLAG_GETTER(cf_has_ffb, s->c[9] != 0)
static void *config_vtbl[22] = {
    (void *)cf_qi,           (void *)snap_addref,       (void *)snap_release,     (void *)any_iids,
    (void *)cf_name,         (void *)any_trust,         (void *)cf_wheel_bits,    (void *)cf_throttle_bits,
    (void *)cf_brake_bits,   (void *)cf_clutch_bits,    (void *)cf_handbrake_bits, (void *)cf_min_rotation,
    (void *)cf_max_rotation, (void *)cf_flag7,          (void *)cf_flag6,         (void *)cf_has_clutch,
    (void *)cf_has_handbrake, (void *)cf_flag3,         (void *)cf_shifter,       (void *)cf_shifter_hi,
    (void *)cf_has_ffb,      (void *)cf_ffb_byte};

/* ------------------------------------------------------------------ interfaces of the wheel */

/* every interface delegates IUnknown to the controlling object (aggregation) */
static HRESULT WINAPI outer_qi(void *self, const GUID *iid, void **out) {
    (void)self;
    return ((QIFn)VT(wheel.outer)[0])(wheel.outer, iid, out);
}
static ULONG WINAPI outer_addref(void *self) {
    (void)self;
    return ((RefFn)VT(wheel.outer)[1])(wheel.outer);
}
static ULONG WINAPI outer_release(void *self) {
    (void)self;
    return ((RefFn)VT(wheel.outer)[2])(wheel.outer);
}
static HRESULT WINAPI wh_name(void *self, void **out) {
    (void)self;
    return class_name(out, L"Microsoft.Xbox.Input.Wheel");
}
static HRESULT WINAPI wh_one(void *self, UINT32 *out) {
    (void)self;
    if (!out) return E_POINTER;
    *out = 1;
    return S_OK;
}
static HRESULT WINAPI wh_zero(void *self, UINT32 *out) {
    (void)self;
    if (!out) return E_POINTER;
    *out = 0;
    return S_OK;
}
static HRESULT WINAPI wh_three(void *self, UINT32 *out) {
    (void)self;
    if (!out) return E_POINTER;
    *out = 3;
    return S_OK;
}
static HRESULT WINAPI wh_false(void *self, unsigned char *out) {
    (void)self;
    if (!out) return E_POINTER;
    *out = 0;
    return S_OK;
}
/* device info words (VID, PID, firmware) come from the controlling object, like in the DLL */
static HRESULT device_info(unsigned char *info) {
    clear_bytes(info, 16);
    void *dev = NULL;
    HRESULT hr = ((QIFn)VT(wheel.outer)[0])(wheel.outer, &IID_DeviceInfo_, &dev);
    if (hr < 0 || !dev) return hr < 0 ? hr : E_NOINTERFACE;
    hr = ((HRESULT(WINAPI *)(void *, void *))VT(dev)[4])(dev, info);
    ((RefFn)VT(dev)[2])(dev);
    return hr;
}
static HRESULT WINAPI wh_product(void *self, UINT32 *out) {
    (void)self;
    unsigned char info[16];
    HRESULT hr = device_info(info);
    if (hr >= 0 && out) *out = u16_at(info + 2) << 16 | u16_at(info + 4);
    return hr;
}
static HRESULT WINAPI wh_firmware(void *self, UINT32 *out) {
    (void)self;
    unsigned char info[16];
    HRESULT hr = device_info(info);
    if (hr >= 0 && out) *out = u16_at(info + 0xc);
    return hr;
}
static HRESULT WINAPI wh_reading(void *self, void **out) {
    (void)self;
    if (!out) return E_POINTER;
    *out = NULL;
    AcquireSRWLockExclusive(&wheel.lock);
    if (!wheel.reading) wheel.reading = snapshot_new(reading_vtbl);
    Snapshot *s = wheel.reading;
    if (s) snap_addref(s);
    ReleaseSRWLockExclusive(&wheel.lock);
    *out = s;
    return s ? S_OK : E_OUTOFMEMORY;
}
static HRESULT WINAPI wh_config(void *self, void **out) {
    (void)self;
    if (!out) return E_POINTER;
    *out = NULL;
    AcquireSRWLockExclusive(&wheel.lock);
    Snapshot *s = wheel.have_config ? snapshot_new(config_vtbl) : NULL;
    int have = wheel.have_config;
    ReleaseSRWLockExclusive(&wheel.lock);
    if (!have) return (HRESULT)0x8007139f; /* not available yet, like the DLL */
    *out = s;
    return s ? S_OK : E_OUTOFMEMORY;
}
static HRESULT WINAPI wh_ok_u32(void *self, UINT32 value) {
    (void)self;
    (void)value;
    return S_OK;
}
static HRESULT WINAPI wh_ok_float(void *self, float value) {
    (void)self;
    (void)value;
    return S_OK;
}
/* event add/remove pairs: accepted, never raised */
static HRESULT WINAPI wh_add_event(void *self, void *handler, int64_t *token) {
    (void)self;
    (void)handler;
    if (!token) return E_POINTER;
    *token = InterlockedIncrement(&wheel.tokens);
    return S_OK;
}
static HRESULT WINAPI wh_remove_event(void *self, int64_t token) {
    (void)self;
    (void)token;
    return S_OK;
}
/* force feedback programs: slot 0..15 */
static HRESULT WINAPI wh_set_program(void *self, UINT8 slot, void *program, UINT32 flags, UINT32 *size) {
    (void)self;
    (void)flags;
    if (size) *size = 0;
    if (slot >= 16) return E_INVALIDARG;
    if (!program) return E_INVALIDARG;
    if (size) *size = 16;
    return S_OK;
}
static HRESULT WINAPI wh_slot(void *self, UINT8 slot) {
    (void)self;
    return slot < 16 ? S_OK : E_INVALIDARG;
}
static HRESULT WINAPI wh_ok(void *self) {
    (void)self;
    return S_OK;
}
static HRESULT WINAPI wh_param(void *self, void *name) {
    (void)self;
    return name ? S_OK : E_INVALIDARG;
}
static HRESULT WINAPI wh_param_u32(void *self, void *name, UINT32 value) {
    (void)self;
    (void)value;
    return name ? S_OK : E_INVALIDARG;
}
static HRESULT WINAPI wh_set_param(void *self, void *name, float value) {
    (void)self;
    (void)value;
    return name ? S_OK : E_INVALIDARG;
}
static HRESULT WINAPI wh_param_out(void *self, void *name, UINT32 *out) {
    (void)self;
    (void)name;
    if (out) *out = 0;
    return S_OK;
}
static HRESULT WINAPI wh_index_out(void *self, UINT32 index, void **out) {
    (void)self;
    if (out) *out = NULL;
    return index < 0x200 ? E_NOTIMPL : E_INVALIDARG;
}
/* slot 41: send queued messages; nothing is queued here */
static HRESULT WINAPI wh_flush(void *self, UINT8 max, UINT8 *pending) {
    (void)self;
    (void)max;
    if (!pending) return E_POINTER;
    *pending = 0;
    return S_OK;
}
static HRESULT WINAPI wh_notimpl(void *self) {
    (void)self;
    return E_NOTIMPL;
}
static void *wheel_vtbl[50] = {
    (void *)outer_qi,        (void *)outer_addref,    (void *)outer_release,   (void *)any_iids,
    (void *)wh_name,         (void *)any_trust,       (void *)wh_one,          (void *)wh_zero,
    (void *)wh_three,        (void *)wh_false,        (void *)wh_product,      (void *)wh_firmware,
    (void *)wh_reading,      (void *)wh_config,       (void *)wh_ok_u32,       (void *)wh_ok_float,
    (void *)wh_add_event,    (void *)wh_remove_event, (void *)wh_add_event,    (void *)wh_remove_event,
    (void *)wh_add_event,    (void *)wh_remove_event, (void *)wh_add_event,    (void *)wh_remove_event,
    (void *)wh_add_event,    (void *)wh_remove_event, (void *)wh_set_program,  (void *)wh_slot,
    (void *)wh_slot,         (void *)wh_slot,         (void *)wh_slot,         (void *)wh_slot,
    (void *)wh_ok,           (void *)wh_ok,           (void *)wh_add_event,    (void *)wh_remove_event,
    (void *)wh_param,        (void *)wh_param_u32,    (void *)wh_set_param,    (void *)wh_param_out,
    (void *)wh_index_out,    (void *)wh_flush,        (void *)wh_ok,           (void *)wh_notimpl,
    (void *)wh_notimpl,      (void *)wh_notimpl,      (void *)wh_notimpl,      (void *)wh_notimpl,
    (void *)wh_notimpl,      (void *)wh_notimpl};

/* INavigationController */
static HRESULT WINAPI nav_name(void *self, void **out) {
    return wh_name(self, out);
}
static HRESULT WINAPI nav_reading(void *self, void **out) {
    (void)self;
    if (out) *out = NULL;
    return E_NOTIMPL;
}
static HRESULT WINAPI nav_raw(void *self, unsigned char *out) {
    (void)self;
    if (!out) return E_POINTER;
    AcquireSRWLockShared(&wheel.lock);
    uint64_t stamp = wheel.stamp;
    UINT32 buttons = (wheel.report[0] & 0xfcu) | (wheel.report[1] & 0x3fu) << 8;
    ReleaseSRWLockShared(&wheel.lock);
    copy_bytes(out, &stamp, 8);
    copy_bytes(out + 8, &buttons, 4);
    return S_OK;
}
static void *nav_vtbl[8] = {(void *)outer_qi, (void *)outer_addref, (void *)outer_release, (void *)any_iids,
                            (void *)nav_name, (void *)any_trust,    (void *)nav_reading,   (void *)nav_raw};

/* IInputHandler: the reports of the bridge */
static HRESULT WINAPI input_name(void *self, void **out) {
    return wh_name(self, out);
}
static HRESULT WINAPI input_report(void *self, UINT32 size, const unsigned char *packet) {
    (void)self;
    if (size < 0x14) return E_INVALIDARG;
    if (!packet) return E_POINTER;
    UINT32 length;
    copy_bytes(&length, packet + 0xc, 4);
    if (length > size - 0x14) length = size - 0x14;
    Snapshot *old = NULL;
    if (packet[8] == 0x20 && length >= REPORT_SIZE) {
        FILETIME now, local;
        GetSystemTimeAsFileTime(&now);
        if (!FileTimeToLocalFileTime(&now, &local)) local = now;
        AcquireSRWLockExclusive(&wheel.lock);
        copy_bytes(wheel.report, packet + 0x14, REPORT_SIZE);
        wheel.stamp = (uint64_t)local.dwHighDateTime << 32 | local.dwLowDateTime;
        old = wheel.reading;
        wheel.reading = NULL;
        ReleaseSRWLockExclusive(&wheel.lock);
    } else if (packet[8] == 0x21 && length >= CONFIG_SIZE) {
        AcquireSRWLockExclusive(&wheel.lock);
        copy_bytes(wheel.config, packet + 0x14, CONFIG_SIZE);
        wheel.have_config = 1;
        old = wheel.reading;
        wheel.reading = NULL;
        ReleaseSRWLockExclusive(&wheel.lock);
    }
    if (old) snap_release(old);
    return S_OK;
}
static void *input_vtbl[7] = {(void *)outer_qi,   (void *)outer_addref, (void *)outer_release, (void *)any_iids,
                              (void *)input_name, (void *)any_trust,    (void *)input_report};

/* non-delegating IInspectable (what the controlling object holds) */
static HRESULT WINAPI inner_qi(void *self, const GUID *iid, void **out) {
    if (!out) return E_POINTER;
    void *found = NULL;
    if (same_guid(iid, &IID_Unknown_) || same_guid(iid, &IID_Inspectable_)) {
        *out = self;
        return S_OK;
    }
    if (same_guid(iid, &IID_Wheel_)) found = &wheel.wheel_vtbl;
    else if (same_guid(iid, &IID_NavController_)) found = &wheel.nav_vtbl;
    else if (same_guid(iid, &IID_InputHandler_)) found = &wheel.input_vtbl;
    *out = found;
    if (!found) return E_NOINTERFACE;
    outer_addref(NULL);
    return S_OK;
}
static ULONG WINAPI inner_addref(void *self) {
    (void)self;
    return 2;
}
static ULONG WINAPI inner_release(void *self) {
    (void)self;
    return 1;
}
static void *inner_vtbl[6] = {(void *)inner_qi, (void *)inner_addref, (void *)inner_release,
                              (void *)any_iids, (void *)wh_name,      (void *)any_trust};

void *wheel_soft_create(void *outer, const WheelSoftEnv *env) {
    if (!outer) return NULL;
    wheel.wheel_vtbl = wheel_vtbl;
    wheel.nav_vtbl = nav_vtbl;
    wheel.input_vtbl = input_vtbl;
    wheel.inner_vtbl = inner_vtbl;
    wheel.outer = outer;
    if (env) wheel.env = *env;
    clear_bytes(wheel.report, sizeof(wheel.report));
    clear_bytes(wheel.config, sizeof(wheel.config));
    wheel.report[3] = 0x80; /* wheel centred until the first report */
    wheel.have_config = 0;
    wheel.reading = NULL;
    return &wheel.inner_vtbl;
}

void **wheel_soft_wheel_table(void) {
    return wheel_vtbl;
}
