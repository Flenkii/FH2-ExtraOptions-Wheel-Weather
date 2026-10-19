/* compat5: In-game page "Lenkrad & Verkehr" - unofficial add-on.
 *
 * Holds the menu description of the wheel-bridge and More-Traffic settings, forwards
 * changes to the live modules and persists them in the launcher's INI files:
 *   FH2_Lenkrad.ini       [Lenkrad]  Aktiv, ForceFeedback, FFBStaerke, ...
 *   FH2_ExtraOptions.ini  [Traffic]  TrafficLevel, RushHourAllDay
 * Saving happens on a background thread shortly after the last change, by editing only the
 * affected lines (comments and every other key stay untouched). When the launcher changes
 * one of the files while the game runs, the new values are picked up within a second. */
#include "weather.h"
#include "rig_settings.h"
#include "ini_edit.h"
#include "logging.h"
#include "support.h"
#include "video_options_text.h"
#include "wheel_buttons.h"

#define WHEEL_SECTION "Lenkrad"
#define TRAFFIC_SECTION "Traffic"
#define EO_INI_LIMIT 8192u
#define FILE_LIMIT 16384u
#define SAVE_DELAY_MS 600u

static const RigSettingInfo infos[RIG_SETTING_COUNT] = {
    [RIG_WHEEL_ENABLED] = {"EoRigWheelEnabled", "Aktiv", 0, 1, RIG_KIND_TOGGLE, 0, 1, NULL},
    [RIG_WHEEL_FFB] = {"EoRigForceFeedback", "ForceFeedback", 0, 1, RIG_KIND_TOGGLE, 0, 1, NULL},
    [RIG_WHEEL_STRENGTH] = {"EoRigStrength", "FFBStaerke", 0, 200, RIG_KIND_PERCENT, 0, 0.01f,
                            "EO_RigPercent200"},
    [RIG_WHEEL_RUMBLE] = {"EoRigRumble", "Vibration", 0, 200, RIG_KIND_PERCENT, 0, 0.01f,
                          "EO_RigPercent200"},
    [RIG_WHEEL_DAMPING] = {"EoRigDamping", "Daempfung", 0, 100, RIG_KIND_PERCENT, 0, 0.01f,
                           "A_Style_Slider_Options"},
    [RIG_WHEEL_FRICTION] = {"EoRigFriction", "Reibung", 0, 100, RIG_KIND_PERCENT, 0, 0.01f,
                            "A_Style_Slider_Options"},
    [RIG_WHEEL_SMOOTHING] = {"EoRigSmoothing", "Glaettung", 0, 200, RIG_KIND_NUMBER, 0, 1,
                             "EO_RigMilliseconds"},
    [RIG_WHEEL_MINFORCE] = {"EoRigMinimumForce", "Mindestkraft", 0, 50, RIG_KIND_PERCENT, 0,
                            0.01f, "EO_RigPercent50"},
    [RIG_WHEEL_OUTWARD] = {"EoRigOutward", "KraftNachAussen", 0, 100, RIG_KIND_PERCENT, 0, 0.01f,
                           "EO_RigPercent100"},
    [RIG_WHEEL_CENTERING] = {"EoRigCentering", "Zentrierung", 0, 100, RIG_KIND_PERCENT, 0, 0.01f,
                             "EO_RigPercent100"},
    [RIG_WHEEL_LOCK] = {"EoRigLock", "Anschlag", 30, 450, RIG_KIND_NUMBER, 0, 1, "EO_RigLock"},
    [RIG_WHEEL_CURVE] = {"EoRigCurve", "Kurve", 10, 60, RIG_KIND_NUMBER, 1, 0.1f, "EO_RigCurve"},
    [RIG_WHEEL_ROTATION] = {"EoRigRotation", "Drehwinkel", 180, 2520, RIG_KIND_NUMBER, 0, 1,
                            "EO_RigRotation"},
    [RIG_WHEEL_SHIFTER] = {"EoRigShifter", "Schaltknauf", 0, 1, RIG_KIND_TOGGLE, 0, 1, NULL},
    [RIG_WHEEL_BUTTON1] = {"EoRigButton1", "ZusatzFunktion1", 0, WHEEL_FUNCTION_COUNT - 1,
                           RIG_KIND_FUNCTION, 0, 1, NULL},
    [RIG_WHEEL_BUTTON2] = {"EoRigButton2", "ZusatzFunktion2", 0, WHEEL_FUNCTION_COUNT - 1,
                           RIG_KIND_FUNCTION, 0, 1, NULL},
    [RIG_WHEEL_BUTTON3] = {"EoRigButton3", "ZusatzFunktion3", 0, WHEEL_FUNCTION_COUNT - 1,
                           RIG_KIND_FUNCTION, 0, 1, NULL},
    [RIG_TRAFFIC_LEVEL] = {"EoRigTrafficLevel", "TrafficLevel", 0, 5, RIG_KIND_TRAFFIC, 0, 1,
                           NULL},
    [RIG_TRAFFIC_ALL_DAY] = {"EoRigRushHour", "RushHourAllDay", 0, 1, RIG_KIND_TOGGLE, 0, 1,
                             NULL},
    [RIG_WHEEL_PROFILE] = {"EoRigProfile", "", 0, RIG_PROFILE_COUNT - 1, RIG_KIND_PROFILE, 0, 1,
                           NULL},
    [RIG_TRAFFIC_PRESET] = {"EoRigDensity", "", 0, RIG_DENSITY_COUNT - 1, RIG_KIND_DENSITY, 0, 1,
                            NULL},
    [RIG_WEATHER] = {"EoRigWeather", "Wetter", 0, RIG_WEATHER_COUNT - 1, RIG_KIND_WEATHER, 0, 1,
                     NULL},
};

