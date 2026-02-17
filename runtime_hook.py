import os
import sys

if getattr(sys, 'frozen', False):
    # Para onedir, _MEIPASS aponta para _internal
    base = sys._MEIPASS
    
    # Tenta encontrar o diretório share
    share_dir = os.path.join(base, 'share')
    if not os.path.exists(share_dir):
        # Pode estar um nível acima
        parent = os.path.dirname(base)
        share_dir = os.path.join(parent, 'share')
    
    os.environ['XDG_DATA_DIRS'] = share_dir
    os.environ['GTK_DATA_PREFIX'] = os.path.dirname(share_dir)
    
    # GDK Pixbuf
    pixbuf_cache = os.path.join(base, 'lib', 'gdk-pixbuf-2.0', '2.10.0', 'loaders.cache')
    if not os.path.exists(pixbuf_cache):
        pixbuf_cache = os.path.join(os.path.dirname(base), 'lib', 'gdk-pixbuf-2.0', '2.10.0', 'loaders.cache')
    if os.path.exists(pixbuf_cache):
        os.environ['GDK_PIXBUF_MODULE_FILE'] = pixbuf_cache
    
    # GI typelibs
    typelib_dir = os.path.join(base, 'lib', 'girepository-1.0')
    if not os.path.exists(typelib_dir):
        typelib_dir = os.path.join(os.path.dirname(base), 'lib', 'girepository-1.0')
    if os.path.exists(typelib_dir):
        os.environ['GI_TYPELIB_PATH'] = typelib_dir
    
    # Schemas
    schemas_dir = os.path.join(share_dir, 'glib-2.0', 'schemas')
    if os.path.exists(schemas_dir):
        os.environ['GSETTINGS_SCHEMA_DIR'] = schemas_dir
    
    # Debug - remover depois
    print(f"[runtime_hook] base: {base}")
    print(f"[runtime_hook] share_dir exists: {os.path.exists(share_dir)} -> {share_dir}")
    print(f"[runtime_hook] typelib_dir exists: {os.path.exists(typelib_dir)} -> {typelib_dir}")