#!/usr/bin/env python3
"""
TAC - Continuous Argumentation Technique
Main entry point for the application
GTK4 + libadwaita academic text writing assistant
"""

import sys
import os
import traceback
import warnings
from pathlib import Path

# Suppress various system warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Suppress GTK and enchant warnings via environment variables
os.environ.setdefault('G_MESSAGES_DEBUG', '')
os.environ.setdefault('MESA_GLTHREAD', 'false')

# Suppress libenchant broker warnings
import logging
enchant_logger = logging.getLogger('enchant.broker')
enchant_logger.setLevel(logging.ERROR)

# Setup path for imports
app_dir = Path(__file__).parent.resolve()
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

# Import modules
from utils.i18n import _

try:
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Gtk, Adw
except ImportError as e:
    print(_("Error: Required dependencies not found: {}").format(e))
    print(_("Please install: python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adwaita-1"))
    sys.exit(1)


def check_dependencies():
    """Check if required GTK version is available"""
    try:
        if Gtk.get_major_version() < 4:
            print(_("Error: GTK 4.0 or higher is required"))
            return False
        return True
        
    except Exception as e:
        print(_("Error checking dependencies: {}").format(e))
        return False


def main():
    """Main application entry point"""
    try:
        # Check dependencies
        if not check_dependencies():
            return 1
        
        # Import and run application
        from application import TacApplication
        
        app = TacApplication()
        return app.run(sys.argv)
        
    except KeyboardInterrupt:
        print("\n" + _("Application interrupted by user."))
        return 0
    except Exception as e:
        print(_("Critical error during startup: {}").format(e))
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())