static const unsigned char order[RIG_SETTING_COUNT] = {
    RIG_WHEEL_ENABLED,   RIG_WHEEL_FFB,       RIG_WHEEL_PROFILE,  RIG_WHEEL_STRENGTH,
    RIG_WHEEL_RUMBLE,    RIG_WHEEL_DAMPING,   RIG_WHEEL_FRICTION, RIG_WHEEL_SMOOTHING,
    RIG_WHEEL_MINFORCE,  RIG_WHEEL_OUTWARD,   RIG_WHEEL_CENTERING, RIG_WHEEL_LOCK,
    RIG_WHEEL_CURVE,     RIG_WHEEL_ROTATION,  RIG_WHEEL_SHIFTER,  RIG_WHEEL_BUTTON1,
    RIG_WHEEL_BUTTON2,   RIG_WHEEL_BUTTON3,   RIG_TRAFFIC_PRESET, RIG_TRAFFIC_LEVEL,
    RIG_TRAFFIC_ALL_DAY, RIG_WEATHER,
};

unsigned rig_setting_order(unsigned position) {
    return position < RIG_SETTING_COUNT ? order[position] : 0;
}

/* ------------------------------------------------------------------ FFB profiles */

/* The profile is not stored anywhere: it is whichever preset the current values match
   ("Eigene Werte" otherwise). Choosing a preset simply sets these values. */
static const unsigned char profile_ids[] = {RIG_WHEEL_STRENGTH, RIG_WHEEL_RUMBLE,
                                            RIG_WHEEL_DAMPING,  RIG_WHEEL_FRICTION,
                                            RIG_WHEEL_SMOOTHING, RIG_WHEEL_MINFORCE,
                                            RIG_WHEEL_OUTWARD,  RIG_WHEEL_CENTERING};
#define PROFILE_VALUES ARRAY_COUNT(profile_ids)
static const unsigned char presets[RIG_PROFILE_COUNT][PROFILE_VALUES] = {
    {0},                                /* 0 = own values (not a preset) */
    {75, 50, 6, 4, 35, 2, 30, 20},      /* 1 = Mein Setup (eigene Werte vom 18.10.2026) */
    {50, 30, 10, 6, 60, 1, 20, 20},     /* 2 = weich / Komfort */
    {90, 40, 4, 3, 20, 3, 40, 20},      /* 3 = direkt / Rennen */
    {80, 100, 5, 3, 25, 2, 35, 20},     /* 4 = Offroad */
    {60, 40, 3, 2, 25, 2, 70, 20},      /* 5 = Drift */
};

/* Traffic presets: whichever one matches TrafficLevel + RushHourAllDay is shown. */
static const unsigned char density_presets[RIG_DENSITY_COUNT][2] = {
    {0, 0}, /* 0 = own values (not a preset) */
    {0, 0}, /* 1 = Original */
    {1, 0}, /* 2 = Ruhig */
    {3, 0}, /* 3 = Lebhaft */
    {4, 1}, /* 4 = Rushhour */
    {5, 1}, /* 5 = Chaos */
};

static int density_current(void) {
    for (unsigned p = 1; p < RIG_DENSITY_COUNT; ++p) {
        if (traffic_setting(RIG_TRAFFIC_LEVEL) == density_presets[p][0] &&
            traffic_setting(RIG_TRAFFIC_ALL_DAY) == density_presets[p][1]) {
            return (int)p;
        }
    }
    return 0;
}

