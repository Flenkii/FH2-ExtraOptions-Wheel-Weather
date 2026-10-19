#ifndef FH2_RIG_SETTINGS_H
#define FH2_RIG_SETTINGS_H
#include "extra_options.h"

/* In-game page "Lenkrad & Verkehr": wheel bridge and More Traffic settings.
   Values are kept in the units of the INI files (FH2_Lenkrad.ini / FH2_ExtraOptions.ini),
   so the launcher keeps reading and writing the very same keys. */
enum {
    RIG_WHEEL_ENABLED,   /* Aktiv            0/1, next game start */
    RIG_WHEEL_FFB,       /* ForceFeedback    0/1 */
    RIG_WHEEL_STRENGTH,  /* FFBStaerke       % */
    RIG_WHEEL_RUMBLE,    /* Vibration        % */
    RIG_WHEEL_DAMPING,   /* Daempfung        % */
    RIG_WHEEL_FRICTION,  /* Reibung          % */
    RIG_WHEEL_SMOOTHING, /* Glaettung        ms */
    RIG_WHEEL_MINFORCE,  /* Mindestkraft     % */
    RIG_WHEEL_OUTWARD,   /* KraftNachAussen  % */
    RIG_WHEEL_CENTERING, /* Zentrierung      % */
    RIG_WHEEL_LOCK,      /* Anschlag         degrees per side */
    RIG_WHEEL_CURVE,     /* Kurve            x10 */
    RIG_WHEEL_ROTATION,  /* Drehwinkel       degrees */
    RIG_WHEEL_SHIFTER,   /* Schaltknauf      0/1 */
    RIG_WHEEL_BUTTON1,   /* ZusatzFunktion1  WHEEL_FUNCTION_* of extra button 1 (RSB) */
    RIG_WHEEL_BUTTON2,   /* ZusatzFunktion2  extra button 2 (LSB) */
    RIG_WHEEL_BUTTON3,   /* ZusatzFunktion3  extra button 3 (Xbox button) */
    RIG_WHEEL_COUNT,
    RIG_TRAFFIC_LEVEL = RIG_WHEEL_COUNT, /* [Traffic] TrafficLevel   0..5 */
    RIG_TRAFFIC_ALL_DAY,                 /* [Traffic] RushHourAllDay 0/1 */
    RIG_WEATHER,                         /* [Traffic] Wetter         0..5 (weather.h) */
    RIG_WHEEL_PROFILE,                   /* FFB profile: not stored, derived from the FFB values */
    RIG_TRAFFIC_PRESET,                  /* traffic preset: not stored, derived from level + rush hour */
    RIG_SETTING_COUNT
};

/* How a setting is shown in the menu. */
enum {
    RIG_KIND_TOGGLE,  /* SpinnerControl, ToggleChoices (0 = off, 1 = on) */
    RIG_KIND_TRAFFIC, /* SpinnerControl, TrafficChoices */
    RIG_KIND_PERCENT, /* Slider, value / 100 with the game's percent display */
    RIG_KIND_NUMBER,  /* Slider, value * scale with a plain number display */
    RIG_KIND_PROFILE, /* SpinnerControl, ProfileChoices */
    RIG_KIND_FUNCTION, /* SpinnerControl, FunctionChoices (free wheel buttons) */
    RIG_KIND_DENSITY,  /* SpinnerControl, DensityChoices (traffic presets) */
    RIG_KIND_WEATHER,  /* SpinnerControl, WeatherChoices */
};

#define RIG_PROFILE_COUNT 6
#define RIG_DENSITY_COUNT 6
#define RIG_WEATHER_COUNT 6

typedef struct {
    const char *property; /* binding name on the options page */
    const char *key;      /* INI key */
    int minimum, maximum; /* INI units */
    unsigned char kind, digits;
    float scale;        /* menu value = INI value * scale */
    const char *style;  /* slider style key (sliders only) */
} RigSettingInfo;

const RigSettingInfo *rig_setting_info(unsigned id);
int rig_setting_get(unsigned id);
/* Returns 1 when the value changed. Out-of-range values are refused. */
int rig_setting_set(unsigned id, int value);
void rig_settings_start(const wchar_t *settings_directory);
void rig_settings_flush(void);

/* Texts of the page (German or English, following the game language). */
const char *rig_setting_heading(unsigned char *game_image, unsigned id);
const char *rig_setting_description(unsigned char *game_image, unsigned id);
const wchar_t *rig_traffic_choice(unsigned char *game_image, unsigned index);
const wchar_t *rig_profile_choice(unsigned char *game_image, unsigned index);
const wchar_t *rig_density_choice(unsigned char *game_image, unsigned index);
const wchar_t *rig_weather_choice(unsigned char *game_image, unsigned index);
const wchar_t *rig_function_choice(unsigned char *game_image, unsigned index);
/* Menu order of the settings (the profile sits right below Force Feedback). */
unsigned rig_setting_order(unsigned position);

/* Provided by the wheel bridge and the traffic watcher. */
int wheel_bridge_setting(unsigned id);
void wheel_bridge_set_setting(unsigned id, int value);
const wchar_t *wheel_bridge_ini_path(void);
int traffic_setting(unsigned id);
void traffic_set_setting(unsigned id, int value);
#endif
