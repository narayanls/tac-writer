"""
TAC Application Class

Main application controller using GTK4 and libadwaita
"""

# Standard library imports
import gettext
import locale
import os
import warnings
import traceback

# Third-party imports
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gio, Gdk, GLib

# Local imports
from core.config import Config
from core.services import ProjectManager
from ui.main_window import MainWindow
from utils.i18n import _

# Try to load enchant for spell checking
try:
    import enchant
    ENCHANT_AVAILABLE = True
except ImportError:
    ENCHANT_AVAILABLE = False
    enchant = None

# Try to load PyGTKSpellcheck
try:
    import gtkspellcheck
    SPELL_CHECK_AVAILABLE = True
except ImportError:
    SPELL_CHECK_AVAILABLE = False


def setup_system_localization():
    """
    Configure automatic localization based on system locale
    for PyGTKSpellcheck and GTK translations
    """
    
    # Available languages mapping for spellchecker
    SPELLCHECK_LANGUAGES = ['pt_BR', 'en_US', 'en_GB', 'es_ES', 'fr_FR', 'de_DE', 'it_IT']
    FALLBACK_LANGUAGE = 'en_GB'
    
    def detect_system_locale():
        """Detect system locale using multiple sources"""
        
        # Method 1: Environment variables (gettext priority order)
        for env_var in ['LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG']:
            locale_str = os.environ.get(env_var, '').strip()
            if locale_str:
                # Extract first language from list (format: pt_BR:pt:en)
                first_locale = locale_str.split(':')[0]
                if first_locale:
                    return first_locale
        
        # Method 2: locale.getdefaultlocale()
        try:
            default_locale, _ = locale.getdefaultlocale()
            if default_locale:
                return default_locale
        except Exception:
            pass
        
        # Method 3: locale.setlocale with empty string (user's default)
        try:
            current_locale = locale.setlocale(locale.LC_MESSAGES, '')
            if current_locale and current_locale != 'C':
                return current_locale
        except Exception:
            pass
        
        return None
    
    def map_locale_to_spellcheck_language(detected_locale):
        """Map system locale to available spellchecker language"""
        
        if not detected_locale:
            return FALLBACK_LANGUAGE
        
        # Normalize format: pt-BR -> pt_BR, pt.utf8 -> pt
        normalized = detected_locale.replace('-', '_').split('.')[0]
        
        # Direct verification
        if normalized in SPELLCHECK_LANGUAGES:
            return normalized
        
        # Map by language code (first two characters)
        language_code = normalized.split('_')[0].lower()
        
        language_mapping = {
            'pt': 'pt_BR',     # Portuguese -> Brazilian Portuguese
            'en': 'en_GB',     # English -> British English (specified fallback)
            'es': 'es_ES',     # Spanish -> Spain Spanish
            'fr': 'fr_FR',     # French -> France French
            'de': 'de_DE',     # German -> Germany German
            'it': 'it_IT',     # Italian -> Italy Italian
        }
        
        mapped_language = language_mapping.get(language_code, FALLBACK_LANGUAGE)
        return mapped_language
    
    # Detect system locale
    system_locale = detect_system_locale()
    target_language = map_locale_to_spellcheck_language(system_locale)
    
    # Configure system locale
    try:
        # Configure locale using automatic detection
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error as e:
        # Fallback to C locale
        try:
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'C')
            except locale.Error as fallback_error:
                print(_("Warning: Could not set system locale: {}").format(fallback_error))
    
    # Configure environment variables for GTK/GSpell translations
    detected_language = target_language.split('_')[0]  # pt_BR -> pt
    detected_country = target_language  # keep full format
    
    os.environ['LANGUAGE'] = f"{detected_country}:{detected_language}:en"
    os.environ['LC_MESSAGES'] = f"{detected_country}.UTF-8"
    
    # Configure gettext for system libraries (including PyGTKSpellcheck)
    try:
        # Configure known translation domains
        domains_to_configure = [
            'gedit',        # Gedit editor
            'gspell-1',     # GSpell (spell checking library)
            'gtkspell',     # Alternative GTKSpell
            'gtk30',        # GTK 3.0
            'gtk40',        # GTK 4.0
            'glib20',       # GLib
        ]
        
        for domain in domains_to_configure:
            try:
                gettext.bindtextdomain(domain, '/usr/share/locale')
            except Exception:
                pass  # Silent failure for optional domains
    
    except Exception:
        pass  # Silent failure for gettext configuration
    
    return target_language