static int profile_current(void) {
    for (unsigned p = 1; p < RIG_PROFILE_COUNT; ++p) {
        unsigned i = 0;
        while (i < PROFILE_VALUES && wheel_bridge_setting(profile_ids[i]) == presets[p][i]) {
            ++i;
        }
        if (i == PROFILE_VALUES) {
            return (int)p;
        }
    }
    return 0;
}

const RigSettingInfo *rig_setting_info(unsigned id) {
    return id < RIG_SETTING_COUNT ? &infos[id] : NULL;
}

/* ------------------------------------------------------------------ texts */

typedef struct {
    const char *heading, *description;
} RigText;

static const RigText german[RIG_SETTING_COUNT] = {
    [RIG_WHEEL_ENABLED] = {"Lenkrad: Lenkrad im Spiel",
                           "Reicht dein Lenkrad (G920 & Co.) ans Spiel durch. Wirkt erst nach einem "
                           "Neustart des Spiels."},
    [RIG_WHEEL_FFB] = {"Lenkrad: Force Feedback",
                       "Kräfte aus dem Spiel am Lenkrad: Rückstellkraft, Lenkgewicht und "
                       "Vibration. Aus = gar keine Kraft am Lenkrad. Wirkt sofort."},
    [RIG_WHEEL_STRENGTH] = {"Lenkrad: FFB-Stärke",
                            "Stärke der Kräfte aus dem Spiel. Wirkt sofort."},
    [RIG_WHEEL_RUMBLE] = {"Lenkrad: Vibration",
                          "Stärke der Vibrationen, z. B. auf Rüttelstreifen und im Gelände. "
                          "Wirkt sofort."},
    [RIG_WHEEL_DAMPING] = {"Lenkrad: Dämpfung",
                           "Grunddämpfung gegen schnelles Drehen des Lenkrads. Wirkt sofort."},
    [RIG_WHEEL_FRICTION] = {"Lenkrad: Reibung",
                            "Leichte Reibung wie bei einer echten Lenkung. Wirkt sofort."},
    [RIG_WHEEL_SMOOTHING] = {"Lenkrad: Glättung (ms)",
                             "Glättet die Kraftstufen des Spiels in Millisekunden. Schläge kommen "
                             "weiter sofort durch. 0 = aus. Wirkt sofort."},
    [RIG_WHEEL_MINFORCE] = {"Lenkrad: Mindestkraft",
                            "Hebt sehr kleine Kräfte an, damit das Getriebe des Lenkrads sie nicht "
                            "verschluckt. Wirkt sofort."},
    [RIG_WHEEL_OUTWARD] = {"Lenkrad: Kraft nach außen",
                           "Anteil der Spielkraft, der das Lenkrad von der Mitte weg zieht. Wirkt "
                           "sofort."},
    [RIG_WHEEL_CENTERING] = {"Lenkrad: Zentrierung (Menüs)",
                             "Zieht das Lenkrad zur Mitte, solange du nicht fährst (Menüs, "
                             "Ladebildschirme). Wirkt sofort."},
    [RIG_WHEEL_LOCK] = {"Lenkrad: Anschlag (Grad)",
                        "Grad je Seite, ab denen das Lenkrad weich blockiert. Wirkt sofort."},
    [RIG_WHEEL_CURVE] = {"Lenkrad: Lenkkurve",
                         "1,0 = linear. Höher = Mitte direkter, außen ruhiger. Wirkt sofort. Die "
                         "Cockpit-Animation stellt der Launcher ein."},
    [RIG_WHEEL_ROTATION] = {"Lenkrad: Drehwinkel (Grad)",
                            "Lenkwinkel, den das Spiel für dein Lenkrad annimmt. In G HUB 900 Grad "
                            "lassen. Wirkt sofort. Die Cockpit-Animation stellt der Launcher ein."},
    [RIG_WHEEL_SHIFTER] = {"Lenkrad: H-Schaltung",
                           "Schaltknauf (Driving Force Shifter) benutzen. Wirkt sofort."},
    [RIG_WHEEL_BUTTON1] = {"Lenkrad: Taste RSB",
                           "Spielfunktion für die rechte Stick-Taste am Lenkrad (G920: RSB, in "
                           "FH2_Lenkrad.ini ZusatzTaste1). Wirkt sofort."},
    [RIG_WHEEL_BUTTON2] = {"Lenkrad: Taste LSB",
                           "Spielfunktion für die linke Stick-Taste am Lenkrad (G920: LSB, in "
                           "FH2_Lenkrad.ini ZusatzTaste2). Wirkt sofort."},
    [RIG_WHEEL_BUTTON3] = {"Lenkrad: Xbox-Taste",
                           "Spielfunktion für die Xbox-Taste am Lenkrad (in FH2_Lenkrad.ini "
                           "ZusatzTaste3). Achtung: Windows kann damit die Xbox Game Bar öffnen. "
                           "Wirkt sofort."},
    [RIG_TRAFFIC_LEVEL] = {"Verkehr: Menge",
                           "Höchstzahl der Verkehrsautos. Wirkt sofort, neue Autos erscheinen nach "
                           "und nach. Die Verkehrsdateien stellt der Launcher ein."},
    [RIG_TRAFFIC_ALL_DAY] = {"Verkehr: Rushhour rund um die Uhr",
                             "Volle Verkehrsdichte zu jeder Uhrzeit statt nur von 7 bis 19 Uhr. "
                             "Wirkt sofort."},
    [RIG_WEATHER] = {"Wetter",
                     "Festes Wetter in der freien Fahrt: Sonnig, Bewölkt, Gewitterwolken, Regen "
                     "oder Nebel (Nebel nur auf der Sturm-Insel, sonst bewölkt). Original = das "
                     "Wetter wechselt wie im Spiel. Rennen und Treffen mit eigenem Wetter behalten "
                     "es, danach kommt deine Wahl zurück. Wirkt nach dem Schließen des Menüs."},
    [RIG_TRAFFIC_PRESET] = {"Verkehr: Voreinstellung",
                            "Stellt Menge und Rushhour mit einem Klick ein: Original, Ruhig (24), "
                            "Lebhaft (48), Rushhour (64, rund um die Uhr) oder Chaos (100, rund "
                            "um die Uhr). Änderst du danach Menge oder Rushhour, steht hier Eigene "
                            "Werte. Wirkt sofort."},
    [RIG_WHEEL_PROFILE] = {"Lenkrad: FFB-Profil",
                           "Lädt fertige Werte für Stärke, Vibration, Dämpfung, Reibung, Glättung, "
                           "Mindestkraft, Kraft nach außen und Zentrierung. Mein Setup = deine "
                           "Werte vom 18.10. Änderst du danach etwas, steht hier Eigene Werte. "
                           "Wirkt sofort."},
};

