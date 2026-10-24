#ifndef FH2_PLATFORM_LINK_H
#define FH2_PLATFORM_LINK_H

/* FH2 Mod Platform (Trinculo54, MIT; d3dcompiler_47.dll next to azimuth.exe) link.

   The platform only loads DLLs from fh2-mods. Gripline ships a tiny fh2-mods\Gripline.dll
   (platform/gripline_mod.c) whose fh2mod_init hands the platform API to this winmm.dll
   (export GriplinePlatformAttach). Gripline then registers as a mod (MODS > Installed mods)
   and puts its settings page on the pause menu's tile that does nothing on PC
   ("Achievements"), as a GRIPLINE tile. Without the platform nothing changes: the settings
   stay at Options > HUD > bottom. */

/* 1 once the tile page is registered: the HUD page then leaves out Gripline's rows. */
int platform_page_active(void);

#endif