# Call configuration function
DETECTED_SPELLCHECK_LANGUAGE = setup_system_localization()


class TacApplication(Adw.Application):
    """Main TAC application class"""
    
    def __init__(self):
        super().__init__(
            application_id='org.communitybig.tac',
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )
        GLib.set_prgname('org.communitybig.tac')
        
        # Suppress various system warnings for cleaner output
        self._suppress_warnings()
        
        # Application components
        self.config = Config()
        self.project_manager = ProjectManager()
        self.main_window = None
        
        # Check spell checking availability
        self._check_spell_dependencies()
        
        # Connect signals
        self.connect('activate', self._on_activate)
        self.connect('startup', self._on_startup)
    
    def _suppress_warnings(self):
        """Suppress system warnings for cleaner output"""
        # Suppress enchant warnings (spell checker plugins)
        warnings.filterwarnings("ignore", category=UserWarning, module="enchant")
        
        # Suppress mesa OpenGL warnings
        os.environ.setdefault('MESA_GLTHREAD', 'false')
        
        # Suppress GTK debug messages
        os.environ.setdefault('G_MESSAGES_DEBUG', '')
        
        # Suppress libenchant warnings about missing plugins
        os.environ.setdefault('G_MESSAGES_DEBUG', '')
        
        # Redirect enchant warnings to null
        import logging
        logging.getLogger('enchant').setLevel(logging.ERROR)
    
    def _check_spell_dependencies(self):
        """Check and configure spell checking dependencies"""
        if not SPELL_CHECK_AVAILABLE:
            if os.environ.get('TAC_DEBUG'):
                print(_("PyGTKSpellcheck not installed - disabling spell checking"))
            self.config.set_spell_check_enabled(False)
            return
        
        if not ENCHANT_AVAILABLE:
            if os.environ.get('TAC_DEBUG'):
                print(_("Enchant backend not available - disabling spell checking"))
            self.config.set_spell_check_enabled(False)
            return
        
        try:
            # Check for available dictionaries
            available_dicts = []
            for lang in ['pt_BR', 'en_US', 'en_GB', 'es_ES', 'fr_FR', 'de_DE', 'it_IT']:
                try:
                    if enchant.dict_exists(lang):
                        available_dicts.append(lang)
                except Exception as e:
                    if os.environ.get('TAC_DEBUG'):
                        print(_("Error checking dictionary {}: {}").format(lang, e))

            if available_dicts:
                if os.environ.get('TAC_DEBUG'):
                    print(_("Available spell check dictionaries: {}").format(available_dicts))
                
                # Update config with actually available languages
                self.config.set('spell_check_available_languages', available_dicts)
                
                # Use auto-detected language if available
                if DETECTED_SPELLCHECK_LANGUAGE in available_dicts:
                    detected_language = DETECTED_SPELLCHECK_LANGUAGE
                    if os.environ.get('TAC_DEBUG'):
                        print(_("Using auto-detected language: {}").format(detected_language))
                else:
                    # Fallback to first available
                    detected_language = available_dicts[0]
                    if os.environ.get('TAC_DEBUG'):
                        print(_("Auto-detected language not available, using fallback: {}").format(detected_language))
                
                self.config.set_spell_check_language(detected_language)
                
            else:
                if os.environ.get('TAC_DEBUG'):
                    print(_("No spell check dictionaries found - disabling spell checking"))
                self.config.set_spell_check_enabled(False)
                
        except ImportError as e:
            if os.environ.get('TAC_DEBUG'):
                print(_("Import error while checking spell dependencies: {}").format(e))
            self.config.set_spell_check_enabled(False)
        except Exception as e:
            if os.environ.get('TAC_DEBUG'):
                print(_("Unexpected error checking spell dependencies: {}").format(e))
            self.config.set_spell_check_enabled(False)
    
    def _setup_icon_theme(self):
        """Setup custom icon theme path with PRIORITY"""
        try:
            # Get application's directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            icons_dir = os.path.join(script_dir, 'icons')

            # Check if icons directory exists
            if os.path.exists(icons_dir):
                # Get default icon theme
                icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())

                # Get current search paths
                current_paths = icon_theme.get_search_path()

                # CRITICAL: Prepend (not append) to ensure priority
                new_paths = [icons_dir] + current_paths
                icon_theme.set_search_path(new_paths)

                if os.environ.get('TAC_DEBUG'):
                    print(_("Custom icons loaded with priority: {}").format(icons_dir))

        except Exception as e:
            if os.environ.get('TAC_DEBUG'):
                print(_("Warning: Could not setup icon theme: {}").format(e))
    
    def _on_startup(self, app):
        """Called when application starts"""
        try:
            # Setup custom icon theme path FIRST
            self._setup_icon_theme()
            
            # Setup application actions
            self._setup_actions()
            
            # Setup application menu and shortcuts
            self._setup_menu()
            
            # Apply application theme
            self._setup_theme()
            
        except Exception as e:
            print(_("Error during application startup: {}: {}").format(type(e).__name__, e))
            traceback.print_exc()
    
    def _on_activate(self, app):
        """Called when application is activated"""
        try:
            if not self.main_window:
                self.main_window = MainWindow(
                    application=self,
                    project_manager=self.project_manager,
                    config=self.config
                )
                if os.environ.get('TAC_DEBUG'):
                    print(_("Main window created"))
            
            self.main_window.present()
            if os.environ.get('TAC_DEBUG'):
                print(_("Main window presented"))
            
        except Exception as e:
            print(_("Error activating application: {}: {}").format(type(e).__name__, e))
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
            ('ai_assistant', self._action_ai_assistant),
        ]
        
        try:
            for action_name, callback in actions:
                action = Gio.SimpleAction.new(action_name, None)
                action.connect('activate', callback)
                self.add_action(action)
        except Exception as e:
            print(_("Error setting up actions: {}: {}").format(type(e).__name__, e))
            traceback.print_exc()
    
    def _setup_menu(self):
        """Setup application menu and keyboard shortcuts"""
        try:
            # Keyboard shortcuts
            shortcuts = [
                ('<Control>n', 'app.new_project'),
                ('<Control>o', 'app.open_project'),
                ('<Control>s', 'app.save_project'),
                ('<Control>e', 'app.export_project'),
                ('<Control>comma', 'app.preferences'),
                ('<Control>q', 'app.quit'),
                # Global undo/redo shortcuts (backup if window shortcuts fail)
                ('<Control>z', 'app.undo'),
                ('<Control><Shift>z', 'app.redo'),
                ('<Control><Shift>i', 'app.ai_assistant'),
            ]
            
            for accelerator, action in shortcuts:
                self.set_accels_for_action(action, [accelerator])
                
        except Exception as e:
            print(_("Error setting up menu: {}: {}").format(type(e).__name__, e))
            traceback.print_exc()
    
    def _setup_theme(self):
        """Setup application theme"""
        try:
            style_manager = Adw.StyleManager.get_default()
            
            # Apply theme preference
            if self.config.get('use_dark_theme', False):
                style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            else:
                style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
            
            # Force GTK to reload translations with new locale
            try:
                # This forces GTK to reload translations
                display = Gtk.Widget.get_default_direction()
                
            except Exception:
                pass  # Silent failure for translation reload
            
            # Load custom CSS for drag and drop and spell checking
            css_provider = Gtk.CssProvider()
            css_data = '''
            .card.draggable-hover {
                background: alpha(@accent_color, 0.05);
                border: 1px solid alpha(@accent_color, 0.3);
                transition: all 200ms ease;
            }

            .card.dragging {
                opacity: 0.6;
                transform: scale(0.98);
                transition: all 150ms ease;
            }

            .card.drop-target {
                background: alpha(@accent_color, 0.1);
                border: 2px solid @accent_color;
                transition: all 200ms ease;
            }

            /* Spell check styles */
            .spell-error {
                text-decoration: underline;
                text-decoration-color: red;
                text-decoration-style: wavy;
            }

            /* Undo/redo feedback styles */
            .undo-feedback {
                background: alpha(@success_color, 0.1);
                border: 1px solid alpha(@success_color, 0.3);
                transition: all 300ms ease;
            }

            .redo-feedback {
                background: alpha(@warning_color, 0.1);
                border: 1px solid alpha(@warning_color, 0.3);
                transition: all 300ms ease;
            }

            /* Wiki help button highlight */
            .wiki-help-button {
                background: alpha(@warning_color, 0.35);
                border: 1px solid alpha(@warning_color, 0.5);
                border-radius: 6px;
                transition: all 200ms ease;
            }

            .wiki-help-button:hover {
                background: alpha(@warning_color, 0.45);
                border: 1px solid alpha(@warning_color, 0.6);
            }

            /* Footnote badge styles */
            .footnote-badge {
                background: @accent_bg_color;
                color: @accent_fg_color;
                font-size: 10px;
                font-weight: bold;
                min-width: 16px;
                min-height: 16px;
                padding: 2px 4px;
                border-radius: 8px;
                box-shadow: 0 1px 2px alpha(black, 0.2);
            }
            '''
            
            css_provider.load_from_data(css_data.encode())
            
            # Apply CSS safely
            try:
                display = Gdk.Display.get_default()
                if display:
                    Gtk.StyleContext.add_provider_for_display(
                        display,
                        css_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )
            except Exception as e:
                if os.environ.get('TAC_DEBUG'):
                    print(_("Could not apply CSS: {}").format(e))
                    
        except Exception as e:
            print(_("Error setting up theme: {}: {}").format(type(e).__name__, e))
            traceback.print_exc()
    
    # Existing action methods
    def _action_new_project(self, action, param):
        """Handle new project action"""
        try:
            if self.main_window:
                self.main_window.show_new_project_dialog()
        except Exception as e:
            print(_("Error showing new project dialog: {}: {}").format(type(e).__name__, e))
    
    def _action_open_project(self, action, param):
        """Handle open project action"""
        try:
            if self.main_window:
                self.main_window.show_open_project_dialog()
        except Exception as e:
            print(_("Error showing open project dialog: {}: {}").format(type(e).__name__, e))
    
    def _action_save_project(self, action, param):
        """Handle save project action"""
        try:
            if self.main_window:
                self.main_window.save_current_project()
        except Exception as e:
            print(_("Error saving project: {}: {}").format(type(e).__name__, e))
    
    def _action_export_project(self, action, param):
        """Handle export project action"""
        try:
            if self.main_window:
                self.main_window.show_export_dialog()
        except Exception as e:
            print(_("Error showing export dialog: {}: {}").format(type(e).__name__, e))
    
    def _action_preferences(self, action, param):
        """Handle preferences action"""
        try:
            if self.main_window:
                self.main_window.show_preferences_dialog()
        except Exception as e:
            print(_("Error showing preferences dialog: {}: {}").format(type(e).__name__, e))
    
    def _action_about(self, action, param):
        """Handle about action"""
        try:
            if self.main_window:
                self.main_window.show_about_dialog()
        except Exception as e:
            print(_("Error showing about dialog: {}: {}").format(type(e).__name__, e))

    def _action_ai_assistant(self, action, param):
        """Handle AI assistant action"""
        try:
            if self.main_window:
                self.main_window.open_ai_assistant_prompt()
        except Exception as e:
            print(_("Error opening AI assistant: {}: {}").format(type(e).__name__, e))
    
    def _action_quit(self, action, param):
        """Handle quit action"""
        try:
            self.quit()
        except Exception as e:
            print(_("Error quitting application: {}: {}").format(type(e).__name__, e))
    
    def do_shutdown(self):
        """Called when application shuts down"""
        try:
            # Save configuration
            if self.config:
                self.config.save()
                if os.environ.get('TAC_DEBUG'):
                    print(_("Configuration saved"))
            
            # Call parent shutdown
            Adw.Application.do_shutdown(self)
            
            if os.environ.get('TAC_DEBUG'):
                print(_("Application shutdown complete"))
                
        except Exception as e:
            print(_("Error during shutdown: {}: {}").format(type(e).__name__, e))
            traceback.print_exc()
    
    # Utility methods for debugging
    def debug_spell_config(self):
        """Debug method to print spell check configuration"""
        if self.config:
            self.config.debug_spell_config()
        else:
            print(_("No config available for spell check debug"))
    
    def get_main_window(self):
        """Get reference to main window"""
        return self.main_window
    
    def is_spell_check_available(self):
        """Check if spell checking is available"""
        return SPELL_CHECK_AVAILABLE and self.config.get_spell_check_enabled()