static const RigText english[RIG_SETTING_COUNT] = {
    [RIG_WHEEL_ENABLED] = {"Wheel: Use Wheel In Game",
                           "Passes your wheel (G920 and similar) to the game. Restart the game to "
                           "apply."},
    [RIG_WHEEL_FFB] = {"Wheel: Force Feedback",
                       "Game forces on the wheel: self-aligning torque, steering weight and "
                       "rumble. Off = no force on the wheel at all. Applies immediately."},
    [RIG_WHEEL_STRENGTH] = {"Wheel: Force Feedback Strength",
                            "Strength of the game forces. Applies immediately."},
    [RIG_WHEEL_RUMBLE] = {"Wheel: Rumble", "Strength of road and kerb rumble. Applies immediately."},
    [RIG_WHEEL_DAMPING] = {"Wheel: Damping",
                           "Base damping against fast wheel movement. Applies immediately."},
    [RIG_WHEEL_FRICTION] = {"Wheel: Friction",
                            "Light friction like a real steering rack. Applies immediately."},
    [RIG_WHEEL_SMOOTHING] = {"Wheel: Smoothing (ms)",
                             "Smooths the game's force steps in milliseconds. Impacts still pass "
                             "through. 0 = off. Applies immediately."},
    [RIG_WHEEL_MINFORCE] = {"Wheel: Minimum Force",
                            "Lifts very small forces so the wheel's gears do not swallow them. "
                            "Applies immediately."},
    [RIG_WHEEL_OUTWARD] = {"Wheel: Outward Force",
                           "Share of the game force that pulls the wheel away from the centre. "
                           "Applies immediately."},
    [RIG_WHEEL_CENTERING] = {"Wheel: Centring (Menus)",
                             "Pulls the wheel to the centre while you are not driving. Applies "
                             "immediately."},
    [RIG_WHEEL_LOCK] = {"Wheel: Lock (Degrees)",
                        "Degrees per side after which the wheel is softly blocked. Applies "
                        "immediately."},
    [RIG_WHEEL_CURVE] = {"Wheel: Steering Curve",
                         "1.0 = linear. Higher = more direct centre, calmer outside. Applies "
                         "immediately. The launcher adjusts the cockpit animation."},
    [RIG_WHEEL_ROTATION] = {"Wheel: Rotation (Degrees)",
                            "Rotation the game assumes for your wheel. Keep 900 degrees in G HUB. "
                            "Applies immediately. The launcher adjusts the cockpit animation."},
    [RIG_WHEEL_SHIFTER] = {"Wheel: H-Pattern Shifter",
                           "Use the Driving Force Shifter. Applies immediately."},
    [RIG_WHEEL_BUTTON1] = {"Wheel: RSB Button",
                           "Game function for the wheel's right stick button (G920: RSB, "
                           "ZusatzTaste1 in FH2_Lenkrad.ini). Applies immediately."},
    [RIG_WHEEL_BUTTON2] = {"Wheel: LSB Button",
                           "Game function for the wheel's left stick button (G920: LSB, "
                           "ZusatzTaste2 in FH2_Lenkrad.ini). Applies immediately."},
    [RIG_WHEEL_BUTTON3] = {"Wheel: Xbox Button",
                           "Game function for the wheel's Xbox button (ZusatzTaste3 in "
                           "FH2_Lenkrad.ini). Windows may open the Xbox Game Bar with it. "
                           "Applies immediately."},
    [RIG_TRAFFIC_LEVEL] = {"Traffic: Amount",
                           "Maximum number of traffic cars. Applies immediately; new cars appear "
                           "over time. The launcher installs the traffic files."},
    [RIG_TRAFFIC_ALL_DAY] = {"Traffic: Rush Hour All Day",
                             "Full traffic density at any time of day instead of 7:00-19:00 only. "
                             "Applies immediately."},
    [RIG_WEATHER] = {"Weather",
                     "Fixed weather in free roam: Sunny, Cloudy, Storm Clouds, Rain or Fog (fog "
                     "only on Storm Island, cloudy elsewhere). Original = the game's normal "
                     "weather changes. Races and meets with their own weather keep it; your "
                     "choice returns afterwards. Applies after closing the menu."},
    [RIG_TRAFFIC_PRESET] = {"Traffic: Preset",
                            "Sets amount and rush hour in one go: Original, Calm (24), Busy (48), "
                            "Rush Hour (64, all day) or Chaos (100, all day). Changing amount or "
                            "rush hour afterwards shows Custom. Applies immediately."},
    [RIG_WHEEL_PROFILE] = {"Wheel: Force Feedback Profile",
                           "Loads ready-made values for strength, rumble, damping, friction, "
                           "smoothing, minimum force, outward force and centring. Changing any of "
                           "them afterwards shows Custom. Applies immediately."},
};

