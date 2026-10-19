#include "runtime.h"
#include "support.h"

void wheel_bridge_shutdown(void);
void rig_settings_flush(void);

__declspec(dllexport) const char *Fh2TweaksStatus(void) {
    return status_get();
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        adapter_process_attach(instance);
    } else if (reason == DLL_PROCESS_DETACH) {
        wheel_bridge_shutdown();
        rig_settings_flush();
    }
    return TRUE;
}
