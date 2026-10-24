/* fh2-mods\Gripline.dll - the FH2 Mod Platform's way in to Gripline.

   The platform loads every DLL in fh2-mods and calls its fh2mod_init. Gripline itself is the
   winmm.dll next to azimuth.exe, so this file only passes the platform API on to it
   (export GriplinePlatformAttach). Without Gripline's winmm.dll it registers a placeholder
   that says so on the title screen. */
#include <windows.h>
#include "../third_party/fh2mod/fh2mod.h"

typedef int (*AttachFn)(const FH2ModApi *);

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance;
    (void)reason;
    (void)reserved;
    return TRUE;
}

FH2MOD_EXPORT int fh2mod_init(const FH2ModApi *api) {
    HMODULE gripline = GetModuleHandleW(L"winmm.dll");
    AttachFn attach = gripline ? (AttachFn)(void *)GetProcAddress(gripline, "GriplinePlatformAttach") : NULL;
    if (attach) {
        return attach(api);
    }
    static FH2ModInfo info;
    info.size = sizeof(info);
    info.name = "Gripline";
    info.version = "missing";
    info.github_repo = "Flenkii/Gripline";
    info.description = "Gripline's winmm.dll is not next to azimuth.exe.";
    FH2Mod *mod = api && api->register_mod ? api->register_mod(&info) : NULL;
    if (mod) {
        api->log(mod, "Gripline's winmm.dll was not found next to azimuth.exe");
        api->set_notice(mod, "Gripline: winmm.dll missing");
    }
    return 0;
}
