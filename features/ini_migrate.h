#ifndef FH2_INI_MIGRATE_H
#define FH2_INI_MIGRATE_H
#include <stddef.h>
#include <wchar.h>

/* English settings files (fork4): the German files of fork1-fork3 are taken over once.

     FH2_Lenkrad.ini  [Lenkrad]   ->  FH2_Wheel.ini     [Wheel]
     FH2_Tastatur.ini [Tastatur]  ->  FH2_Keyboard.ini  [Keyboard]
     FH2_ExtraOptions.ini [Traffic] Wetter=  ->  Weather=

   The new file is the mod's English default file with the user's values filled in (key names
   translated, German key names in keyboard bindings too). The old files (and the old wheel
   logs) are moved into the folder FH2_Settings_Backup next to the INIs, FH2_ExtraOptions.ini is
   copied there before its key is renamed. Nothing happens when a new file already exists.
   Safe to call more than once (only the first call per process does the work). */
void ini_migrate(const wchar_t *settings_directory);
/* Writes what ini_migrate did into FH2_ExtraOptions.log (after the log was started). */
void ini_migrate_log(void);

/* default file texts of the modules */
const char *wheel_bridge_default_ini(size_t *length);
size_t keyboard_default_ini(char *out, size_t capacity);
#endif
