#ifndef FH2_VIDEO_OPTIONS_XAML_H
#define FH2_VIDEO_OPTIONS_XAML_H
#include "extra_options.h"

unsigned video_options_page(const char *text, size_t length);
int video_options_is_xaml(const char *text, size_t length);
size_t video_options_extend_xaml(unsigned char *game_image, const char *text, size_t length,
                                 char *output, size_t capacity);

/* Gripline's page on the pause-menu tile (FH2 Mod Platform): XAML resources and content.
   Returns 0 when a buffer is too small. */
#define GRIPLINE_PAGE_MARKER "<!-- GRIPLINE_SETTINGS_PAGE -->"
int video_options_gripline_page(unsigned char *image, char *resources, size_t resources_capacity,
                                char *content, size_t content_capacity);
#endif