static const wchar_t *const profile_german[RIG_PROFILE_COUNT] = {
    L"Eigene Werte", L"Mein Setup", L"Weich", L"Direkt (Rennen)", L"Offroad", L"Drift"};
static const wchar_t *const profile_english[RIG_PROFILE_COUNT] = {
    L"Custom", L"My Setup", L"Soft", L"Direct (Racing)", L"Off-Road", L"Drift"};

static const wchar_t *const density_german[RIG_DENSITY_COUNT] = {
    L"Eigene Werte", L"Original", L"Ruhig", L"Lebhaft", L"Rushhour", L"Chaos"};
static const wchar_t *const density_english[RIG_DENSITY_COUNT] = {
    L"Custom", L"Original", L"Calm", L"Busy", L"Rush Hour", L"Chaos"};

static const wchar_t *const weather_german[RIG_WEATHER_COUNT] = {
    L"Original", L"Sonnig", L"Bewölkt", L"Gewitterwolken", L"Regen", L"Nebel"};
static const wchar_t *const weather_english[RIG_WEATHER_COUNT] = {
    L"Original", L"Sunny", L"Cloudy", L"Storm Clouds", L"Rain", L"Fog"};

const wchar_t *rig_weather_choice(unsigned char *game_image, unsigned index) {
    if (index >= RIG_WEATHER_COUNT) {
        return L"";
    }
    return video_options_text_is_german(game_image) ? weather_german[index]
                                                     : weather_english[index];
}

const wchar_t *rig_density_choice(unsigned char *game_image, unsigned index) {
    if (index >= RIG_DENSITY_COUNT) {
        return L"";
    }
    return video_options_text_is_german(game_image) ? density_german[index]
                                                     : density_english[index];
}

const wchar_t *rig_profile_choice(unsigned char *game_image, unsigned index) {
    if (index >= RIG_PROFILE_COUNT) {
        return L"";
    }
    return video_options_text_is_german(game_image) ? profile_german[index]
                                                     : profile_english[index];
}

