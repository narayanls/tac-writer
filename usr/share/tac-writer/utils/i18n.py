#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# i18n utilities for TAC Writer
#
import gettext
import os

_DOMAIN = "tac-writer"

_script_dir = os.path.dirname(os.path.abspath(__file__))  # .../tac-writer/utils
_app_dir = os.path.dirname(_script_dir)                  # .../tac-writer
_share_dir = os.path.dirname(_app_dir)                   # .../share
_bundled_locale = os.path.join(_share_dir, "locale")     # .../share/locale


def _has_translations(locale_root: str) -> bool:
    """True if this locale root ships at least one compiled catalog for us."""
    if not os.path.isdir(locale_root):
        return False
    try:
        for lang in os.listdir(locale_root):
            mo = os.path.join(locale_root, lang, "LC_MESSAGES", f"{_DOMAIN}.mo")
            if os.path.isfile(mo):
                return True
    except OSError:
        return False
    return False


# Prefer catalogs shipped next to the app (source / Flatpak / AppImage),
# then fall back to the system prefix. Checking for *.mo avoids always
# picking /usr/share/locale just because that directory exists on Linux.
_candidates = [
    _bundled_locale,
    "/app/share/locale",
    "/usr/share/locale",
]

locale_dir = "/usr/share/locale"
for candidate in _candidates:
    if _has_translations(candidate):
        locale_dir = candidate
        break

gettext.bindtextdomain(_DOMAIN, locale_dir)
gettext.textdomain(_DOMAIN)

_ = gettext.gettext
