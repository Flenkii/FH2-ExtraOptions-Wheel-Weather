#ifndef FH2_WHEEL_SOFT_H
#define FH2_WHEEL_SOFT_H
/* Own implementation of the Microsoft.Xbox.Input.Wheel class (the Xbox One racing wheel) for
   game copies without Microsoft.Xbox.Input.Wheel.dll in the Mount folder.

   It answers exactly what Microsoft's DLL answers to the game (worked out from the DLL's code):
   IWheel, IWheelReading, IWheelStaticConfiguration, INavigationController and IInputHandler.
   The wheel bridge feeds it with the same input reports (0x20) and static configuration
   (0x21) as the DLL. Force feedback programs and parameters (IWheel slots 26/36/38) are only
   accepted here; the bridge hooks those slots and runs the programs in ffb_vm.c, as with the
   DLL. Nothing is sent to a device. */
#include <windows.h>

typedef struct {
    void *(*make_string)(const wchar_t *text); /* HSTRING for GetRuntimeClassName */
} WheelSoftEnv;

/* Creates the (single) wheel object aggregated by `outer` (the controlling IInspectable) and
   returns its non-delegating IInspectable. */
void *wheel_soft_create(void *outer, const WheelSoftEnv *env);
/* IWheel method table of the object (the bridge patches slots 26/36/38 for the game FFB). */
void **wheel_soft_wheel_table(void);
#endif
