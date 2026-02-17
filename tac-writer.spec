# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

MINGW = os.path.join(os.environ.get('MSYSTEM_PREFIX', '/mingw64'))

# Coletar DLLs GTK4 necessárias
gtk_bins = os.path.join(MINGW, 'bin')
gtk_dlls = []
for f in os.listdir(gtk_bins):
    if f.endswith('.dll'):
        gtk_dlls.append((os.path.join(gtk_bins, f), '.'))

# GObject Introspection typelibs
typelib_dir = os.path.join(MINGW, 'lib', 'girepository-1.0')
typelibs = [(os.path.join(typelib_dir, f), 'lib/girepository-1.0') 
            for f in os.listdir(typelib_dir) if f.endswith('.typelib')]

# GLib schemas
schemas_dir = os.path.join(MINGW, 'share', 'glib-2.0', 'schemas')
schemas = [(os.path.join(schemas_dir, 'gschemas.compiled'), 'share/glib-2.0/schemas')]

# Ícones Adwaita (essenciais para GTK4)
icon_dir = os.path.join(MINGW, 'share', 'icons', 'Adwaita')
icons = []
if os.path.exists(icon_dir):
    for root, dirs, files in os.walk(icon_dir):
        for f in files:
            src = os.path.join(root, f)
            dst = os.path.relpath(root, MINGW)
            icons.append((src, dst))

# Hicolor icons
hicolor_dir = os.path.join(MINGW, 'share', 'icons', 'hicolor')
if os.path.exists(hicolor_dir):
    for root, dirs, files in os.walk(hicolor_dir):
        for f in files:
            src = os.path.join(root, f)
            dst = os.path.relpath(root, MINGW)
            icons.append((src, dst))

# GDK Pixbuf loaders
pixbuf_dir = os.path.join(MINGW, 'lib', 'gdk-pixbuf-2.0')
pixbufs = []
if os.path.exists(pixbuf_dir):
    for root, dirs, files in os.walk(pixbuf_dir):
        for f in files:
            src = os.path.join(root, f)
            dst = os.path.relpath(root, MINGW)
            pixbufs.append((src, dst))

# Enchant (spell check)
enchant_data = []
enchant_lib_dir = os.path.join(MINGW, 'lib', 'enchant-2')
if os.path.exists(enchant_lib_dir):
    for f in os.listdir(enchant_lib_dir):
        enchant_data.append((os.path.join(enchant_lib_dir, f), 'lib/enchant-2'))

enchant_dict_dir = os.path.join(MINGW, 'share', 'enchant')
if os.path.exists(enchant_dict_dir):
    for root, dirs, files in os.walk(enchant_dict_dir):
        for f in files:
            src = os.path.join(root, f)
            dst = os.path.relpath(root, MINGW)
            enchant_data.append((src, dst))

# Hunspell dictionaries
hunspell_dir = os.path.join(MINGW, 'share', 'hunspell')
hunspell = []
if os.path.exists(hunspell_dir):
    for f in os.listdir(hunspell_dir):
        hunspell.append((os.path.join(hunspell_dir, f), 'share/hunspell'))

# Myspell dictionaries
myspell_dir = os.path.join(MINGW, 'share', 'myspell')
if os.path.exists(myspell_dir):
    for root, dirs, files in os.walk(myspell_dir):
        for f in files:
            src = os.path.join(root, f)
            dst = os.path.relpath(root, MINGW)
            hunspell.append((src, dst))

# Arquivos do próprio app
app_data = []

# Locales do app
locale_dir = 'locales'
if os.path.exists(locale_dir):
    for root, dirs, files in os.walk(locale_dir):
        for f in files:
            src = os.path.join(root, f)
            app_data.append((src, root))

# Outros recursos (CSS, ícones do app, etc.)
for resource_dir in ['resources', 'assets', 'data']:
    if os.path.exists(resource_dir):
        for root, dirs, files in os.walk(resource_dir):
            for f in files:
                src = os.path.join(root, f)
                app_data.append((src, root))

# Juntar todos os data files
all_datas = (gtk_dlls + typelibs + schemas + icons + pixbufs + 
             enchant_data + hunspell + app_data)

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=all_datas + [('icons/hicolor', 'share/icons/hicolor')],
    hiddenimports=[
        'gi',
        'gi.overrides',
        'gi.overrides.Gtk',
        'gi.overrides.Gdk',
        'gi.overrides.GLib',
        'gi.overrides.GObject',
        'gi.overrides.Gio',
        'gi.overrides.Pango',
        'gi.overrides.GdkPixbuf',
        'gi.repository.Gtk',
        'gi.repository.Gdk',
        'gi.repository.GLib',
        'gi.repository.GObject',
        'gi.repository.Gio',
        'gi.repository.Pango',
        'gi.repository.GdkPixbuf',
        'gi.repository.Adw',
        'enchant',
        'json',
        'sqlite3',
        'pathlib',
        'platform',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TacWriter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='icons/hicolor/scalable/actions/tac-writer.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TacWriter',
)