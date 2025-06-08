#!/usr/bin/env python3
"""
TAC - Text Analysis and Creation
Main entry point for the application
GTK4 + libadwaita academic text writing assistant
"""

import sys
import os
from pathlib import Path


def setup_environment():
    """Setup the application environment and paths"""
    # Get the directory where this script is located
    app_dir = Path(__file__).parent.resolve()
    
    # Add the application directory to Python path if not already present
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    
    return app_dir


def check_dependencies():
    """Check if required dependencies are available"""
    try:
        import gi
        gi.require_version('Gtk', '4.0')
        gi.require_version('Adw', '1')
        from gi.repository import Gtk, Adw
        
        # Check GTK version
        gtk_version = f"{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}"
        print(f"GTK version: {gtk_version}")
        
        if Gtk.get_major_version() < 4:
            print("Error: GTK 4.0 or higher is required")
            return False
            
        return True
        
    except ImportError as e:
        print(f"Error: Required dependencies not found: {e}")
        print("Please install: python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adwaita-1")
        return False
    except Exception as e:
        print(f"Error checking dependencies: {e}")
        return False


def main():
    """Main application entry point"""
    print("=== Starting TAC - Text Analysis and Creation ===")
    print(f"Python: {sys.version}")
    print(f"Platform: {sys.platform}")
    
    try:
        # Setup environment
        app_dir = setup_environment()
        print(f"Application directory: {app_dir}")
        
        # Check dependencies
        if not check_dependencies():
            return 1
        
        # Import and run application
        print("Loading application modules...")
        from application import TacApplication
        
        print("Creating application instance...")
        app = TacApplication()
        
        print("Running TAC application...")
        result = app.run(sys.argv)
        
        print("Application finished.")
        return result
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user.")
        return 0
    except Exception as e:
        print(f"Critical error during startup: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())