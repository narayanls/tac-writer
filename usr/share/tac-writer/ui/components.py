"""
TAC UI Components
Reusable UI components for the TAC application
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GObject, Gdk, GLib, Pango, Graphene
from datetime import datetime

from core.models import Paragraph, ParagraphType, DEFAULT_TEMPLATES
from core.services import ProjectManager
from utils.helpers import TextHelper, FormatHelper
from utils.i18n import _

# Try to load PyGTKSpellcheck
try:
    import gtkspellcheck
    SPELL_CHECK_AVAILABLE = True
    print("PyGTKSpellcheck available - spell checking enabled")
except ImportError:
    SPELL_CHECK_AVAILABLE = False
    print("PyGTKSpellcheck not available - spell checking disabled")

# Global CSS provider cache
_css_cache = {}


def get_cached_css_provider(font_family: str, font_size: int) -> dict:
    """Get or create cached CSS provider"""
    key = f"{font_family}_{font_size}"
    
    if key not in _css_cache:
        css_provider = Gtk.CssProvider()
        class_name = f'paragraph-text-view-{key.replace(" ", "_").replace("\'", "")}'
        css = f"""
        .{class_name} {{
            font-family: '{font_family}';
            font-size: {font_size}pt;
        }}
        """
        css_provider.load_from_data(css.encode())
        _css_cache[key] = {
            'provider': css_provider,
            'class_name': class_name
        }
    
    return _css_cache[key]


class PomodoroTimer(GObject.Object):
    """Pomodoro Timer to help with focus during writing sessions"""
    
    __gtype_name__ = 'TacPomodoroTimer'
    __gsignals__ = {
        'timer-finished': (GObject.SIGNAL_RUN_FIRST, None, (str,)),
        'timer-tick': (GObject.SIGNAL_RUN_FIRST, None, (int,)),
        'session-changed': (GObject.SIGNAL_RUN_FIRST, None, (int, str)),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Timer state
        self.current_session = 1
        self.is_running = False
        self.is_work_time = True
        self.timer_id = None
        
        # Duration in seconds
        self.work_duration = 25 * 60
        self.short_break_duration = 5 * 60
        self.long_break_duration = 15 * 60
        self.max_sessions = 4
        
        # Current remaining time
        self.time_remaining = self.work_duration

    def start_timer(self):
        """Start the timer"""
        if not self.is_running:
            self.is_running = True
            self._start_countdown()

    def stop_timer(self):
        """Stop the timer"""
        if self.is_running:
            self.is_running = False
            if self.timer_id:
                GLib.source_remove(self.timer_id)
                self.timer_id = None

    def reset_timer(self):
        """Reset the timer to initial state"""
        self.stop_timer()
        self.current_session = 1
        self.is_work_time = True
        self.time_remaining = self.work_duration
        self.emit('session-changed', self.current_session, 'work')

    def _start_countdown(self):
        """Start the countdown"""
        if self.timer_id:
            GLib.source_remove(self.timer_id)
        
        self.timer_id = GLib.timeout_add(1000, self._countdown_tick)

    def _countdown_tick(self):
        """Execute every second of countdown"""
        if not self.is_running:
            return False
            
        self.time_remaining -= 1
        self.emit('timer-tick', self.time_remaining)
        
        if self.time_remaining <= 0:
            self._timer_finished()
            return False
            
        return True

    def _timer_finished(self):
        """Called when timer finishes"""
        self.is_running = False
        
        if self.is_work_time:
            # Work period finished, start break
            self.emit('timer-finished', 'work')
            self.is_work_time = False
            
            # Determine break duration
            if self.current_session >= self.max_sessions:
                self.time_remaining = self.long_break_duration
            else:
                self.time_remaining = self.short_break_duration
                
            self.emit('session-changed', self.current_session, 'break')
            
        else:
            # Break period finished
            self.emit('timer-finished', 'break')
            
            if self.current_session >= self.max_sessions:
                # Completed all sessions
                self.reset_timer()
            else:
                # Next work session
                self.current_session += 1
                self.is_work_time = True
                self.time_remaining = self.work_duration
                self.emit('session-changed', self.current_session, 'work')

    def get_time_string(self):
        """Return formatted time as MM:SS string"""
        minutes = self.time_remaining // 60
        seconds = self.time_remaining % 60
        return f"{minutes:02d}:{seconds:02d}"

    def get_session_info(self):
        """Return current session information"""
        if self.is_work_time:
            return {
                'title': _("Session {}").format(self.current_session),
                'type': 'work',
                'session': self.current_session
            }
        else:
            if self.current_session >= self.max_sessions:
                return {
                    'title': _("Long Break"),
                    'type': 'long_break',
                    'session': self.current_session
                }
            else:
                return {
                    'title': _("Rest Time"),
                    'type': 'short_break',
                    'session': self.current_session
                }


class PomodoroDialog(Adw.Window):
    """Pomodoro timer dialog with enhanced design"""
    
    def __init__(self, parent, timer, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title(_("Pomodoro Timer"))
        self.set_default_size(450, 350)
        self.set_resizable(False)
        
        self.timer = timer
        self.parent_window = parent
        
        # Connect timer signals
        self.timer.connect('timer-tick', self._on_timer_tick)
        self.timer.connect('timer-finished', self._on_timer_finished)
        self.timer.connect('session-changed', self._on_session_changed)
        
        self._setup_ui()
        self._setup_styles()
        self._update_display()
        
        # Connect close signal
        self.connect('close-request', self._on_close_request)
    
    def _setup_ui(self):
        """Setup user interface with improved design"""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Custom header with minimize button
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header_box.set_size_request(-1, 50)
        header_box.set_margin_start(20)
        header_box.set_margin_end(15)
        header_box.set_margin_top(15)
        header_box.add_css_class("header-area")
        
        # Spacer to push button to right
        header_spacer = Gtk.Box()
        header_spacer.set_hexpand(True)
        header_box.append(header_spacer)
        
        # Minimize button in top right corner
        self.minimize_button = Gtk.Button()
        self.minimize_button.set_icon_name('window-minimize-symbolic')
        self.minimize_button.set_tooltip_text(_("Minimize"))
        self.minimize_button.add_css_class("flat")
        self.minimize_button.add_css_class("circular")
        self.minimize_button.set_size_request(30, 30)
        self.minimize_button.set_hexpand(False)
        self.minimize_button.set_vexpand(False)
        self.minimize_button.set_halign(Gtk.Align.CENTER)
        self.minimize_button.set_valign(Gtk.Align.CENTER)
        self.minimize_button.connect('clicked', self._on_minimize_clicked)
        header_box.append(self.minimize_button)
        
        main_box.append(header_box)
        
        # Main content area
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=30)
        content_box.set_margin_start(40)
        content_box.set_margin_end(40)
        content_box.set_margin_top(10)
        content_box.set_margin_bottom(40)
        content_box.set_vexpand(True)
        content_box.set_valign(Gtk.Align.CENTER)
        
        # Session title header
        self.session_label = Gtk.Label()
        self.session_label.add_css_class('title-2')
        self.session_label.set_halign(Gtk.Align.CENTER)
        content_box.append(self.session_label)
        
        # Time display with enhanced styling
        time_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        time_container.set_halign(Gtk.Align.CENTER)
        
        self.time_label = Gtk.Label()
        self.time_label.add_css_class('timer-display')
        self.time_label.set_halign(Gtk.Align.CENTER)
        time_container.append(self.time_label)
        
        content_box.append(time_container)
        
        # Control buttons with circular design
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(10)
        
        # Start/Stop button with circular design
        self.start_stop_button = Gtk.Button()
        self.start_stop_button.add_css_class('pill')
        self.start_stop_button.add_css_class('suggested-action')
        self.start_stop_button.set_size_request(120, 45)
        self.start_stop_button.connect('clicked', self._on_start_stop_clicked)
        button_box.append(self.start_stop_button)
        
        # Reset button with circular design
        self.reset_button = Gtk.Button(label=_("Reset"))
        self.reset_button.add_css_class('pill')
        self.reset_button.add_css_class('destructive-action')
        self.reset_button.set_size_request(100, 45)
        self.reset_button.connect('clicked', self._on_reset_clicked)
        button_box.append(self.reset_button)
        
        content_box.append(button_box)
        
        main_box.append(content_box)
        
        # Add to window
        self.set_content(main_box)
        
        # Update initial button state
        self._update_buttons()
    
    def _setup_styles(self):
        """Setup custom CSS styles"""
        try:
            css_provider = Gtk.CssProvider()
            css_data = """
            .timer-display {
                font-size: 72px;
                font-weight: bold;
                font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', monospace;
                color: @accent_color;
                text-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            .header-area {
                background: transparent;
            }
            
            .timer-container {
                background: alpha(@accent_color, 0.1);
                border-radius: 20px;
                padding: 20px;
                box-shadow: inset 0 1px 2px rgba(0,0,0,0.05);
            }
            
            button.pill {
                border-radius: 25px;
                font-weight: 600;
                font-size: 16px;
                transition: all 0.2s ease;
            }
            
            button.pill:hover {
                transform: translateY(-1px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.15);
            }
            
            button.pill:active {
                transform: translateY(0);
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            button.circular {
                border-radius: 15px;
                min-width: 30px;
                min-height: 30px;
                max-width: 30px;
                max-height: 30px;
                padding: 0;
            }
            
            button.circular:hover {
                background: alpha(@accent_color, 0.1);
            }
            """
            
            css_provider.load_from_data(css_data.encode())
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception as e:
            print(_("Error setting up Pomodoro dialog styles: {}").format(e))
    
    def _update_display(self):
        """Update dialog display with current timer information"""
        session_info = self.timer.get_session_info()
        time_str = self.timer.get_time_string()
        
        self.session_label.set_text(session_info['title'])
        self.time_label.set_text(time_str)
    
    def _force_display_update(self):
        """Force complete display update"""
        session_info = self.timer.get_session_info()
        time_str = self.timer.get_time_string()
        
        # Update labels directly
        self.session_label.set_text(session_info['title'])
        self.time_label.set_text(time_str)
        
        # Force interface redraw
        self.session_label.queue_draw()
        self.time_label.queue_draw()
        self.queue_draw()
        
        return False
    
    def _update_buttons(self):
        """Update button states"""
        if self.timer.is_running:
            self.start_stop_button.set_label(_("⏸ Pause"))
            self.start_stop_button.remove_css_class('suggested-action')
            self.start_stop_button.add_css_class('destructive-action')
        else:
            self.start_stop_button.set_label(_("▶ Start"))
            self.start_stop_button.remove_css_class('destructive-action')
            self.start_stop_button.add_css_class('suggested-action')
    
    def _on_timer_tick(self, timer, time_remaining):
        """Update only time during execution"""
        if time_remaining > 0:
            time_str = self.timer.get_time_string()
            self.time_label.set_text(time_str)
    
    def _on_timer_finished(self, timer, timer_type):
        """Handle timer finished - show window again"""
        GLib.idle_add(self._force_display_update)
        GLib.idle_add(self._show_timer_finished, timer_type)
    
    def _on_session_changed(self, timer, session, session_type):
        """Handle session change"""
        GLib.idle_add(self._force_display_update)
        GLib.idle_add(self._update_buttons)
    
    def _show_timer_finished(self, timer_type):
        """Show window when timer finishes"""
        self._force_display_update()
        self._update_buttons()
        
        # Show the window
        self.present()
        
        # Add visual effect
        self._add_finish_animation()
        
        return False
    
    def _add_finish_animation(self):
        """Add visual effect when timer finishes"""
        def blink_effect(count=0):
            if count < 6:
                if count % 2 == 0:
                    self.time_label.add_css_class('accent')
                else:
                    self.time_label.remove_css_class('accent')
                
                GLib.timeout_add(300, lambda: blink_effect(count + 1))
            else:
                self.time_label.remove_css_class('accent')
        
        blink_effect()
    
    def _on_start_stop_clicked(self, button):
        """Handle Start/Stop button"""
        if self.timer.is_running:
            self.timer.stop_timer()
        else:
            self.timer.start_timer()
        
        self._update_buttons()
    
    def _on_reset_clicked(self, button):
        """Handle Reset button"""
        self.timer.reset_timer()
        self._force_display_update()
        self._update_buttons()
    
    def _on_minimize_clicked(self, button):
        """Handle Minimize button"""
        self.set_visible(False)
    
    def _on_close_request(self, window):
        """Handle window close"""
        self.set_visible(False)
        return True
    
    def show_dialog(self):
        """Show the dialog"""
        self._force_display_update()
        self._update_buttons()
        self.present()


class SpellCheckHelper:
    """Helper class for spell checking functionality using PyGTKSpellcheck"""

    def __init__(self, config=None):
        self.config = config
        self.available_languages = []
        self.spell_checkers = {}
        self._load_available_languages()

    def _load_available_languages(self):
        """Load available spell check languages"""
        if not SPELL_CHECK_AVAILABLE:
            return

        try:
            import enchant
            self.available_languages = []
            for lang in ['pt_BR', 'en_US', 'en_GB', 'es_ES', 'fr_FR', 'de_DE', 'it_IT']:
                try:
                    if enchant.dict_exists(lang):
                        self.available_languages.append(lang)
                except Exception as e:
                    print(_("Error checking dictionary {}: {}").format(lang, e))

        except ImportError as e:
            print(_("Enchant not available for spell checking: {}").format(e))
            self.available_languages = ['pt_BR', 'en_US', 'es_ES', 'fr_FR', 'de_DE']

    def setup_spell_check(self, text_view, language=None):
        """Setup spell checking for a TextView using PyGTKSpellcheck"""
        if not SPELL_CHECK_AVAILABLE:
            return None

        try:
            if language:
                spell_language = language
            elif self.config:
                spell_language = self.config.get_spell_check_language()
            else:
                spell_language = 'pt_BR'

            spell_checker = gtkspellcheck.SpellChecker(text_view, language=spell_language)

            checker_id = id(text_view)
            self.spell_checkers[checker_id] = spell_checker

            return spell_checker

        except Exception as e:
            print(_("Spell check setup failed: {}").format(e))
            return None

    def enable_spell_check(self, text_view, enabled=True):
        """Enable or disable spell checking for a TextView"""
        if not SPELL_CHECK_AVAILABLE:
            return

        try:
            checker_id = id(text_view)
            spell_checker = self.spell_checkers.get(checker_id)

            if spell_checker:
                if enabled:
                    spell_checker.enable()
                else:
                    spell_checker.disable()
        except Exception as e:
            print(_("Error toggling spell check: {}").format(e))


class WelcomeView(Gtk.Box):
    """Welcome view shown when no project is open"""

    __gtype_name__ = 'TacWelcomeView'

    __gsignals__ = {
        'create-project': (GObject.SIGNAL_RUN_FIRST, None, (str,)),
        'open-project': (GObject.SIGNAL_RUN_FIRST, None, (object,)),
    }

    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.set_spacing(24)

        # Main welcome content
        self._create_welcome_content()
        # Template selection
        self._create_template_section()
        # Recent projects (if any)
        self._create_recent_section()

    def _create_welcome_content(self):
        """Create main welcome content"""
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_halign(Gtk.Align.CENTER)

        # Icon
        icon = Gtk.Image.new_from_icon_name('document-edit-symbolic')
        icon.set_pixel_size(96)
        icon.add_css_class("welcome-icon")
        content_box.append(icon)

        # Title
        title = Gtk.Label()
        title.set_markup("<span size='x-large' weight='bold'>" + _("Welcome to TAC") + "</span>")
        title.set_halign(Gtk.Align.CENTER)
        content_box.append(title)

        # Subtitle
        subtitle = Gtk.Label()
        subtitle.set_markup("<span size='medium'>" + _("Continuous Argumentation Technique") + "</span>")
        subtitle.set_halign(Gtk.Align.CENTER)
        subtitle.add_css_class("dim-label")
        content_box.append(subtitle)

        # Description
        description = Gtk.Label()
        description.set_text(_("Create structured academic texts with guided paragraph types"))
        description.set_halign(Gtk.Align.CENTER)
        description.set_wrap(True)
        description.set_max_width_chars(50)
        content_box.append(description)

        # Help link section
        help_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        help_box.set_halign(Gtk.Align.CENTER)
        help_box.set_margin_top(16)
        
        wiki_button = Gtk.Button()
        wiki_button.set_label(_("How To Wiki"))
        wiki_button.set_icon_name('help-browser-symbolic')
        wiki_button.add_css_class("flat")
        wiki_button.add_css_class("wiki-help-button")
        wiki_button.set_tooltip_text(_("Access the online documentation and tutorials"))
        wiki_button.connect('clicked', self._on_wiki_clicked)
        help_box.append(wiki_button)
        
        content_box.append(help_box)

        self.append(content_box)

        # Note
        note = Gtk.Label()
        note.set_markup("<span size='small'><i>" + _("Note:") + " " + _("exporting to ODT might require some adjustment in your Office Suite.") + "</i></span>")
        note.set_halign(Gtk.Align.CENTER)
        content_box.append(note)

    def _create_template_section(self):
        """Create template selection section"""
        template_group = Adw.PreferencesGroup()
        template_group.set_title(_("Start Writing"))
        template_group.set_description(_("Choose a template to get started"))

        # Template cards
        for template in DEFAULT_TEMPLATES:
            row = Adw.ActionRow()
            row.set_title(template.name)
            row.set_subtitle(template.description)

            # Start button
            start_button = Gtk.Button()
            start_button.set_label(_("Start"))
            start_button.add_css_class("suggested-action")
            start_button.set_valign(Gtk.Align.CENTER)
            start_button.connect('clicked', lambda btn, tmpl=template.name: self.emit('create-project', tmpl))
            row.add_suffix(start_button)

            template_group.add(row)

        self.append(template_group)

    def _on_wiki_clicked(self, button):
        """Handle wiki button click - open external browser"""
        import subprocess
        import webbrowser
        
        wiki_url = "https://github.com/big-comm/comm-tac-writer/wiki"
        
        try:
            # Try to open with default browser
            webbrowser.open(wiki_url)
        except Exception as e:
            # Fallback: try xdg-open on Linux
            try:
                subprocess.run(['xdg-open', wiki_url], check=False)
            except Exception as fallback_error:
                print(_("Could not open wiki URL: {}").format(fallback_error))

    def _create_recent_section(self):
        """Create recent projects section"""
        # TODO: Implement recent projects display
        pass


class ProjectListWidget(Gtk.Box):
    """Widget for displaying and selecting projects"""

    __gtype_name__ = 'TacProjectListWidget'

    __gsignals__ = {
        'project-selected': (GObject.SIGNAL_RUN_FIRST, None, (object,)),
    }

    def __init__(self, project_manager: ProjectManager, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.project_manager = project_manager
        self.set_vexpand(True)

        # Search entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(_("Search projects..."))
        self.search_entry.set_hexpand(False)
        self.search_entry.set_margin_top(10)
        self.search_entry.set_margin_bottom(5)
        self.search_entry.set_margin_start(25)
        self.search_entry.set_margin_end(25)
        self.search_entry.connect('search-changed', self._on_search_changed)
        self.append(self.search_entry)

        # Scrolled window for project list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        # Project list
        self.project_list = Gtk.ListBox()
        self.project_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.project_list.connect('row-activated', self._on_project_activated)
        self.project_list.set_filter_func(self._filter_projects)

        scrolled.set_child(self.project_list)
        self.append(scrolled)

        # Load projects
        self.refresh_projects()

    def refresh_projects(self):
        """Refresh the project list"""
        # Clear existing projects
        child = self.project_list.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.project_list.remove(child)
            child = next_child

        # Load projects
        projects = self.project_manager.list_projects()

        for project_info in projects:
            row = self._create_project_row(project_info)
            self.project_list.append(row)
            
    def update_project_statistics(self, project_id: str, stats: dict):
        """Update statistics for a specific project without full refresh"""
        child = self.project_list.get_first_child()
        while child:
            if hasattr(child, 'project_info') and child.project_info['id'] == project_id:
                # Update the project info
                child.project_info['statistics'] = stats
                
                # Update the stats label if it exists
                if hasattr(child, 'stats_label'):
                    words = stats.get('total_words', 0)
                    paragraphs = stats.get('total_paragraphs', 0)
                    stats_text = FormatHelper.format_project_stats(words, paragraphs)
                    child.stats_label.set_text(stats_text)
                break
            child = child.get_next_sibling()

    def _create_project_row(self, project_info):
        """Create a row for a project"""
        row = Gtk.ListBoxRow()
        row.project_info = project_info

        # Main box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        # Header with name and date
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        # Project name
        name_label = Gtk.Label()
        name_label.set_text(project_info['name'])
        name_label.set_halign(Gtk.Align.START)
        name_label.set_ellipsize(3)
        name_label.add_css_class("heading")
        header_box.append(name_label)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_box.append(spacer)

        # Action buttons (initially hidden)
        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        actions_box.set_visible(False)

        # Edit button
        edit_button = Gtk.Button()
        edit_button.set_icon_name('edit-symbolic')
        edit_button.set_tooltip_text(_("Rename project"))
        edit_button.add_css_class("flat")
        edit_button.add_css_class("circular")
        edit_button.connect('clicked', lambda b: self._on_edit_project(project_info))
        actions_box.append(edit_button)

        # Delete button
        delete_button = Gtk.Button()
        delete_button.set_icon_name('user-trash-symbolic')
        delete_button.set_tooltip_text(_("Delete project"))
        delete_button.add_css_class("flat")
        delete_button.add_css_class("circular")
        delete_button.connect('clicked', lambda b: self._on_delete_project(project_info))
        actions_box.append(delete_button)

        header_box.append(actions_box)

        # Modification date
        if project_info.get('modified_at'):
            try:
                modified_dt = datetime.fromisoformat(project_info['modified_at'])
                date_label = Gtk.Label()
                date_label.set_text(FormatHelper.format_datetime(modified_dt, 'short'))
                date_label.add_css_class("caption")
                date_label.add_css_class("dim-label")
                header_box.append(date_label)
            except (ValueError, TypeError):
                pass

        box.append(header_box)

        # Statistics
        stats = project_info.get('statistics', {})
        if stats:
            stats_label = Gtk.Label()
            words = stats.get('total_words', 0)
            paragraphs = stats.get('total_paragraphs', 0)
            stats_text = FormatHelper.format_project_stats(words, paragraphs)
            stats_label.set_text(stats_text)
            stats_label.set_halign(Gtk.Align.START)
            stats_label.add_css_class("caption")
            stats_label.add_css_class("dim-label")
            box.append(stats_label)
            
            # Store reference to stats label for easy updating
            row.stats_label = stats_label

        # Setup hover effect
        hover_controller = Gtk.EventControllerMotion()
        hover_controller.connect('enter', lambda c, x, y: actions_box.set_visible(True))
        hover_controller.connect('leave', lambda c: actions_box.set_visible(False))
        row.add_controller(hover_controller)

        row.set_child(box)
        return row

    def _on_project_activated(self, listbox, row):
        """Handle project activation"""
        if row and hasattr(row, 'project_info'):
            self.emit('project-selected', row.project_info)

    def _on_search_changed(self, search_entry):
        """Handle search text change"""
        self.project_list.invalidate_filter()

    def _filter_projects(self, row):
        """Filter projects based on search text"""
        search_text = self.search_entry.get_text().lower()
        if not search_text:
            return True

        if hasattr(row, 'project_info'):
            project_name = row.project_info.get('name', '').lower()
            project_desc = row.project_info.get('description', '').lower()
            return search_text in project_name or search_text in project_desc

        return True

    def _on_edit_project(self, project_info):
        """Handle project rename"""
        dialog = Adw.MessageDialog.new(
            self.get_root(),
            _("Rename Project"),
            _("Enter new name for '{}'").format(project_info['name'])
        )

        # Add entry for new name
        entry = Gtk.Entry()
        entry.set_text(project_info['name'])
        entry.set_margin_start(20)
        entry.set_margin_end(20)
        entry.set_margin_top(10)
        entry.set_margin_bottom(10)

        # Select all text for easy replacement
        entry.grab_focus()
        entry.select_region(0, -1)

        dialog.set_extra_child(entry)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("rename", _("Rename"))
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("rename")

        def save_name():
            """Save the new name"""
            new_name = entry.get_text().strip()
            if new_name and new_name != project_info['name']:
                project = self.project_manager.load_project(project_info['id'])
                if project:
                    project.name = new_name
                    self.project_manager.save_project(project)
                    self.refresh_projects()
            dialog.destroy()

        def on_response(dialog, response):
            if response == "rename":
                save_name()
            else:
                dialog.destroy()

        def on_entry_activate(entry):
            save_name()

        entry.connect('activate', on_entry_activate)
        dialog.connect('response', on_response)
        dialog.present()

    def _on_delete_project(self, project_info):
        """Handle project deletion"""
        dialog = Adw.MessageDialog.new(
            self.get_root(),
            _("Delete '{}'?").format(project_info['name']),
            _("This project will be moved to trash and can be recovered.")
        )

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")

        def on_response(dialog, response):
            if response == "delete":
                success = self.project_manager.delete_project(project_info['id'])
                if success:
                    self.refresh_projects()
            dialog.destroy()

        dialog.connect('response', on_response)
        dialog.present()


class ParagraphEditor(Gtk.Box):
    """Editor for individual paragraphs"""

    __gtype_name__ = 'TacParagraphEditor'

    __gsignals__ = {
        'content-changed': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'remove-requested': (GObject.SIGNAL_RUN_FIRST, None, (str,)),
        'paragraph-reorder': (GObject.SIGNAL_RUN_FIRST, None, (str, str, str)),
    }

    def __init__(self, paragraph: Paragraph, config=None, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.paragraph = paragraph
        self.config = config
        self.text_view = None
        self.text_buffer = None
        self.is_dragging = False
        
        # Spell check components - initialize once
        self.spell_checker = None
        self.spell_helper = None
        self._spell_check_setup = False
        
        # Footnote badge reference
        self.footnote_badge = None
        
        self.set_spacing(8)
        self.add_css_class("card")
        self.set_margin_start(4)
        self.set_margin_end(4)
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        # Create text editor
        self._create_text_editor()
        # Create header
        self._create_header()
        # Setup drag and drop
        self._setup_drag_and_drop()
        # Connect realize signal to apply initial formatting
        self.connect('realize', self._on_realize)

    def _on_realize(self, widget):
        """Called when widget is shown for the first time"""
        try:
            formatting = self.paragraph.formatting
            font_family = formatting.get('font_family', 'Adwaita Sans')
            font_size = formatting.get('font_size', 12)
            
            # Use CSS cache instead of creating individual provider
            css_cache = get_cached_css_provider(font_family, font_size)
            self.text_view.add_css_class(css_cache['class_name'])
            
            # Apply provider globally only once
            if not hasattr(self.__class__, '_css_applied'):
                display = Gdk.Display.get_default()
                if display:
                    Gtk.StyleContext.add_provider_for_display(
                        display,
                        css_cache['provider'],
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )
                self.__class__._css_applied = True
            
            self._apply_formatting()
            
            # Setup spell check synchronously after text_view is ready
            self._setup_spell_check()
            
        except Exception as e:
            print(_("Error during paragraph editor initialization: {}").format(e))

    def _setup_spell_check(self):
        """Setup spell check once when text view is ready"""
        if self._spell_check_setup or not self.text_view or not self.config:
            return
        
        if not self.config.get_spell_check_enabled():
            return
        
        try:
            # Use shared spell helper from main window if available
            if hasattr(self.get_root(), 'spell_helper'):
                self.spell_helper = self.get_root().spell_helper
            else:
                self.spell_helper = SpellCheckHelper(self.config)
            
            self.spell_checker = self.spell_helper.setup_spell_check(self.text_view)
            self._spell_check_setup = True
        except Exception as e:
            print(_("Spell check setup failed: {}").format(e))

    def _create_header(self):
        """Create paragraph header with type and controls"""
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header_box.set_margin_start(12)
        header_box.set_margin_end(12)
        header_box.set_margin_top(8)
        header_box.set_margin_bottom(4)

        # Type label
        type_label = Gtk.Label()
        type_label.set_text(self._get_type_label())
        type_label.add_css_class("caption")
        type_label.add_css_class("accent")
        type_label.set_halign(Gtk.Align.START)
        header_box.append(type_label)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_box.append(spacer)

        # Footnote button with badge (only for specific types)
        if self.paragraph.type in [ParagraphType.INTRODUCTION, ParagraphType.ARGUMENT, ParagraphType.CONCLUSION, ParagraphType.ARGUMENT_RESUMPTION]:
            # Horizontal container for button + badge
            footnote_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            footnote_container.set_halign(Gtk.Align.CENTER)
            footnote_container.set_valign(Gtk.Align.CENTER)
            
            # Footnote button
            footnote_button = Gtk.Button()
            footnote_button.set_icon_name('text-x-generic-symbolic')
            footnote_button.set_tooltip_text(_("Manage footnotes"))
            footnote_button.add_css_class("flat")
            footnote_button.connect('clicked', self._on_footnote_clicked)
            footnote_container.append(footnote_button)
            
            # Badge (small, next to button)
            self.footnote_badge = Gtk.Label()
            self.footnote_badge.add_css_class("footnote-badge")
            self.footnote_badge.set_halign(Gtk.Align.CENTER)
            self.footnote_badge.set_valign(Gtk.Align.CENTER)
            self.footnote_badge.set_opacity(0.0)  # Start invisible
            footnote_container.append(self.footnote_badge)
            
            header_box.append(footnote_container)
            
            # Update badge with initial count
            self._update_footnote_badge()
        else:
            # Initialize badge as None for other types
            self.footnote_badge = None

        # Spell check toggle button
        if SPELL_CHECK_AVAILABLE and self.config:
            self.spell_button = Gtk.ToggleButton()
            self.spell_button.set_icon_name('tools-check-spelling-symbolic')
            self.spell_button.set_tooltip_text(_("Toggle spell checking"))
            self.spell_button.add_css_class("flat")
            self.spell_button.set_active(self.config.get_spell_check_enabled())
            self.spell_button.connect('toggled', self._on_spell_check_toggled)
            header_box.append(self.spell_button)

        # Word count
        self.word_count_label = Gtk.Label()
        self.word_count_label.add_css_class("caption")
        self.word_count_label.add_css_class("dim-label")
        self._update_word_count()
        header_box.append(self.word_count_label)

        # Remove button
        remove_button = Gtk.Button()
        remove_button.set_icon_name('edit-delete-symbolic')
        remove_button.set_tooltip_text(_("Remove paragraph"))
        remove_button.add_css_class("flat")
        remove_button.connect('clicked', self._on_remove_clicked)
        header_box.append(remove_button)

        self.append(header_box)

    def _on_spell_check_toggled(self, button):
        """Handle spell check toggle"""
        if not self.spell_helper or not self.text_view:
            return
        
        enabled = button.get_active()
        
        if enabled and not self._spell_check_setup:
            self._setup_spell_check()
        elif self.spell_checker:
            try:
                self.spell_helper.enable_spell_check(self.text_view, enabled)
            except Exception as e:
                print(_("Error toggling spell check: {}").format(e))
        
        if self.config:
            self.config.set_spell_check_enabled(enabled)

    def _create_text_editor(self):
        """Create the text editing area"""
        # Text buffer
        self.text_buffer = Gtk.TextBuffer()
        self.text_buffer.set_text(self.paragraph.content)
        self.text_buffer.connect('changed', self._on_text_changed)

        # Text view
        self.text_view = Gtk.TextView()
        self.text_view.add_css_class("paragraph-text-view")
        self.text_view.set_buffer(self.text_buffer)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_accepts_tab(False)
        self.text_view.set_margin_start(12)
        self.text_view.set_margin_end(12)
        self.text_view.set_margin_top(8)
        self.text_view.set_margin_bottom(12)

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(100)
        scrolled.set_max_content_height(300)
        scrolled.set_child(self.text_view)

        self.append(scrolled)

    def _setup_drag_and_drop(self):
        """Setup drag and drop functionality for reordering paragraphs"""
        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect('prepare', self._on_drag_prepare)
        drag_source.connect('drag-begin', self._on_drag_begin)
        drag_source.connect('drag-end', self._on_drag_end)
        self.add_controller(drag_source)

        drop_target = Gtk.DropTarget()
        drop_target.set_gtypes([GObject.TYPE_STRING])
        drop_target.set_actions(Gdk.DragAction.MOVE)
        drop_target.connect('accept', self._on_drop_accept)
        drop_target.connect('enter', self._on_drop_enter)
        drop_target.connect('leave', self._on_drop_leave)
        drop_target.connect('drop', self._on_drop)
        self.add_controller(drop_target)

    def _on_drag_prepare(self, drag_source, x, y):
        """Prepare drag operation"""
        content = Gdk.ContentProvider.new_for_value(self.paragraph.id)
        return content

    def _on_drag_begin(self, drag_source, drag):
        """Start drag operation"""
        self.is_dragging = True
        self.add_css_class("dragging")
        try:
            paintable = Gtk.WidgetPaintable.new(self)
            drag_source.set_icon(paintable, 0, 0)
        except Exception:
            pass

    def _on_drag_end(self, drag_source, drag, delete_data):
        """End drag operation"""
        self.is_dragging = False
        self.remove_css_class("dragging")
        self.remove_css_class("drop-target")

    def _on_drop_accept(self, drop_target, drop):
        """Check if drop is acceptable"""
        return drop.get_formats().contain_gtype(GObject.TYPE_STRING)

    def _on_drop_enter(self, drop_target, x, y):
        """Handle drop enter"""
        self.add_css_class("drop-target")
        return Gdk.DragAction.MOVE

    def _on_drop_leave(self, drop_target):
        """Handle drop leave"""
        self.remove_css_class("drop-target")

    def _on_drop(self, drop_target, value, x, y):
        """Handle drop operation"""
        self.remove_css_class("drop-target")

        if isinstance(value, str):
            dragged_paragraph_id = value
            target_paragraph_id = self.paragraph.id

            if dragged_paragraph_id == target_paragraph_id:
                return False

            widget_height = self.get_allocated_height()
            drop_position = "after" if y > widget_height / 2 else "before"

            self.emit('paragraph-reorder', dragged_paragraph_id, target_paragraph_id, drop_position)
            return True

        return False

    def _get_type_label(self) -> str:
        """Get display label for paragraph type"""
        type_labels = {
            ParagraphType.TITLE_1: _("Title 1"),
            ParagraphType.TITLE_2: _("Title 2"),
            ParagraphType.INTRODUCTION: _("Introduction"),
            ParagraphType.ARGUMENT: _("Argument"),
            ParagraphType.ARGUMENT_RESUMPTION: _("Argument Resumption"),
            ParagraphType.QUOTE: _("Quote"),
            ParagraphType.EPIGRAPH: _("Epigraph"),
            ParagraphType.CONCLUSION: _("Conclusion")
        }
        return type_labels.get(self.paragraph.type, _("Paragraph"))

    def _apply_formatting(self):
        """Apply formatting using TextBuffer tags (GTK4 mode)"""
        if not self.text_buffer or not self.text_view:
            return
    
        formatting = self.paragraph.formatting

        # Create text tags
        tag_table = self.text_buffer.get_tag_table()

        # Remove existing format tag
        existing_tag = tag_table.lookup("format")
        if existing_tag:
            tag_table.remove(existing_tag)

        # Create new formatting tag
        format_tag = self.text_buffer.create_tag("format")

        # Apply styles
        if formatting.get('bold', False):
            format_tag.set_property("weight", 700)
        if formatting.get('italic', False):
            format_tag.set_property("style", 2)
        if formatting.get('underline', False):
            format_tag.set_property("underline", 1)

        # Apply tag to all text
        start_iter = self.text_buffer.get_start_iter()
        end_iter = self.text_buffer.get_end_iter()
        self.text_buffer.apply_tag(format_tag, start_iter, end_iter)

        # Apply margins
        left_margin = formatting.get('indent_left', 0.0)
        right_margin = formatting.get('indent_right', 0.0)
        self.text_view.set_left_margin(int(left_margin * 28))
        self.text_view.set_right_margin(int(right_margin * 28))

    def _update_word_count(self):
        """Update word count display"""
        word_count = TextHelper.count_words(self.paragraph.content)
        self.word_count_label.set_text(_("{count} words").format(count=word_count))

    def _on_text_changed(self, buffer):
        """Handle text changes"""
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        text = buffer.get_text(start_iter, end_iter, False)

        self.paragraph.update_content(text)
        self._update_word_count()
        self.emit('content-changed')

    def _on_remove_clicked(self, button):
        """Handle remove button click"""
        dialog = Adw.MessageDialog.new(
            self.get_root(),
            _("Remove Paragraph?"),
            _("This action cannot be undone.")
        )

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("remove", _("Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        dialog.connect('response', self._on_remove_confirmed)
        dialog.present()

    def _on_remove_confirmed(self, dialog, response):
        """Handle remove confirmation"""
        if response == "remove":
            self.emit('remove-requested', self.paragraph.id)
        dialog.destroy()
        
    def _on_footnote_clicked(self, button):
        """Handle footnote button click"""
        dialog = FootnoteDialog(self.get_root(), self.paragraph)
        dialog.connect('footnotes-updated', self._on_footnotes_updated)
        dialog.present()

    def _on_footnotes_updated(self, dialog):
        """Handle footnotes update"""
        self._update_footnote_badge()
        self.emit('content-changed')
        
    def _update_footnote_badge(self):
        """Update the footnote count badge"""
        if not self.footnote_badge:
            return
        
        # Get footnote count
        footnote_count = len(self.paragraph.footnotes) if hasattr(self.paragraph, 'footnotes') and self.paragraph.footnotes else 0
        
        if footnote_count > 0:
            # Show badge with count
            self.footnote_badge.set_text(str(footnote_count))
            self.footnote_badge.set_opacity(1.0)  # Fade in
            
            # Update tooltip
            if footnote_count == 1:
                self.footnote_badge.set_tooltip_text(_("1 footnote"))
            else:
                self.footnote_badge.set_tooltip_text(_("{} footnotes").format(footnote_count))
        else:
            # Hide badge but keep space reserved
            self.footnote_badge.set_text("")
            self.footnote_badge.set_opacity(0.0)  # Fade out
            self.footnote_badge.set_tooltip_text("")


class TextEditor(Gtk.Box):
    """Advanced text editor component"""

    __gtype_name__ = 'TacTextEditor'

    __gsignals__ = {
        'content-changed': (GObject.SIGNAL_RUN_FIRST, None, (str,)),
    }

    def __init__(self, initial_text: str = "", config=None, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.config = config
        
        self.spell_checker = None
        self.spell_helper = SpellCheckHelper(config) if config else None

        self.text_buffer = Gtk.TextBuffer()
        self.text_buffer.set_text(initial_text)
        self.text_buffer.connect('changed', self._on_text_changed)

        self.text_view = Gtk.TextView()
        self.text_view.set_buffer(self.text_buffer)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_accepts_tab(True)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(self.text_view)
        scrolled.set_vexpand(True)

        self.append(scrolled)
        
        GLib.idle_add(self._setup_spell_check_delayed)

    def _setup_spell_check_delayed(self):
        """Setup spell checking after widget is realized"""
        if not self.spell_helper or not self.text_view:
            return False
        
        if self.config and self.config.get_spell_check_enabled():
            try:
                self.spell_checker = self.spell_helper.setup_spell_check(self.text_view)
            except Exception as e:
                print(_("Error setting up spell check: {}").format(e))
        
        return False

    def _on_text_changed(self, buffer):
        """Handle text buffer changes"""
        text = self.get_text()
        self.emit('content-changed', text)

    def get_text(self) -> str:
        """Get current text content"""
        start_iter = self.text_buffer.get_start_iter()
        end_iter = self.text_buffer.get_end_iter()
        return self.text_buffer.get_text(start_iter, end_iter, False)

    def set_text(self, text: str):
        """Set text content"""
        self.text_buffer.set_text(text)

        
class FootnoteDialog(Adw.Window):
    """Dialog for managing footnotes"""

    __gtype_name__ = 'TacFootnoteDialog'

    __gsignals__ = {
        'footnotes-updated': (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, parent, paragraph, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("Manage Footnotes"))
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(500, 400)
        
        self.paragraph = paragraph
        
        # Initialize footnotes list if it doesn't exist
        if not hasattr(self.paragraph, 'footnotes'):
            self.paragraph.footnotes = []
        
        self._create_ui()

    def _create_ui(self):
        """Create the footnote dialog UI"""
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content_box)

        # Header bar
        header_bar = Adw.HeaderBar()
        
        cancel_button = Gtk.Button()
        cancel_button.set_label(_("Cancel"))
        cancel_button.connect('clicked', lambda x: self.destroy())
        header_bar.pack_start(cancel_button)

        save_button = Gtk.Button()
        save_button.set_label(_("Save"))
        save_button.add_css_class("suggested-action")
        save_button.connect('clicked', self._on_save_clicked)
        header_bar.pack_end(save_button)

        content_box.append(header_bar)

        # Main content
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_spacing(16)

        # Instructions
        instruction_label = Gtk.Label()
        instruction_label.set_text(_("Add footnotes that will appear as numbered references in your paragraph:"))
        instruction_label.set_wrap(True)
        instruction_label.set_halign(Gtk.Align.START)
        main_box.append(instruction_label)

        # Footnotes list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(200)

        self.footnotes_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scrolled.set_child(self.footnotes_box)
        main_box.append(scrolled)

        # Add footnote button
        add_button = Gtk.Button()
        add_button.set_label(_("Add Footnote"))
        add_button.set_icon_name('list-add-symbolic')
        add_button.add_css_class("suggested-action")
        add_button.connect('clicked', self._on_add_footnote)
        main_box.append(add_button)

        content_box.append(main_box)

        # Load existing footnotes
        self._load_footnotes()

    def _load_footnotes(self):
        """Load existing footnotes"""
        # Calculate global footnote offset based on previous paragraphs
        global_offset = self._calculate_global_footnote_offset()
        
        for i, footnote_text in enumerate(self.paragraph.footnotes):
            self._add_footnote_row(footnote_text, global_offset + i)

    def _calculate_global_footnote_offset(self) -> int:
        """Calculate how many footnotes exist before this paragraph"""
        if not hasattr(self, 'paragraph') or not hasattr(self.paragraph, 'id'):
            return 0
        
        # Find the project that contains this paragraph
        try:
            # Try to get project from parent window
            parent = self.get_transient_for()
            if hasattr(parent, 'current_project') and parent.current_project:
                project = parent.current_project
                total_footnotes = 0
                
                for p in project.paragraphs:
                    if p.id == self.paragraph.id:
                        break
                    if hasattr(p, 'footnotes') and p.footnotes:
                        total_footnotes += len(p.footnotes)
                
                return total_footnotes
        except Exception:
            pass
        
        return 0

    def _add_footnote_row(self, text="", index=None):
        """Add a footnote row"""
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row_box.set_margin_bottom(4)

        # Number label
        num_label = Gtk.Label()
        
        # Count current children correctly
        if index is not None:
            num_label.set_text(f"{index + 1}.")
        else:
            # Calculate global offset + current children count
            global_offset = self._calculate_global_footnote_offset()
            child_count = 0
            child = self.footnotes_box.get_first_child()
            while child:
                child_count += 1
                child = child.get_next_sibling()
            num_label.set_text(f"{global_offset + child_count + 1}.")
        
        num_label.set_halign(Gtk.Align.START)
        num_label.set_size_request(30, -1)
        row_box.append(num_label)

        # Text entry
        entry = Gtk.Entry()
        entry.set_text(text)
        entry.set_hexpand(True)
        entry.set_placeholder_text(_("Enter footnote text..."))
        row_box.append(entry)

        # Remove button
        remove_button = Gtk.Button()
        remove_button.set_icon_name('edit-delete-symbolic')
        remove_button.add_css_class("flat")
        remove_button.connect('clicked', lambda btn: self._remove_footnote_row(row_box))
        row_box.append(remove_button)

        self.footnotes_box.append(row_box)

    def _on_add_footnote(self, button):
        """Add a new footnote"""
        self._add_footnote_row()

    def _remove_footnote_row(self, row_box):
        """Remove a footnote row"""
        self.footnotes_box.remove(row_box)
        self._renumber_footnotes()

    def _renumber_footnotes(self):
        """Renumber footnote labels"""
        global_offset = self._calculate_global_footnote_offset()
        child = self.footnotes_box.get_first_child()
        index = 1
        while child:
            # Get the first child (number label)
            label = child.get_first_child()
            if isinstance(label, Gtk.Label):
                label.set_text(f"{global_offset + index}.")
            child = child.get_next_sibling()
            index += 1

    def _on_save_clicked(self, button):
        """Save footnotes"""
        footnotes = []
        
        child = self.footnotes_box.get_first_child()
        while child:
            # Get the entry (second child)
            entry_child = child.get_first_child().get_next_sibling()
            if isinstance(entry_child, Gtk.Entry):
                text = entry_child.get_text().strip()
                if text:  # Only add non-empty footnotes
                    footnotes.append(text)
            child = child.get_next_sibling()

        self.paragraph.footnotes = footnotes
        self.emit('footnotes-updated')
        self.destroy()


class FirstRunTour:
    """Interactive tour for first-time users with multiple steps"""

    def __init__(self, main_window, config):
        self.main_window = main_window
        self.config = config
        self.current_step = 0
        self.popover = None

        # Define tour steps with target widget and message
        self.steps = [
            {
                'target': 'new_project_button',
                'title': _("Welcome to TAC Writer!"),
                'message': _("Let's take a quick tour. Click here to create your first project and start writing."),
                'position': Gtk.PositionType.BOTTOM,
            },
            {
                'target': 'sidebar',
                'title': _("Project Library"),
                'message': _("All your projects are listed here. You can search, rename, or delete them at any time."),
                'position': Gtk.PositionType.RIGHT,
            },
            {
                'target': 'pomodoro_button',
                'title': _("Pomodoro Timer"),
                'message': _("Stay focused with the built-in Pomodoro timer. Perfect for writing sessions!"),
                'position': Gtk.PositionType.BOTTOM,
            },
            {
                'target': 'ai_button',
                'title': _("AI Assistant"),
                'message': _("Use AI to revise your exported text. Configure in Preferences. Read wiki for guided configuration."),
                'position': Gtk.PositionType.BOTTOM,
            },
            {
                'target': 'save_button',
                'title': _("Save Your Work"),
                'message': _("Don't worry! Auto-save is enabled by default, but you can also save manually here."),
                'position': Gtk.PositionType.BOTTOM,
            },
        ]

        # Add CSS for overlay
        self._setup_css()

    def _setup_css(self):
        """Setup CSS for tour overlay"""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            /* Dark overlay that covers everything - 50% opacity to see interface */
            .dark-overlay {
                background-color: rgba(0, 0, 0, 0.5);
            }

            /* Popover stays visible and bright */
            popover {
                opacity: 1.0;
            }
        """)

        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def start(self):
        """Start the tour by showing first step"""
        # Simply show the dark overlay (already created in main_window)
        if hasattr(self.main_window, 'tour_dark_overlay'):
            self.main_window.tour_dark_overlay.set_visible(True)

        # Show first step
        GLib.timeout_add(100, lambda: self.show_step(0))

    def show_step(self, step_index):
        """Show a specific step of the tour"""
        if step_index < 0 or step_index >= len(self.steps):
            self.end_tour()
            return

        self.current_step = step_index
        step = self.steps[step_index]

        # Close previous popover if exists
        if self.popover:
            self.popover.popdown()
            self.popover.unparent()
            self.popover = None

        # Get target widget
        target_widget = self._get_target_widget(step['target'])

        if not target_widget:
            # Skip to next step if target not found
            self.show_step(step_index + 1)
            return

        # Create new popover
        self.popover = Gtk.Popover()
        self.popover.set_position(step['position'])
        self.popover.set_autohide(False)  # Don't close when clicking outside
        self.popover.set_has_arrow(True)
        self.popover.add_css_class('tour-popover')

        # Create content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content_box.set_margin_top(20)
        content_box.set_margin_bottom(20)
        content_box.set_margin_start(20)
        content_box.set_margin_end(20)

        # Title
        title_label = Gtk.Label()
        title_label.set_markup(f"<span size='large' weight='bold'>{step['title']}</span>")
        title_label.set_wrap(True)
        title_label.set_max_width_chars(35)
        title_label.set_justify(Gtk.Justification.CENTER)
        content_box.append(title_label)

        # Message
        message_label = Gtk.Label()
        message_label.set_text(step['message'])
        message_label.set_wrap(True)
        message_label.set_max_width_chars(35)
        message_label.set_justify(Gtk.Justification.CENTER)
        content_box.append(message_label)

        # Progress indicator
        progress_label = Gtk.Label()
        progress_label.set_markup(
            f"<span size='small' alpha='60%'>{step_index + 1} / {len(self.steps)}</span>"
        )
        progress_label.set_halign(Gtk.Align.CENTER)
        content_box.append(progress_label)

        # Buttons box
        buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons_box.set_halign(Gtk.Align.CENTER)

        # Skip button (only on first step)
        if step_index == 0:
            skip_button = Gtk.Button.new_with_label(_("Skip Tour"))
            skip_button.connect('clicked', lambda b: self.end_tour())
            buttons_box.append(skip_button)

        # Previous button (if not first step)
        if step_index > 0:
            prev_button = Gtk.Button.new_with_label(_("Previous"))
            prev_button.connect('clicked', lambda b: self.show_step(step_index - 1))
            buttons_box.append(prev_button)

        # Next/Finish button
        if step_index < len(self.steps) - 1:
            next_button = Gtk.Button.new_with_label(_("Next"))
            next_button.add_css_class("suggested-action")
            next_button.connect('clicked', lambda b: self.show_step(step_index + 1))
        else:
            next_button = Gtk.Button.new_with_label(_("Finish"))
            next_button.add_css_class("suggested-action")
            next_button.connect('clicked', lambda b: self.end_tour())

        buttons_box.append(next_button)
        content_box.append(buttons_box)

        self.popover.set_child(content_box)

        # CRITICAL FIX: If target widget is disabled, use window as parent
        # Otherwise GTK will disable the entire popover!
        if target_widget.get_sensitive():
            # Widget is enabled - use it as parent (normal behavior)
            self.popover.set_parent(target_widget)
        else:
            # Widget is DISABLED - use main window as parent
            # and manually position the popover
            self.popover.set_parent(self.main_window)
            self.popover.set_pointing_to(self._get_widget_rect(target_widget))

        self.popover.popup()

    def _get_widget_rect(self, widget):
        """Get the rectangle position of a widget relative to window"""
        # Get widget size
        width = widget.get_width()
        height = widget.get_height()

        # Get widget position relative to window
        # In GTK4, compute_point returns (success, point)
        result = widget.compute_point(self.main_window, Graphene.Point().init(0, 0))

        if result and result[0]:  # Check if successful
            point = result[1]
            rect = Gdk.Rectangle()
            rect.x = int(point.x)
            rect.y = int(point.y)
            rect.width = width
            rect.height = height
            return rect

        # Fallback - use approximate position
        rect = Gdk.Rectangle()
        rect.x = 100
        rect.y = 100
        rect.width = width if width > 0 else 100
        rect.height = height if height > 0 else 40
        return rect

    def _get_target_widget(self, target_name):
        """Get widget by name from main window"""
        if hasattr(self.main_window, target_name):
            return getattr(self.main_window, target_name)
        return None

    def end_tour(self):
        """End the tour and restore normal UI"""
        # Close popover
        if self.popover:
            self.popover.popdown()
            self.popover.unparent()
            self.popover = None

        # Hide dark overlay
        if hasattr(self.main_window, 'tour_dark_overlay'):
            self.main_window.tour_dark_overlay.set_visible(False)

        # Save config to not show tour again
        self.config.set('show_first_run_tutorial', False)
        self.config.save()
