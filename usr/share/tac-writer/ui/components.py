"""
TAC UI Components
Reusable UI components for the TAC application
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

import re

from gi.repository import Gtk, Adw, GObject, Gdk, GLib, Pango, Graphene
from datetime import datetime

from core.models import Paragraph, ParagraphType, DEFAULT_TEMPLATES
from core.services import ProjectManager
from utils.helpers import TextHelper, FormatHelper
from utils.i18n import _

_CURRENT_DRAG_ID = None

# Try to load PyGTKSpellcheck
try:
    import gtkspellcheck
    SPELL_CHECK_AVAILABLE = True
    print("PyGTKSpellcheck available - spell checking enabled", flush=True)
except ImportError:
    SPELL_CHECK_AVAILABLE = False
    print("PyGTKSpellcheck not available - spell checking disabled", flush=True)

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
                'title': _("Sessão {}").format(self.current_session),
                'type': 'work',
                'session': self.current_session
            }
        else:
            if self.current_session >= self.max_sessions:
                return {
                    'title': _("Pausa Longa"),
                    'type': 'long_break',
                    'session': self.current_session
                }
            else:
                return {
                    'title': _("Tempo de Descanso"),
                    'type': 'short_break',
                    'session': self.current_session
                }


class PomodoroDialog(Adw.Window):
    """Pomodoro timer dialog with enhanced design"""
    
    def __init__(self, parent, timer, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title(_("Temporizador Pomodoro"))
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
        self.minimize_button.set_icon_name('tac-window-minimize-symbolic')
        self.minimize_button.set_tooltip_text(_("Minimizar"))
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
        self.reset_button = Gtk.Button(label=_("Reiniciar"))
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
            print(_("Erro ao configurar estilos do Pomodoro: {}").format(e))
    
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
            self.start_stop_button.set_label(_("⏸ Pausar"))
            self.start_stop_button.remove_css_class('suggested-action')
            self.start_stop_button.add_css_class('destructive-action')
        else:
            self.start_stop_button.set_label(_("▶ Iniciar"))
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
            # Try to list the sayings that the enchant actually sees
            try:
                broker = enchant.Broker()
                dicts = broker.list_dicts()
                print(f"DEBUG: Dicionários brutos encontrados pelo Enchant: {[d[0] for d in dicts]}", flush=True)
            except:
                pass

            self.available_languages = []
            # Expanded list to try to catch variations
            candidates = ['pt_BR', 'pt-BR', 'pt', 'en_US', 'en-US', 'en', 'es_ES', 'es']
            
            for lang in candidates:
                try:
                    if enchant.dict_exists(lang):
                        self.available_languages.append(lang)
                except Exception as e:
                    print(f"Error checking dictionary {lang}: {e}", flush=True)

        except ImportError as e:
            print(f"Enchant not available for spell checking: {e}", flush=True)

    def setup_spell_check(self, text_view, language=None):
        """Setup spell checking for a TextView using PyGTKSpellcheck"""
        if not SPELL_CHECK_AVAILABLE:
            print("DEBUG: Spell check not available (module import failed)", flush=True)
            return None

        try:
            # Determine the language
            if language:
                target_lang = language
            elif self.config:
                target_lang = self.config.get_spell_check_language()
            else:
                target_lang = 'pt_BR'

            print(f"DEBUG: Configurando SpellChecker para TextView {id(text_view)} com idioma '{target_lang}'", flush=True)

            spell_checker = None
            
            # Tenta criar com o idioma exato (SEM O ARGUMENTO enable=True)
            try:
                spell_checker = gtkspellcheck.SpellChecker(text_view, language=target_lang)
            except Exception as e1:
                print(f"DEBUG: Falha inicial com '{target_lang}': {e1}", flush=True)
                
                # Try common variations on Linux/Arch
                alternatives = []
                if '_' in target_lang:
                    alternatives.append(target_lang.replace('_', '-')) # pt_BR -> pt-BR
                elif '-' in target_lang:
                    alternatives.append(target_lang.replace('-', '_')) # pt-BR -> pt_BR
                
                # Tenta só o código do idioma (ex: pt)
                base_lang = target_lang.split('_')[0].split('-')[0]
                if base_lang != target_lang:
                    alternatives.append(base_lang)

                for alt in alternatives:
                    try:
                        print(f"DEBUG: Tentando alternativa '{alt}'...", flush=True)
                        # WITHOUT THE enable=True ARGUMENT HERE TOO
                        spell_checker = gtkspellcheck.SpellChecker(text_view, language=alt)
                        print(f"DEBUG: Sucesso com '{alt}'!", flush=True)
                        break
                    except Exception as e_alt:
                        print(f"DEBUG: Falha com alternativa '{alt}': {e_alt}", flush=True)
                        continue

            if spell_checker:
                # Force enable NOW, after creation
                spell_checker.enabled = True
                
                checker_id = id(text_view)
                self.spell_checkers[checker_id] = spell_checker
                print(f"DEBUG: SpellChecker ANEXADO com sucesso. Idioma: {spell_checker.language}. Ativado: {spell_checker.enabled}", flush=True)
                return spell_checker
            else:
                print("DEBUG: Não foi possível inicializar o SpellChecker com nenhum idioma compatível.", flush=True)
                return None

        except Exception as e:
            print(f"DEBUG: Erro fatal no setup_spell_check: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return None

    def enable_spell_check(self, text_view, enabled=True):
        """Enable or disable spell checking for a TextView"""
        if not SPELL_CHECK_AVAILABLE:
            return

        try:
            checker_id = id(text_view)
            spell_checker = self.spell_checkers.get(checker_id)

            if spell_checker:
                spell_checker.enabled = enabled
                print(f"DEBUG: Spell check alternado para {enabled} no widget {checker_id}", flush=True)
        except Exception as e:
            print(f"Error toggling spell check: {e}", flush=True)


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
        icon = Gtk.Image.new_from_icon_name('tac-document-edit-symbolic')
        icon.set_pixel_size(96)
        icon.add_css_class("welcome-icon")
        content_box.append(icon)

        # Title
        title = Gtk.Label()
        title.set_markup("<span size='x-large' weight='bold'>" + _("Bem-vindo ao TAC") + "</span>")
        title.set_halign(Gtk.Align.CENTER)
        content_box.append(title)

        # Subtitle
        subtitle = Gtk.Label()
        subtitle.set_markup("<span size='medium'>" + _("Técnica de Argumentação Contínua") + "</span>")
        subtitle.set_halign(Gtk.Align.CENTER)
        subtitle.add_css_class("dim-label")
        content_box.append(subtitle)

        # Description
        description = Gtk.Label()
        description.set_text(_("Crie textos acadêmicos estruturados com parágrafos guiados"))
        description.set_halign(Gtk.Align.CENTER)
        description.set_wrap(True)
        description.set_max_width_chars(50)
        content_box.append(description)

        # Help link section
        help_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        help_box.set_halign(Gtk.Align.CENTER)
        help_box.set_margin_top(16)
        
        wiki_button = Gtk.Button()
        wiki_button.set_label(_("Wiki Como Fazer"))
        wiki_button.set_icon_name('tac-help-browser-symbolic')
        wiki_button.add_css_class("flat")
        wiki_button.add_css_class("wiki-help-button")
        wiki_button.set_tooltip_text(_("Acesse a documentação online e tutoriais"))
        wiki_button.connect('clicked', self._on_wiki_clicked)
        help_box.append(wiki_button)
        
        content_box.append(help_box)

        self.append(content_box)

        # Note
        note = Gtk.Label()
        note.set_markup("<span size='small'><i>" + _("Nota:") + " " + _("exportar para ODT pode exigir ajustes na sua Suíte Office.") + "</i></span>")
        note.set_halign(Gtk.Align.CENTER)
        content_box.append(note)

    def _create_template_section(self):
        """Create template selection section"""
        template_group = Adw.PreferencesGroup()
        template_group.set_title(_("Começar a Escrever"))
        template_group.set_description(_("Escolha um modelo para começar"))

        # Template cards
        # 1. Deafult
        row_std = Adw.ActionRow()
        row_std.set_title(_("Ensaio Acadêmico"))
        row_std.set_subtitle(_("Estrutura padrão (Humanas, Biológicas, etc)"))

        btn_std = Gtk.Button()
        btn_std.set_label(_("Iniciar"))
        btn_std.add_css_class("suggested-action")
        btn_std.set_valign(Gtk.Align.CENTER)
        # Send 'standard' to main_window
        btn_std.connect('clicked', lambda btn: self.emit('create-project', 'standard'))

        row_std.add_suffix(btn_std)
        template_group.add(row_std)

        # 2. LaTeX
        row_latex = Adw.ActionRow()
        row_latex.set_title(_("Ensaio LaTeX"))
        row_latex.set_subtitle(_("Otimizado para Exatas (Suporte a fórmulas)"))

        btn_latex = Gtk.Button()
        btn_latex.set_label(_("Iniciar"))
        btn_latex.add_css_class("suggested-action") 
        btn_latex.set_valign(Gtk.Align.CENTER)
        # Send 'latex' to main_window
        btn_latex.connect('clicked', lambda btn: self.emit('create-project', 'latex'))

        row_latex.add_suffix(btn_latex)
        template_group.add(row_latex)

        # 3. IT Essay (New Implementation)
        row_it = Adw.ActionRow()
        row_it.set_title(_("Ensaio T.I."))
        row_it.set_subtitle(_("Focado em tecnologia (Suporte a blocos de código)"))

        btn_it = Gtk.Button()
        btn_it.set_label(_("Iniciar"))
        btn_it.add_css_class("suggested-action")
        btn_it.set_valign(Gtk.Align.CENTER)
        # Send 'it_essay' to main_window
        btn_it.connect('clicked', lambda btn: self.emit('create-project', 'it_essay'))

        row_it.add_suffix(btn_it)
        template_group.add(row_it)

        self.append(template_group)

    def _on_wiki_clicked(self, button):
        """Handle wiki button click - open external browser"""
        wiki_url = "https://github.com/narayanls/tac-writer/wiki"
        
        try:
            # Try Gtk.UriLauncher (GTK 4.10+)
            launcher = Gtk.UriLauncher.new(uri=wiki_url)
            launcher.launch(self.get_root(), None, None)
        except AttributeError:
            # Fallback
            try:
                Gio.AppInfo.launch_default_for_uri(wiki_url, None)
            except Exception as e:
                print(_("Não foi possível abrir URL da wiki: {}").format(e))
        except Exception as e:
            print(_("Erro ao lançar navegador: {}").format(e))

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
        self.search_entry.set_placeholder_text(_("Pesquisar projetos..."))
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
        edit_button.set_icon_name('tac-edit-symbolic')
        edit_button.set_tooltip_text(_("Renomear projeto"))
        edit_button.add_css_class("flat")
        edit_button.add_css_class("circular")
        edit_button.connect('clicked', lambda b: self._on_edit_project(project_info))
        actions_box.append(edit_button)

        # Delete button
        delete_button = Gtk.Button()
        delete_button.set_icon_name('tac-user-trash-symbolic')
        delete_button.set_tooltip_text(_("Excluir projeto"))
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
            _("Renomear Projeto"),
            _("Digite novo nome para '{}'").format(project_info['name'])
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
        dialog.add_response("cancel", _("Cancelar"))
        dialog.add_response("rename", _("Renomear"))
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
            _("Excluir '{}'?").format(project_info['name']),
            _("Este projeto será movido para a lixeira e pode ser recuperado.")
        )

        dialog.add_response("cancel", _("Cancelar"))
        dialog.add_response("delete", _("Excluir"))
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

        self.drag_start_x = 0
        self.drag_start_y = 0
        
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
        
        # Use 'map' instead of 'realize'
        self.connect('map', self._on_map)

    def _on_map(self, widget):
        """Called when widget is mapped to screen (visible)"""
        try:
            formatting = self.paragraph.formatting
            
            # Logic for LaTeX
            if self.paragraph.type == ParagraphType.LATEX:
                font_family = 'Monospace'
                font_size = formatting.get('font_size', 11)
                
                # Add specific visual style
                css_provider = Gtk.CssProvider()
                css = """
                .latex-view {
                    font-family: 'Monospace';
                    background-color: alpha(@theme_fg_color, 0.05);
                    border-radius: 4px;
                    padding: 6px;
                }
                """
                css_provider.load_from_data(css.encode())
                self.text_view.get_style_context().add_provider(
                    css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                self.text_view.add_css_class("latex-view")
                
            # Logic for Code Block
            elif self.paragraph.type == ParagraphType.CODE:
                font_family = 'Monospace'
                font_size = formatting.get('font_size', 10)
                
                # Add specific visual style for Code
                css_provider = Gtk.CssProvider()
                css = """
                .code-view {
                    font-family: 'Monospace';
                    background-color: #f3f3f3;
                    color: #2e3436;
                    border: 1px solid alpha(#000000, 0.1);
                    border-radius: 4px;
                    padding: 8px;
                }
                """

                css_provider.load_from_data(css.encode())
                self.text_view.get_style_context().add_provider(
                    css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                self.text_view.add_css_class("code-view")

            else:
                # Default type
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
            
            # DEBUG: Visual confirmation in terminal ---
            print(f"DEBUG: ParagraphEditor {self.paragraph.id[:8]} MAPPED (Type: {self.paragraph.type})", flush=True)
            
        except Exception as e:
            print(f"Error during paragraph editor initialization: {e}", flush=True)


    def _setup_spell_check(self):
        """Setup spell check once when text view is ready"""
        # If LATEX or CODE disable spellcheck
        if self.paragraph.type in [ParagraphType.LATEX, ParagraphType.CODE]:
            return False
        # DEBUG: Call tracking
        print(f"DEBUG: Tentando setup spell check para {self.paragraph.id[:8]}...", flush=True)

        if self._spell_check_setup or not self.text_view:
            return False # Retorna False para parar o timeout
        
        if not self.config or not self.config.get_spell_check_enabled():
            print("DEBUG: Spell check desabilitado na config ou config ausente.", flush=True)
            return False
        
        try:
            # Try to get the helper from the main window, otherwise it will create a new one
            root = self.get_root()
            if root and hasattr(root, 'spell_helper'):
                self.spell_helper = root.spell_helper
            else:
                if not hasattr(self, 'local_spell_helper'):
                    self.local_spell_helper = SpellCheckHelper(self.config)
                self.spell_helper = self.local_spell_helper
            
            self.spell_checker = self.spell_helper.setup_spell_check(self.text_view)
            
            if self.spell_checker:
                self._spell_check_setup = True
            
        except Exception as e:
            print(f"Spell check setup failed: {e}", flush=True)
            import traceback
            traceback.print_exc()
            
        return False

    def _create_header(self):
        """Create paragraph header with type and controls"""
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header_box.set_margin_start(12)
        header_box.set_margin_end(12)
        header_box.set_margin_top(8)
        header_box.set_margin_bottom(4)

        # Drag Handle
        self.drag_handle = Gtk.Button()
        self.drag_handle.set_icon_name('open-menu-symbolic')
        self.drag_handle.set_icon_name('view-grid-symbolic') 
        self.drag_handle.add_css_class("flat")
        self.drag_handle.add_css_class("drag-handle")
        self.drag_handle.set_tooltip_text(_("Arraste para mover"))
        self.drag_handle.set_cursor(Gdk.Cursor.new_from_name("grab", None))
        header_box.append(self.drag_handle)
        
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
            footnote_button.set_icon_name('tac-text-x-generic-symbolic')
            footnote_button.set_tooltip_text(_("Gerenciar notas de rodapé"))
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

        # Container for buttons (Lazy Loading)
        self.format_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.format_box.add_css_class("linked")
        
        # Flag to know if the buttons have already been created
        self._formatting_buttons_created = False
        
        header_box.append(self.format_box)

        # Spell check toggle button
        if SPELL_CHECK_AVAILABLE and self.config and self.paragraph.type not in [ParagraphType.LATEX, ParagraphType.CODE]:
            self.spell_button = Gtk.ToggleButton()
            self.spell_button.set_icon_name('tac-tools-check-spelling-symbolic')
            self.spell_button.set_tooltip_text(_("Alternar verificação ortográfica"))
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
        remove_button.set_icon_name('tac-edit-delete-symbolic')
        remove_button.set_tooltip_text(_("Remover parágrafo"))
        remove_button.add_css_class("flat")
        remove_button.connect('clicked', self._on_remove_clicked)
        header_box.append(remove_button)

        self.append(header_box)

    def _on_format_clicked(self, button, tag_name):
        """Handle formatting button clicks"""
        bounds = self.text_buffer.get_selection_bounds()
        if not bounds:
            # Show popover warning
            popover = Gtk.Popover()
            label = Gtk.Label(label=_("Selecione uma palavra ou seção para formatar primeiro."))
            label.set_margin_start(10)
            label.set_margin_end(10)
            label.set_margin_top(10)
            label.set_margin_bottom(10)
            popover.set_child(label)
            popover.set_parent(button)
            popover.popup()
            return
        
        start, end = bounds
        
        # Check if tag is present at the start of selection to toggle
        tag = self.text_buffer.get_tag_table().lookup(tag_name)
        if not tag:
            return

        # Simple toggle logic: if start has tag, remove from whole selection. Else apply.
        if start.has_tag(tag):
            self.text_buffer.remove_tag_by_name(tag_name, start, end)
        else:
            self.text_buffer.apply_tag_by_name(tag_name, start, end)

        # Forces update for saving tags <b>, <i>, etc.
        self._on_text_changed(self.text_buffer)

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
                print(_("Erro ao alternar verificação ortográfica: {}").format(e))
        
        if self.config:
            self.config.set_spell_check_enabled(enabled)

    def _create_text_editor(self):
        """Create the text editing area"""
        # Text buffer
        self.text_buffer = Gtk.TextBuffer()

        # Define Formatting Tags
        tag_table = self.text_buffer.get_tag_table()
        if not tag_table.lookup('bold'):
            self.text_buffer.create_tag('bold', weight=Pango.Weight.BOLD)
        if not tag_table.lookup('italic'):
            self.text_buffer.create_tag('italic', style=Pango.Style.ITALIC)
        if not tag_table.lookup('underline'):
            self.text_buffer.create_tag('underline', underline=Pango.Underline.SINGLE)
        # ------------------------------

        # Use new method for formatting text
        self._set_content_from_storage(self.paragraph.content)

        # Connect signal AFTER loading text
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

        # Detect focus to create toolbar on demand
        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect("enter", self._on_focus_enter)
        self.text_view.add_controller(focus_controller)

    def _on_focus_enter(self, controller):
        """Called when text view gains focus"""
        self._ensure_formatting_buttons()

        # Active spellcheck only when focus
        if not self._spell_check_setup:
            GLib.idle_add(self._setup_spell_check)

    def _ensure_formatting_buttons(self):
        """Create formatting buttons only when needed"""
        if self._formatting_buttons_created:
            return

        # If LaTeX or CODE, do not create text formatting buttons
        if self.paragraph.type in [ParagraphType.LATEX, ParagraphType.CODE]:
            return

        # Bold
        img_bold = Gtk.Image.new_from_icon_name('tac-format-text-bold-symbolic')
        img_bold.set_pixel_size(24)
        btn_bold = Gtk.Button()
        btn_bold.set_child(img_bold)
        btn_bold.set_tooltip_text(_("Negrito"))
        btn_bold.add_css_class("flat")
        btn_bold.connect('clicked', lambda b: self._on_format_clicked(b, 'bold'))
        self.format_box.append(btn_bold)
        
        # Italic
        btn_italic = Gtk.Button(icon_name='tac-format-text-italic-symbolic')
        btn_italic.set_tooltip_text(_("Itálico"))
        btn_italic.add_css_class("flat")
        btn_italic.connect('clicked', lambda b: self._on_format_clicked(b, 'italic'))
        self.format_box.append(btn_italic)
        
        # Underline
        btn_underline = Gtk.Button(icon_name='tac-format-text-underline-symbolic')
        btn_underline.set_tooltip_text(_("Sublinhado"))
        btn_underline.add_css_class("flat")
        btn_underline.connect('clicked', lambda b: self._on_format_clicked(b, 'underline'))
        self.format_box.append(btn_underline)

        self._formatting_buttons_created = True

    # NEW DEFS FOR FORMATTING PERSISTENCE
    def _get_content_for_storage(self) -> str:
        """
        Serializes the buffer content into a string with HTML-like tags 
        (<b>, <i>, <u>) for storage.
        """
        if not self.text_buffer:
            return ""

        start_iter = self.text_buffer.get_start_iter()
        end_iter = self.text_buffer.get_end_iter()
        
        if start_iter.equal(end_iter):
            return ""

        output = []
        current_iter = start_iter
        
        while not current_iter.is_end():
            # Find the next point where tags change or the end of text
            next_iter = current_iter.copy()
            if not next_iter.forward_to_tag_toggle(None):
                next_iter = end_iter

            # Get the text from this segment
            text_segment = self.text_buffer.get_text(current_iter, next_iter, False)
            
            # Check which tags are active at the beginning of this segment
            tags = current_iter.get_tags()
            tag_names = [t.get_property('name') for t in tags]
            
            # Apply opening tags
            if 'bold' in tag_names: output.append('<b>')
            if 'italic' in tag_names: output.append('<i>')
            if 'underline' in tag_names: output.append('<u>')
            
            output.append(text_segment)
            
            # Aplicar tags de fechamento (na ordem inversa)
            if 'underline' in tag_names: output.append('</u>')
            if 'italic' in tag_names: output.append('</i>')
            if 'bold' in tag_names: output.append('</b>')
            
            current_iter = next_iter

        return "".join(output)

    def _set_content_from_storage(self, html_content: str):
        """
        Parses the stored string with tags and applies them to the buffer.
        """
        if not self.text_buffer:
            return

        # Clear current buffer
        self.text_buffer.set_text("")
        
        if not html_content:
            return

        # Regex to separate tags from text
        # Capture <b>, </b>, <i>, </i>, <u>, </u>
        parts = re.split(r'(</?[biu]>)', html_content)
        
        active_tags = set()
        
        for part in parts:
            if not part:
                continue
                
            if part == '<b>':
                active_tags.add('bold')
            elif part == '</b>':
                active_tags.discard('bold')
            elif part == '<i>':
                active_tags.add('italic')
            elif part == '</i>':
                active_tags.discard('italic')
            elif part == '<u>':
                active_tags.add('underline')
            elif part == '</u>':
                active_tags.discard('underline')
            else:
                iter_loc = self.text_buffer.get_end_iter()
                
                if active_tags:
                    # Native GTK method: inserts and applies tags at once
                    self.text_buffer.insert_with_tags_by_name(iter_loc, part, *list(active_tags))
                else:
                    self.text_buffer.insert(iter_loc, part)

    def _setup_dnd_styles(self):
        """Setup specific Drag and Drop visual styles (Efeito Kanri - Margens)"""
        css_provider = Gtk.CssProvider()
        
        # Using margin instead of border
        css = """
        .drop-target-top {
            margin-top: 60px;
            transition: margin 0.15s ease-out;
            background-image: linear-gradient(to bottom, @accent_color 2px, transparent 2px);
        }
        
        .drop-target-bottom {
            margin-bottom: 60px;
            transition: margin 0.15s ease-out;
            background-image: linear-gradient(to top, @accent_color 2px, transparent 2px);
        }
        
        .dragging {
            opacity: 0.15;
        }
        """
        try:
            css_provider.load_from_data(css.encode())
            self.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception as e:
            print(f"Erro ao carregar estilos DnD: {e}")

    def _setup_drag_and_drop(self):
        """Setup drag and drop functionality using Global State for stability"""
        
        # DRAG SOURCE
        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        
        drag_source.connect('prepare', self._on_drag_prepare)
        drag_source.connect('drag-begin', self._on_drag_begin)
        drag_source.connect('drag-end', self._on_drag_end)
        
        if hasattr(self, 'drag_handle'):
            self.drag_handle.add_controller(drag_source)
        else:
            self.add_controller(drag_source)

    def _on_drag_prepare(self, drag_source, x, y):
        """Prepare drag - Set global state and return dummy content"""
        global _CURRENT_DRAG_ID

        self.drag_start_x = x
        self.drag_start_y = y

        # Saves the ID to the Python global variable
        _CURRENT_DRAG_ID = self.paragraph.id
        return Gdk.ContentProvider.new_for_value("")

    def _on_drag_begin(self, drag_source, drag):
        """Start drag operation"""
        self.is_dragging = True
        self.add_css_class("dragging")
        
        if hasattr(self, 'drag_handle'):
            self.drag_handle.set_cursor(Gdk.Cursor.new_from_name("grabbing", None))

        try:
            paintable = Gtk.WidgetPaintable.new(self)
            
            # Try "grab" middle card
            icon_x = self.get_width() // 2
            icon_y = 20 # Top card
            
            drag_source.set_icon(paintable, icon_x, icon_y)
                
        except Exception as e:
            print(f"Erro no drag icon: {e}")

    def _on_drag_end(self, drag_source, drag, delete_data):
        """End drag operation - Clear global state"""
        global _CURRENT_DRAG_ID
        self.is_dragging = False
        self.remove_css_class("dragging")
        
        # Clears the global variable
        _CURRENT_DRAG_ID = None
        
        if hasattr(self, 'drag_handle'):
            self.drag_handle.set_cursor(Gdk.Cursor.new_from_name("grab", None))

    def _get_type_label(self) -> str:
        """Get display label for paragraph type"""
        type_labels = {
            ParagraphType.TITLE_1: _("Título 1"),
            ParagraphType.TITLE_2: _("Título 2"),
            ParagraphType.INTRODUCTION: _("Introdução"),
            ParagraphType.ARGUMENT: _("Argumento"),
            ParagraphType.ARGUMENT_RESUMPTION: _("Retomada do Argumento"),
            ParagraphType.QUOTE: _("Citação"),
            ParagraphType.EPIGRAPH: _("Epígrafe"),
            ParagraphType.CONCLUSION: _("Conclusão"),
            ParagraphType.LATEX: _("Equação LaTeX"),
            ParagraphType.CODE: _("Bloco de Código")
        }
        return type_labels.get(self.paragraph.type, _("Parágrafo"))

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
         # Check if label already exist before use it
        if not hasattr(self, 'word_count_label') or self.word_count_label is None:
            return
        word_count = TextHelper.count_words(self.paragraph.content)
        self.word_count_label.set_text(_("{count} palavras").format(count=word_count))

    def _on_text_changed(self, buffer):
        """Handle text changes"""
        # Use method that capture formatting tags
        formatted_text = self._get_content_for_storage()

        self.paragraph.update_content(formatted_text)
        self._update_word_count()
        self.emit('content-changed')

    def _on_remove_clicked(self, button):
        """Handle remove button click"""
        dialog = Adw.MessageDialog.new(
            self.get_root(),
            _("Remover Parágrafo?"),
            _("Esta ação não pode ser desfeita.")
        )

        dialog.add_response("cancel", _("Cancelar"))
        dialog.add_response("remove", _("Remover"))
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
                self.footnote_badge.set_tooltip_text(_("1 nota de rodapé"))
            else:
                self.footnote_badge.set_tooltip_text(_("{} notas de rodapé").format(footnote_count))
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
                print(_("Erro ao configurar verificação ortográfica: {}").format(e))
        
        return False

    def _on_text_changed(self, buffer):
        """Handle text buffer changes"""
        # Using new serialization method
        formatted_text = self._get_content_for_storage()

        self.paragraph.update_content(formatted_text)
        self._update_word_count()
        self.emit('content-changed')
        
        
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
        self.set_title(_("Gerenciar Notas de Rodapé"))
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
        cancel_button.set_label(_("Cancelar"))
        cancel_button.connect('clicked', lambda x: self.destroy())
        header_bar.pack_start(cancel_button)

        save_button = Gtk.Button()
        save_button.set_label(_("Salvar"))
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
        instruction_label.set_text(_("Adicione notas de rodapé que aparecerão como referências numeradas:"))
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
        add_button.set_label(_("Adicionar Nota"))
        add_button.set_icon_name('tac-list-add-symbolic')
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
        entry.set_placeholder_text(_("Digite o texto da nota..."))
        row_box.append(entry)

        # Remove button
        remove_button = Gtk.Button()
        remove_button.set_icon_name('tac-edit-delete-symbolic')
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
                'title': _("Bem-vindo ao Tac Writer!"),
                'message': _("Vamos fazer um tour rápido. Clique aqui para criar seu primeiro projeto."),
                'position': Gtk.PositionType.BOTTOM,
            },
            {
                'target': 'sidebar',
                'title': _("Biblioteca de Projetos"),
                'message': _("Todos seus projetos estão aqui. Você pode pesquisar, renomear ou excluir a qualquer momento."),
                'position': Gtk.PositionType.RIGHT,
            },
            {
                'target': 'pomodoro_button',
                'title': _("Temporizador Pomodoro"),
                'message': _("Mantenha o foco com o Pomodoro integrado. Perfeito para sessões de escrita"),
                'position': Gtk.PositionType.BOTTOM,
            },
            {
                'target': 'cloud_button',
                'title': _("Sincronização em Nuvem"),
                'message': _("Sincronize seus projetos com o Dropbox"),
                'position': Gtk.PositionType.BOTTOM,
            },
            {
                'target': 'ai_button',
                'title': _("Assistente de IA"),
                'message': _("Use IA para revisar seu texto. Configure em Preferências. Leia a wiki para ajuda."),
                'position': Gtk.PositionType.BOTTOM,
            },
            {
                'target': 'save_button',
                'title': _("Salve Seu Trabalho"),
                'message': _("Não se preocupe! O salvamento automático é padrão, mas você pode salvar manualmente aqui."),
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
            skip_button = Gtk.Button.new_with_label(_("Pular Tour"))
            skip_button.connect('clicked', lambda b: self.end_tour())
            buttons_box.append(skip_button)

        # Previous button (if not first step)
        if step_index > 0:
            prev_button = Gtk.Button.new_with_label(_("Anterior"))
            prev_button.connect('clicked', lambda b: self.show_step(step_index - 1))
            buttons_box.append(prev_button)

        # Next/Finish button
        if step_index < len(self.steps) - 1:
            next_button = Gtk.Button.new_with_label(_("Próximo"))
            next_button.add_css_class("suggested-action")
            next_button.connect('clicked', lambda b: self.show_step(step_index + 1))
        else:
            next_button = Gtk.Button.new_with_label(_("Concluir"))
            next_button.add_css_class("suggested-action")
            next_button.connect('clicked', lambda b: self.end_tour())

        buttons_box.append(next_button)
        content_box.append(buttons_box)

        self.popover.set_child(content_box)

        # If target widget is disabled, use window as parent
        if target_widget.get_sensitive():
            # Widget is enabled - use it as parent (normal behavior)
            self.popover.set_parent(target_widget)
        else:
            # Widget is DISABLED - use main window as parent
            self.popover.set_parent(self.main_window)
            self.popover.set_pointing_to(self._get_widget_rect(target_widget))

        self.popover.popup()

    def _get_widget_rect(self, widget):
        """Get the rectangle position of a widget relative to window"""
        # Get widget size
        width = widget.get_width()
        height = widget.get_height()

        # Get widget position relative to window
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

class ReorderableParagraphRow(Gtk.Box):
    """
    Wrapper around ParagraphEditor that implements Planify-style 
    fluid drag and drop with expanding landing pads.
    """
    __gtype_name__ = 'TacReorderableParagraphRow'
    
    # Forwards the reordering signal coming from the drop target
    __gsignals__ = {
        'paragraph-reorder': (GObject.SIGNAL_RUN_FIRST, None, (str, str, str)),
    }

    def __init__(self, editor_widget, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.editor = editor_widget
        
        self.paragraph = editor_widget.paragraph 
        
        # 1. Pad Superior
        self.top_drop_area = Gtk.Box(height_request=50) 
        self.top_drop_area.add_css_class("drop-landing-pad") 
        
        self.top_revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_UP)
        self.top_revealer.set_child(self.top_drop_area)
        self.top_revealer.set_transition_duration(200) 
        self.append(self.top_revealer)

        # 2. O Conteúdo (Editor)
        self.append(self.editor)

        # 3. Pad Inferior
        self.bottom_drop_area = Gtk.Box(height_request=50)
        self.bottom_drop_area.add_css_class("drop-landing-pad")
        
        self.bottom_revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.bottom_revealer.set_child(self.bottom_drop_area)
        self.bottom_revealer.set_transition_duration(200)
        self.append(self.bottom_revealer)

        # --- Controllers ---
        self._setup_drop_targets()
        self._setup_motion_controller()
        self._setup_css()

    def _setup_css(self):
        # Style
        css_provider = Gtk.CssProvider()
        css = """
        .drop-landing-pad {
            background-color: alpha(@accent_color, 0.1);
            border: 2px dashed @accent_color;
            border-radius: 6px;
            margin: 4px 12px;
        }
        """
        try:
            css_provider.load_from_data(css.encode())
            display = Gdk.Display.get_default()
            Gtk.StyleContext.add_provider_for_display(display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except:
            pass

    def _setup_drop_targets(self):
        """Configura os DropTargets nos Pads (e não no widget principal)"""
        
        # Target Superior
        target_top = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        target_top.connect('drop', self._on_drop_top)
        self.top_drop_area.add_controller(target_top)

        # Target Inferior
        target_bottom = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        target_bottom.connect('drop', self._on_drop_bottom)
        self.bottom_drop_area.add_controller(target_bottom)

    def _setup_motion_controller(self):
        """Detecta onde o mouse está para abrir o revealer correto"""
        motion_ctrl = Gtk.DropControllerMotion()
        motion_ctrl.connect('motion', self._on_hover_motion)
        motion_ctrl.connect('leave', self._on_hover_leave)
        self.add_controller(motion_ctrl)

    def _on_hover_motion(self, controller, x, y):
        global _CURRENT_DRAG_ID
        
        if _CURRENT_DRAG_ID == self.paragraph.id:
            return

        height = self.get_height()
        is_top_half = y < (height / 2)

        # Planify logic:
        if self.top_revealer.get_reveal_child() != is_top_half:
            self.top_revealer.set_reveal_child(is_top_half)
            
        if self.bottom_revealer.get_reveal_child() != (not is_top_half):
            self.bottom_revealer.set_reveal_child(not is_top_half)

    def _on_hover_leave(self, controller):
        """Fecha tudo ao sair"""
        self.top_revealer.set_reveal_child(False)
        self.bottom_revealer.set_reveal_child(False)

    def _on_drop_top(self, target, value, x, y):
        return self._handle_drop("before")

    def _on_drop_bottom(self, target, value, x, y):
        return self._handle_drop("after")

    def _handle_drop(self, position):
        global _CURRENT_DRAG_ID
        
        # Clean visual
        self._on_hover_leave(None)

        dragged_id = _CURRENT_DRAG_ID
        target_id = self.paragraph.id

        if not dragged_id or dragged_id == target_id:
            return False
            
        # Sends the signal to the MainWindow to handle data and UI logic
        self.emit('paragraph-reorder', dragged_id, target_id, position)
        return True
