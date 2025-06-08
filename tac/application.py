"""
TAC Application Class
Main application controller using GTK4 and libadwaita
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio

from core.config import Config
from core.services import ProjectManager
from ui.main_window import MainWindow


class TacApplication(Adw.Application):
    """Main TAC application class"""
    
    def __init__(self):
        super().__init__(
            application_id='com.github.tac',
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )
        
        # Application components
        self.config = Config()
        self.project_manager = ProjectManager()
        self.main_window = None
        
        # Connect signals
        self.connect('activate', self._on_activate)
        self.connect('startup', self._on_startup)
        
        print("TacApplication initialized")
    
    def _on_startup(self, app):
        """Called when application starts"""
        print("Application startup...")
        
        # Setup application actions
        self._setup_actions()
        
        # Setup application menu and shortcuts
        self._setup_menu()
        
        # Apply application theme
        self._setup_theme()
    
    def _on_activate(self, app):
        """Called when application is activated"""
        print("Application activate...")
        
        try:
            if not self.main_window:
                self.main_window = MainWindow(
                    application=self,
                    project_manager=self.project_manager,
                    config=self.config
                )
                print("Main window created")
            
            self.main_window.present()
            print("Main window presented")
            
        except Exception as e:
            print(f"Error activating application: {e}")
            import traceback
            traceback.print_exc()
            self.quit()
    
    def _setup_actions(self):
        """Setup application-wide actions"""
        actions = [
            ('new_project', self._action_new_project),
            ('open_project', self._action_open_project),
            ('save_project', self._action_save_project),
            ('export_project', self._action_export_project),
            ('preferences', self._action_preferences),
            ('about', self._action_about),
            ('quit', self._action_quit),
        ]
        
        for action_name, callback in actions:
            action = Gio.SimpleAction.new(action_name, None)
            action.connect('activate', callback)
            self.add_action(action)
        
        print("Application actions setup complete")
    
    def _setup_menu(self):
        """Setup application menu and keyboard shortcuts"""
        # Keyboard shortcuts
        shortcuts = [
            ('<primary>n', 'app.new_project'),
            ('<primary>o', 'app.open_project'),
            ('<primary>s', 'app.save_project'),
            ('<primary>e', 'app.export_project'),
            ('<primary>comma', 'app.preferences'),
            ('<primary>q', 'app.quit'),
        ]
        
        for accelerator, action in shortcuts:
            self.set_accels_for_action(action, [accelerator])
        
        print("Application menu and shortcuts setup complete")
    
    def _setup_theme(self):
        """Setup application theme"""
        style_manager = Adw.StyleManager.get_default()
        
        # Apply theme preference
        if self.config.get('use_dark_theme', False):
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
        
        print("Application theme setup complete")
    
    def _action_new_project(self, action, param):
        """Handle new project action"""
        if self.main_window:
            self.main_window.show_new_project_dialog()
    
    def _action_open_project(self, action, param):
        """Handle open project action"""
        if self.main_window:
            self.main_window.show_open_project_dialog()
    
    def _action_save_project(self, action, param):
        """Handle save project action"""
        if self.main_window:
            self.main_window.save_current_project()
    
    def _action_export_project(self, action, param):
        """Handle export project action"""
        if self.main_window:
            self.main_window.show_export_dialog()
    
    def _action_preferences(self, action, param):
        """Handle preferences action"""
        if self.main_window:
            self.main_window.show_preferences_dialog()
    
    def _action_about(self, action, param):
        """Handle about action"""
        if self.main_window:
            self.main_window.show_about_dialog()
    
    def _action_quit(self, action, param):
        """Handle quit action"""
        self.quit()
    
    def do_shutdown(self):
        """Called when application shuts down"""
        print("Application shutdown...")
        
        # Save configuration
        if self.config:
            self.config.save()
        
        # Call parent shutdown
        Adw.Application.do_shutdown(self)