const wchar_t *rig_function_choice(unsigned char *game_image, unsigned index) {
    return wheel_function_name(game_image, index);
}

static const wchar_t *const traffic_german[6] = {L"Original (~14)", L"24 Autos", L"36 Autos",
                                                  L"48 Autos",       L"64 Autos", L"100 Autos"};
static const wchar_t *const traffic_english[6] = {L"Original (~14)", L"24 Cars", L"36 Cars",
                                                   L"48 Cars",        L"64 Cars", L"100 Cars"};

static const RigText *texts(unsigned char *game_image) {
    return video_options_text_is_german(game_image) ? german : english;
}

const char *rig_setting_heading(unsigned char *game_image, unsigned id) {
    return id < RIG_SETTING_COUNT ? texts(game_image)[id].heading : "";
}

const char *rig_setting_description(unsigned char *game_image, unsigned id) {
    return id < RIG_SETTING_COUNT ? texts(game_image)[id].description : "";
}

const wchar_t *rig_traffic_choice(unsigned char *game_image, unsigned index) {
    if (index >= 6) {
        return L"";
    }
    return video_options_text_is_german(game_image) ? traffic_german[index]
                                                     : traffic_english[index];
}

/* ------------------------------------------------------------------ values */

static wchar_t traffic_ini[PATH_CAPACITY];
static volatile LONG dirty_wheel, dirty_traffic;
static volatile ULONGLONG save_after;
static SRWLOCK file_lock = SRWLOCK_INIT;
static int started;

static int stored_value(unsigned id) {
    if (id < RIG_WHEEL_COUNT) {
        return wheel_bridge_setting(id);
    }
    return id == RIG_WEATHER ? weather_setting() : traffic_setting(id);
}

static int is_wheel(unsigned id) {
    return id < RIG_WHEEL_COUNT;
}

int rig_setting_get(unsigned id) {
    if (id >= RIG_SETTING_COUNT) {
        return 0;
    }
    if (id == RIG_WHEEL_PROFILE) {
        return profile_current();
    }
    if (id == RIG_TRAFFIC_PRESET) {
        return density_current();
    }
    int value = stored_value(id);
    /* the INI may hold values outside the menu range; show them clamped */
    if (value < infos[id].minimum) {
        value = infos[id].minimum;
    }
    if (value > infos[id].maximum) {
        value = infos[id].maximum;
    }
    return value;
}

static void forward(unsigned id, int value) {
    if (is_wheel(id)) {
        wheel_bridge_set_setting(id, value);
    } else {
        if (id == RIG_WEATHER) {
            weather_set_setting(value);
        } else {
            traffic_set_setting(id, value);
        }
    }
}

int rig_setting_set(unsigned id, int value) {
    if (id >= RIG_SETTING_COUNT || value < infos[id].minimum || value > infos[id].maximum) {
        return 0;
    }
    if (id == RIG_WHEEL_PROFILE) {
        /* "Eigene Werte" is only a label: picking it keeps the values as they are */
        if (value == 0 || value == profile_current()) {
            return 0;
        }
        int changed = 0;
        for (unsigned i = 0; i < PROFILE_VALUES; ++i) {
            changed |= rig_setting_set(profile_ids[i], presets[value][i]);
        }
        return changed;
    }
    if (id == RIG_TRAFFIC_PRESET) {
        if (value == 0 || value == density_current()) {
            return 0;
        }
        int changed = rig_setting_set(RIG_TRAFFIC_LEVEL, density_presets[value][0]);
        changed |= rig_setting_set(RIG_TRAFFIC_ALL_DAY, density_presets[value][1]);
        return changed;
    }
    int current = stored_value(id);
    if (current == value) {
        return 0;
    }
    forward(id, value);
    save_after = GetTickCount64() + SAVE_DELAY_MS;
    InterlockedOr(is_wheel(id) ? &dirty_wheel : &dirty_traffic, (LONG)(1u << id));
    return 1;
}

/* ------------------------------------------------------------------ files */

static char file_buffer[FILE_LIMIT + 1], edit_buffer[2][FILE_LIMIT + 1];
static wchar_t temp_path[PATH_CAPACITY];

static int read_file(const wchar_t *path, char *buffer, size_t capacity, size_t *length,
                     int *missing) {
    *length = 0;
    *missing = 0;
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
                              OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        *missing = GetLastError() == ERROR_FILE_NOT_FOUND;
        return *missing;
    }
    LARGE_INTEGER size;
    DWORD got = 0;
    int ok = GetFileSizeEx(file, &size) && size.QuadPart >= 0 &&
             (ULONGLONG)size.QuadPart < capacity &&
             ReadFile(file, buffer, (DWORD)size.QuadPart, &got, NULL) && got == size.QuadPart;
    CloseHandle(file);
    if (ok) {
        *length = got;
        buffer[got] = 0;
    }
    return ok;
}

static int modified_time(const wchar_t *path, ULONGLONG *time) {
    WIN32_FILE_ATTRIBUTE_DATA data;
    if (!path || !path[0] || !GetFileAttributesExW(path, GetFileExInfoStandard, &data)) {
        *time = 0;
        return 0;
    }
    *time = ((ULONGLONG)data.ftLastWriteTime.dwHighDateTime << 32) |
            data.ftLastWriteTime.dwLowDateTime;
    return 1;
}

static int write_file(const wchar_t *path, const char *data, size_t length) {
    size_t n = 0;
    while (path[n] && n < PATH_CAPACITY - 8) {
        temp_path[n] = path[n];
        ++n;
    }
    static const wchar_t suffix[] = L".eotmp";
    for (unsigned i = 0; i < ARRAY_COUNT(suffix); ++i) {
        temp_path[n + i] = suffix[i];
    }
    HANDLE file = CreateFileW(temp_path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    DWORD written = 0;
    int ok = WriteFile(file, data, (DWORD)length, &written, NULL) && written == length &&
             FlushFileBuffers(file);
    CloseHandle(file);
    if (ok) {
        ok = MoveFileExW(temp_path, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
    }
    if (!ok) {
        DeleteFileW(temp_path);
    }
    return ok;
}

typedef struct {
    const wchar_t *path;
    const char *section;
    unsigned first, end; /* setting ids stored in this file */
    size_t limit;
    int create_missing;
    ULONGLONG known_time;
    const char *name;
    int error_logged;
} RigFile;

static RigFile files[2] = {
    {NULL, WHEEL_SECTION, 0, RIG_WHEEL_COUNT, FILE_LIMIT, 1, 0, "FH2_Lenkrad.ini", 0},
    /* never create the Extra Options INI: its absence means "all defaults" */
    {traffic_ini, TRAFFIC_SECTION, RIG_TRAFFIC_LEVEL, RIG_WEATHER + 1, EO_INI_LIMIT, 0, 0,
     "FH2_ExtraOptions.ini", 0},
};

static void log_line(const char *first, const char *second);

/* A failed save is retried a few seconds later; it is only logged once. */
static int save_failed(RigFile *f, const char *message) {
    if (!f->error_logged) {
        f->error_logged = 1;
        log_line(message, f->name);
    }
    return 0;
}

static void log_line(const char *first, const char *second) {
    char line[160];
    size_t n = 0;
    for (const char *p = first; *p && n < sizeof(line) - 4; ++p) line[n++] = *p;
    for (const char *p = second; *p && n < sizeof(line) - 4; ++p) line[n++] = *p;
    line[n++] = '\r';
    line[n++] = '\n';
    line[n] = 0;
    log_append(line);
}

/* Writes the current values of the dirty settings into the file. */
static int save_file(RigFile *f, LONG dirty) {
    if (!f->path || !f->path[0] || !dirty) {
        return 1;
    }
    size_t length;
    int missing;
    if (!read_file(f->path, file_buffer, f->limit + 1, &length, &missing)) {
        return save_failed(f, "MENU: could not read (retrying) ");
    }
    if (missing && !f->create_missing) {
        return 1;
    }
    const char *source = file_buffer;
    size_t source_length = length;
    unsigned slot = 0;
    for (unsigned id = f->first; id < f->end; ++id) {
        if (!(dirty & (LONG)(1u << id))) {
            continue;
        }
        char number[12];
        int value = stored_value(id);
        size_t written = ini_set_value(source, source_length, f->section, infos[id].key,
                                       ini_format_int(value, number), edit_buffer[slot],
                                       f->limit + 1);
        if (!written || written > f->limit) {
            log_line("MENU: not saved, the file would become too large: ", f->name);
            return 1; /* permanent: do not retry */
        }
        source = edit_buffer[slot];
        source_length = written;
        slot ^= 1;
    }
    if (source == file_buffer) {
        return 1;
    }
    if (!write_file(f->path, source, source_length)) {
        return save_failed(f, "MENU: could not save (retrying) ");
    }
    modified_time(f->path, &f->known_time);
    if (f->error_logged) {
        f->error_logged = 0;
        log_line("MENU: saved again: ", f->name);
    }
    return 1;
}

/* The launcher (or an editor) changed the file: take over its values, except for settings
   that were just changed in the menu and still wait to be saved. */
static void reload_file(RigFile *f, LONG pending) {
    size_t length;
    int missing;
    if (!f->path || !read_file(f->path, file_buffer, FILE_LIMIT + 1, &length, &missing) ||
        missing) {
        return;
    }
    int changed = 0;
    for (unsigned id = f->first; id < f->end; ++id) {
        int value;
        if ((pending & (LONG)(1u << id)) ||
            !ini_find_int(file_buffer, length, f->section, infos[id].key, &value) ||
            value < infos[id].minimum || value > infos[id].maximum) {
            continue;
        }
        int current = stored_value(id);
        if (current != value) {
            forward(id, value);
            changed = 1;
        }
    }
    if (changed) {
        log_line("MENU: values reloaded from ", f->name);
    }
}

static ULONGLONG last_check;

static void saver_step(ULONGLONG now) {
    AcquireSRWLockExclusive(&file_lock);
    if ((dirty_wheel || dirty_traffic) && now >= save_after) {
        LONG wheel = InterlockedExchange(&dirty_wheel, 0);
        LONG traffic = InterlockedExchange(&dirty_traffic, 0);
        if (!save_file(&files[0], wheel)) {
            InterlockedOr(&dirty_wheel, wheel);
            save_after = now + 5000; /* retry later, e.g. while the file is locked */
        }
        if (!save_file(&files[1], traffic)) {
            InterlockedOr(&dirty_traffic, traffic);
            save_after = now + 5000;
        }
    }
    if (now - last_check >= 1000) {
        last_check = now;
        for (unsigned i = 0; i < ARRAY_COUNT(files); ++i) {
            ULONGLONG time;
            LONG pending = i == 0 ? dirty_wheel : dirty_traffic;
            if (modified_time(files[i].path, &time) && time != files[i].known_time) {
                files[i].known_time = time;
                reload_file(&files[i], pending);
            }
        }
    }
    ReleaseSRWLockExclusive(&file_lock);
}

static DWORD WINAPI saver_thread(LPVOID unused) {
    (void)unused;
    for (;;) {
        Sleep(100);
        saver_step(GetTickCount64());
    }
    return 0;
}

/* Process exit: save changes from the last moments (the saver thread is gone already). */
void rig_settings_flush(void) {
    if (!started) {
        return;
    }
    LONG wheel = InterlockedExchange(&dirty_wheel, 0);
    LONG traffic = InterlockedExchange(&dirty_traffic, 0);
    save_file(&files[0], wheel);
    save_file(&files[1], traffic);
}

void rig_settings_start(const wchar_t *settings_directory) {
    if (started || !settings_directory ||
        !path_join(traffic_ini, settings_directory, MOD_INI_NAME)) {
        return;
    }
    files[0].path = wheel_bridge_ini_path();
    for (unsigned i = 0; i < ARRAY_COUNT(files); ++i) {
        modified_time(files[i].path, &files[i].known_time);
    }
    HANDLE thread = CreateThread(NULL, 0, saver_thread, NULL, 0, NULL);
    if (!thread) {
        log_append("MENU: Lenkrad & Verkehr - could not start the save thread; menu changes stay "
                   "until the game closes.\r\n");
        return;
    }
    CloseHandle(thread);
    started = 1;
    log_append("MENU: Lenkrad & Verkehr page ready (HUD options); changes apply live and are "
               "saved to FH2_Lenkrad.ini / FH2_ExtraOptions.ini.\r\n");
}

#ifdef FH2_TWEAKS_TEST
#include "features.h"
#include "settings.h"
__declspec(dllexport) int Fh2TestRigStart(unsigned char *image, const wchar_t *executable,
                                          const wchar_t *directory) {
    ModOptions options;
    int ok = settings_read(directory, &options);
    log_set_directory(directory);
    traffic_tunables_start(image, &options);
    weather_start(image, &options);
    wheel_bridge_start(image, executable, directory);
    rig_settings_start(directory);
    return ok ? (started ? 1 : 2) : 0;
}
__declspec(dllexport) void Fh2TestRigStep(ULONGLONG now) {
    saver_step(now);
}
__declspec(dllexport) void Fh2TestRigFlush(void) {
    rig_settings_flush();
}
__declspec(dllexport) int Fh2TestRigGet(unsigned id) {
    return rig_setting_get(id);
}
__declspec(dllexport) int Fh2TestRigSet(unsigned id, int value) {
    return rig_setting_set(id, value);
}
#endif
