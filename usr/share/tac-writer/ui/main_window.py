"""
TAC Main Window
Main application window using GTK4 and libadwaita
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from typing import Dict, List, Optional
import re

from gi.repository import Gtk, Adw, Gio, GLib, Gdk

from core.models import Project, ParagraphType
from core.services import ProjectManager, ExportService
from core.config import Config
from core.ai_assistant import WritingAiAssistant
from utils.helpers import FormatHelper
from utils.i18n import _
from .components import WelcomeView, ParagraphEditor, ProjectListWidget, SpellCheckHelper, PomodoroTimer, FirstRunTour, ReorderableParagraphRow
from .dialogs import NewProjectDialog, ExportDialog, PreferencesDialog, AboutDialog, WelcomeDialog, BackupManagerDialog, ImageDialog, CloudSyncDialog, ReferencesDialog



class MainWindow(Adw.ApplicationWindow):
    """Main application window"""

    __gtype_name__ = 'TacMainWindow'

    def __init__(self, application, project_manager: ProjectManager, config: Config, **kwargs):
        super().__init__(application=application, **kwargs)

        # Track pdf dialog
        self.pdf_loading_dialog = None

        # Store references
        self.project_manager = project_manager
        self.config = config
        self.export_service = ExportService()
        self.current_project: Project = None

        # Shared spell check helper
        self.spell_helper = SpellCheckHelper(config) if config else None

        # Pomodoro Timer
        self.pomodoro_dialog = None
        self.timer = PomodoroTimer()

        # AI assistant
        self.ai_assistant = WritingAiAssistant(self, self.config)
        self._ai_context_target: Optional[dict] = None

        # Search state
        self.search_entry: Optional[Gtk.SearchEntry] = None
        self.search_next_button: Optional[Gtk.Button] = None
        self.search_query: str = ""
        self._search_state = {'paragraph_index': -1, 'offset': -1}

        # Scroll and loading state
        self._is_loading_paragraphs = False
        self._pending_scroll_to_bottom = False
        self._preserved_scroll_position = None

        # Auto-save timer tracking
        self.auto_save_timeout_id = None
        self.auto_save_pending = False

        # UI components
        self.header_bar = None
        self.toast_overlay = None
        self.main_stack = None
        self.welcome_view = None
        self.editor_view = None
        self.sidebar = None
        self.paned = None

        # Setup window
        self._setup_window()
        self._setup_ui()
        self._setup_actions()
        self._setup_keyboard_shortcuts()
        self._restore_window_state()

        # Show welcome dialog if enabled
        GLib.timeout_add(500, self._maybe_show_welcome_dialog)

    def _setup_window(self):
        """Setup basic window properties"""
        self.set_title(_("TAC - Técnica da Argumentação Contínua"))
        self.set_icon_name("tac-writer")

        # Set default size
        default_width = self.config.get('window_width', 1200)
        default_height = self.config.get('window_height', 800)
        self.set_default_size(default_width, default_height)

        # Connect window state events
        self.connect('close-request', self._on_close_request)
        self.connect('notify::maximized', self._on_window_state_changed)

    def _setup_ui(self):
        """Setup the user interface"""
        # Toast overlay for notifications
        self.toast_overlay = Adw.ToastOverlay()

        # Create overlay for tour (with dark background)
        self.tour_overlay_container = Gtk.Overlay()
        self.set_content(self.tour_overlay_container)

        # Add toast overlay as child
        self.tour_overlay_container.set_child(self.toast_overlay)

        # Create dark overlay for tour (initially hidden)
        self.tour_dark_overlay = Gtk.DrawingArea()
        self.tour_dark_overlay.set_vexpand(True)
        self.tour_dark_overlay.set_hexpand(True)
        self.tour_dark_overlay.add_css_class('dark-overlay')
        self.tour_dark_overlay.set_visible(False)
        self.tour_dark_overlay.set_can_target(False)
        self.tour_overlay_container.add_overlay(self.tour_dark_overlay)

        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(main_box)

        # Header bar
        self._setup_header_bar()
        main_box.append(self.header_bar)

        # Main content area with sidebar
        self._setup_content_area(main_box)

        # Show welcome view initially
        self._show_welcome_view()

    def _setup_header_bar(self):
        """Setup the header bar"""
        self.header_bar = Adw.HeaderBar()
        
        # Prevent to show tac icon in KDE Plasma
        self.header_bar.set_show_start_title_buttons(False)

        # Title widget
        title_widget = Adw.WindowTitle()
        title_widget.set_title("TAC")
        self.header_bar.set_title_widget(title_widget)

        # Sidebar toggle button
        self.sidebar_toggle_button = Gtk.ToggleButton()
        self.sidebar_toggle_button.set_icon_name('tac-sidebar-show-symbolic')
        self.sidebar_toggle_button.set_tooltip_text(_("Mostrar/Ocultar Projetos (F9)"))
        self.sidebar_toggle_button.set_active(True)
        self.sidebar_toggle_button.connect('toggled', self._on_sidebar_toggle)
        self.header_bar.pack_start(self.sidebar_toggle_button)

        # Left side buttons
        self.new_project_button = Gtk.MenuButton()
        self.new_project_button.set_icon_name('tac-document-new-symbolic')
        self.new_project_button.set_tooltip_text(_("Novo Projeto"))
        
        new_project_menu=Gio.Menu()

        new_project_menu.append(_("Ensaio Padrão (Humanas/Biológicas)"), "win.new_project('standard')")
        new_project_menu.append(_("Ensaio LaTeX (Exatas)"), "win.new_project('latex')")
        new_project_menu.append(_("Ensaio T.I. (Tecnologia/Código)"), "win.new_project('it_essay')")

        self.new_project_button.set_menu_model(new_project_menu)
        self.header_bar.pack_start(self.new_project_button)

        # Pomodoro Timer Button
        self.pomodoro_button = Gtk.Button()
        self.pomodoro_button.set_icon_name('tac-alarm-symbolic')
        self.pomodoro_button.set_tooltip_text(_("Temporizador Pomodoro"))
        self.pomodoro_button.connect('clicked', self._on_pomodoro_clicked)
        self.pomodoro_button.set_sensitive(False)
        self.header_bar.pack_start(self.pomodoro_button)

        # Cloud Sync Button (Dropbox)
        self.cloud_button = Gtk.Button()
        self.cloud_button.set_icon_name('tac-cloud-symbolic')
        self.cloud_button.set_tooltip_text(_("Sincronização com Dropbox"))
        self.cloud_button.connect('clicked', self._on_cloud_sync_clicked)
        self.cloud_button.set_sensitive(True) 
        self.header_bar.pack_start(self.cloud_button)

        # Referencies catalogy for quotes
        self.references_button = Gtk.Button()
        self.references_button.set_icon_name('tac-accessories-dictionary-symbolic')
        self.references_button.set_tooltip_text(_("Referências para Citação"))
        self.references_button.connect('clicked', self._on_references_clicked)
        self.references_button.set_sensitive(False) 
        self.header_bar.pack_start(self.references_button)


        # Right side buttons
        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name('tac-open-menu-symbolic')
        menu_button.set_tooltip_text(_("Menu Principal"))
        self._setup_menu(menu_button)
        self.header_bar.pack_end(menu_button)

        # Save button
        save_button = Gtk.Button()
        save_button.set_icon_name('tac-document-save-symbolic')
        save_button.set_tooltip_text(_("Salvar Projeto (Ctrl+S)"))
        save_button.set_action_name("app.save_project")
        save_button.set_sensitive(False)
        self.header_bar.pack_end(save_button)
        self.save_button = save_button

        # AI assistant button
        self.ai_button = Gtk.Button()
        self.ai_button.set_icon_name('tac-document-properties-symbolic')
        self.ai_button.set_tooltip_text(_("Revisão de texto por IA (Ctrl+Shift+I)"))
        self.ai_button.connect('clicked', self._on_ai_pdf_clicked)
        self.header_bar.pack_end(self.ai_button)

        # Search box
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(_("Pesquisar..."))
        self.search_entry.set_width_chars(18)
        self.search_entry.connect("search-changed", self._on_search_text_changed)
        self.search_entry.connect("activate", self._on_search_activate)
        search_box.append(self.search_entry)

        self.search_next_button = Gtk.Button.new_from_icon_name('tac-go-down-symbolic')
        self.search_next_button.set_tooltip_text(_("Localizar próxima ocorrência"))
        self.search_next_button.add_css_class("flat")
        self.search_next_button.connect("clicked", self._on_search_next_clicked)
        search_box.append(self.search_next_button)

        self.header_bar.pack_end(search_box)

        

    def _setup_menu(self, menu_button):
        """Setup the main menu"""
        menu_model = Gio.Menu()

        # File section
        file_section = Gio.Menu()
        file_section.append(_("Exportar Projeto..."), "app.export_project")
        file_section.append(_("Gerenciador de Backups..."), "win.backup_manager")
        menu_model.append_section(None, file_section)

        # Edit section
        edit_section = Gio.Menu()
        edit_section.append(_("Desfazer"), "win.undo")
        edit_section.append(_("Refazer"), "win.redo")
        menu_model.append_section(None, edit_section)

        # Preferences section
        preferences_section = Gio.Menu()
        preferences_section.append(_("Preferências"), "app.preferences")
        menu_model.append_section(None, preferences_section)

        # Help section
        help_section = Gio.Menu()
        help_section.append(_("Guia de Boas-vindas"), "win.show_welcome")
        help_section.append(_("Revisão de texto por IA"), "app.ai_assistant")
        help_section.append(_("Sobre o TAC"), "app.about")
        menu_model.append_section(None, help_section)

        menu_button.set_menu_model(menu_model)

    def _setup_content_area(self, main_box):
        """Setup the main content area with resizable sidebar"""
        # Paned for resizable sidebar
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.set_shrink_start_child(False)
        self.paned.set_shrink_end_child(False)
        self.paned.set_resize_start_child(False)
        self.paned.set_resize_end_child(True)
        self.paned.set_wide_handle(True)
        self.paned.set_vexpand(True)
        main_box.append(self.paned)

        # Sidebar
        self._setup_sidebar()

        # Main content stack
        self.main_stack = Adw.ViewStack()
        self.main_stack.set_vexpand(True)
        self.main_stack.set_hexpand(True)
        self.paned.set_end_child(self.main_stack)

    def _setup_sidebar(self):
        """Setup the sidebar"""
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.set_size_request(200, -1)
        sidebar_box.add_css_class("sidebar")

        # Sidebar header
        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_show_end_title_buttons(False)
        # Prevent to show tac icon in KDE Plasma
        sidebar_header.set_show_start_title_buttons(False)
        sidebar_title = Adw.WindowTitle()
        sidebar_title.set_title(_("Projetos"))
        sidebar_header.set_title_widget(sidebar_title)
        sidebar_box.append(sidebar_header)

        # Project list
        self.project_list = ProjectListWidget(self.project_manager)
        self.project_list.connect('project-selected', self._on_project_selected)
        sidebar_box.append(self.project_list)

        # Add to paned as start (left) child
        self.paned.set_start_child(sidebar_box)

        # Restore saved position or use default
        saved_pos = self.config.get('sidebar_width', 300)
        self.paned.set_position(saved_pos)

        self.sidebar = sidebar_box

    def _setup_actions(self):
        """Setup window-specific actions"""
        actions = [
            ('toggle_sidebar', self._action_toggle_sidebar),
            ('toggle_fullscreen', self._action_toggle_fullscreen),
            ('add_paragraph', self._action_add_paragraph, 's'),
            ('insert_image', self._action_insert_image),
            ('show_welcome', self._action_show_welcome),
            ('undo', self._action_undo),
            ('redo', self._action_redo),
            ('backup_manager', self._action_backup_manager),
            ('new_project', self._action_new_project, 's'),
        ]

        for action_data in actions:
            if len(action_data) == 3:
                action = Gio.SimpleAction.new(action_data[0], GLib.VariantType.new(action_data[2]))
            else:
                action = Gio.SimpleAction.new(action_data[0], None)
            action.connect('activate', action_data[1])
            self.add_action(action)

    def _setup_keyboard_shortcuts(self):
        """Setup window-specific shortcuts"""
        shortcut_controller = Gtk.ShortcutController()
        
        # Undo
        undo_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Ctrl>z"),
            Gtk.NamedAction.new("win.undo")
        )
        shortcut_controller.add_shortcut(undo_shortcut)
        
        # Redo
        redo_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Ctrl><Shift>z"),
            Gtk.NamedAction.new("win.redo")
        )
        shortcut_controller.add_shortcut(redo_shortcut)
        
        # Insert Image
        insert_image_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Ctrl><Alt>i"),
            Gtk.NamedAction.new("win.insert_image")
        )
        shortcut_controller.add_shortcut(insert_image_shortcut)
        
        # Toggle Sidebar (F9)
        sidebar_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("F9"),
            Gtk.NamedAction.new("win.toggle_sidebar")
        )
        shortcut_controller.add_shortcut(sidebar_shortcut)

        # Toggle Fullscreen (F11)
        fullscreen_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("F11"),
            Gtk.NamedAction.new("win.toggle_fullscreen")
        )
        shortcut_controller.add_shortcut(fullscreen_shortcut)

        self.add_controller(shortcut_controller)

    def _show_welcome_view(self):
        """Show the welcome view"""
        if not self.welcome_view:
            self.welcome_view = WelcomeView()
            self.welcome_view.connect('create-project', self._on_create_project_from_welcome)
            self.welcome_view.connect('open-project', self._on_open_project_from_welcome)

        self.main_stack.add_named(self.welcome_view, "welcome")
        self.main_stack.set_visible_child_name("welcome")
        self._update_header_for_view("welcome")

    def _show_editor_view(self):
        """Show the editor view"""
        if not self.current_project:
            return

        # Remove existing editor view if any
        editor_page = self.main_stack.get_child_by_name("editor")
        if editor_page:
            self.main_stack.remove(editor_page)

        # Create new editor view
        self.editor_view = self._create_editor_view()
        self.main_stack.add_named(self.editor_view, "editor")
        self.main_stack.set_visible_child_name("editor")
        self._update_header_for_view("editor")
        self._reset_search_state()

    def _create_editor_view(self) -> Gtk.Widget:
        """Create the editor view for current project"""
        # Main editor container with overlay for floating buttons
        overlay = Gtk.Overlay()

        # Main editor container
        editor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Scrolled window for paragraphs
        self.editor_scrolled = Gtk.ScrolledWindow()
        self.editor_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.editor_scrolled.set_vexpand(True)

        # Paragraphs container
        self.paragraphs_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.paragraphs_box.set_spacing(12)
        self.paragraphs_box.set_margin_start(20)
        self.paragraphs_box.set_margin_end(20)
        self.paragraphs_box.set_margin_top(20)
        self.paragraphs_box.set_margin_bottom(20)

        self.editor_scrolled.set_child(self.paragraphs_box)
        editor_box.append(self.editor_scrolled)

        # Add existing paragraphs
        self._refresh_paragraphs()

        # Add paragraph toolbar
        toolbar = self._create_paragraph_toolbar()
        editor_box.append(toolbar)

        # Set main editor as overlay child
        overlay.set_child(editor_box)

        # Create floating navigation buttons
        nav_buttons = self._create_navigation_buttons()
        overlay.add_overlay(nav_buttons)

        return overlay

    def _create_paragraph_toolbar(self) -> Gtk.Widget:
        """Create toolbar for adding paragraphs"""
        toolbar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        toolbar_box.set_spacing(6)
        toolbar_box.set_margin_start(20)
        toolbar_box.set_margin_end(20)
        toolbar_box.set_margin_top(10)
        toolbar_box.set_margin_bottom(20)
        toolbar_box.add_css_class("toolbar")

        # Add paragraph menu button
        self.add_button = Gtk.MenuButton()
        self.add_button.set_label(_("Adicionar Parágrafo"))
        self.add_button.set_icon_name('tac-list-add-symbolic')
        self.add_button.add_css_class("suggested-action")

        # Create menu model
        menu_model = Gio.Menu()
        paragraph_types = [
            (_("Título 1"), ParagraphType.TITLE_1),
            (_("Título 2"), ParagraphType.TITLE_2),
            (_("Introdução"), ParagraphType.INTRODUCTION),
            (_("Argumento"), ParagraphType.ARGUMENT),
            (_("Retomada do Argumento"), ParagraphType.ARGUMENT_RESUMPTION),
            (_("Citação"), ParagraphType.QUOTE),
            (_("Epígrafe"), ParagraphType.EPIGRAPH),
            (_("Conclusão"), ParagraphType.CONCLUSION),
        ]

        # Add LaTex condition
        if self.current_project and self.current_project.metadata.get('type') == 'latex':
            paragraph_types.append((_("Equação LaTeX"), ParagraphType.LATEX))

        # Add Code condition (IT Essay)
        if self.current_project and self.current_project.metadata.get('type') == 'it_essay':
            paragraph_types.append((_("Bloco de Código"), ParagraphType.CODE))
            
        for label, ptype in paragraph_types:
            menu_model.append(label, f"win.add_paragraph('{ptype.value}')")

        self.add_button.set_menu_model(menu_model)
        toolbar_box.append(self.add_button)
        
        # Add image button
        image_button = Gtk.Button()
        image_button.set_label(_("Inserir Imagem"))
        image_button.set_icon_name('insert-image-symbolic')
        image_button.set_tooltip_text(_("Inserir Imagem (Ctrl+Alt+I)"))
        image_button.set_action_name('win.insert_image')
        toolbar_box.append(image_button)

        return toolbar_box
    
    def _create_navigation_buttons(self) -> Gtk.Widget:
        """Create floating navigation buttons for quick scrolling"""
        # Container for buttons positioned at bottom right
        nav_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        nav_container.set_halign(Gtk.Align.END)
        nav_container.set_valign(Gtk.Align.END)
        nav_container.set_margin_end(20)
        nav_container.set_margin_bottom(20)

        # Go to top button
        top_button = Gtk.Button()
        top_button.set_icon_name('tac-go-up-symbolic')
        top_button.set_tooltip_text(_("Ir para o início"))
        top_button.add_css_class("circular")
        top_button.add_css_class("flat")
        top_button.set_size_request(40, 40)
        top_button.connect('clicked', self._on_scroll_to_top)
        nav_container.append(top_button)

        # Go to bottom button
        bottom_button = Gtk.Button()
        bottom_button.set_icon_name('tac-go-down-symbolic')
        bottom_button.set_tooltip_text(_("Ir para o fim"))
        bottom_button.add_css_class("circular")
        bottom_button.add_css_class("flat")
        bottom_button.set_size_request(40, 40)
        bottom_button.connect('clicked', self._on_scroll_to_bottom)
        nav_container.append(bottom_button)

        return nav_container

    def _on_scroll_to_top(self, button):
        """Scroll to the top of the project"""
        if hasattr(self, 'editor_scrolled'):
            adjustment = self.editor_scrolled.get_vadjustment()
            adjustment.set_value(adjustment.get_lower())

    def _on_scroll_to_bottom(self, button):
        """Scroll to the bottom of the project"""
        # If loading, scroll after
        if self._is_loading_paragraphs:
            self._pending_scroll_to_bottom = True
            # Optional: Show a quick warning or change the cursor
            self._show_toast(_("Carregando restante do documento..."), Adw.ToastPriority.LOW)
            
            # Force scroll to current point immediately too
            if hasattr(self, 'editor_scrolled'):
                adjustment = self.editor_scrolled.get_vadjustment()
                adjustment.set_value(adjustment.get_upper())
            return

        # Default behavior if everything has already loaded
        if hasattr(self, 'editor_scrolled'):
            adjustment = self.editor_scrolled.get_vadjustment()
            adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size())

    def _refresh_paragraphs(self):
        """Refresh paragraphs display with optimized loading"""
        if not self.current_project:
            return
    
        # Save scroll position before any changes
        if hasattr(self, 'editor_scrolled') and self.editor_scrolled:
            vadj = self.editor_scrolled.get_vadjustment()
            if vadj.get_value() > 0:
                self._preserved_scroll_position = vadj.get_value()
            else:
                self._preserved_scroll_position = None

        # Cleans up old widgets that are no longer in the project
        existing_widgets = {}
        child = self.paragraphs_box.get_first_child()
        while child:
            if hasattr(child, 'paragraph') and hasattr(child.paragraph, 'id'):
                existing_widgets[child.paragraph.id] = child
            child = child.get_next_sibling()

        current_paragraph_ids = {p.id for p in self.current_project.paragraphs}
    
        for paragraph_id, widget in list(existing_widgets.items()):
            if paragraph_id not in current_paragraph_ids:
                self.paragraphs_box.remove(widget)
                del existing_widgets[paragraph_id]
    
        # Removes all from view to reorder/reinsert correctly
        child = self.paragraphs_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.paragraphs_box.remove(child)
            child = next_child
    
        self._paragraphs_to_add = list(self.current_project.paragraphs)
        self._existing_widgets = existing_widgets
        
        # Reset control flags
        self._is_loading_paragraphs = True
        self._pending_scroll_to_bottom = False

        # Start batch processing
        GLib.idle_add(self._process_paragraph_batch)

    def _process_paragraph_batch(self):
        """Process a batch of paragraphs for asynchronous loading"""
        # PERFORMANCE SETUP
        BATCH_SIZE = 10 
        
        count = 0
        while self._paragraphs_to_add and count < BATCH_SIZE:
            paragraph = self._paragraphs_to_add.pop(0)
            
            # Widget creation/reuse logic
            row_widget = None
            if paragraph.id in self._existing_widgets:
                row_widget = self._existing_widgets[paragraph.id]
            else:
                editor_widget = None 

                # Use 'editor_widget' instead of 'widget
                if paragraph.type == ParagraphType.IMAGE:
                    editor_widget = self._create_image_widget(paragraph)
                    # Ensures image widget has paragraph reference
                    if not hasattr(editor_widget, 'paragraph'):
                        editor_widget.paragraph = paragraph
                else:
                    editor_widget = ParagraphEditor(paragraph, config=self.config)
                    editor_widget.connect('content-changed', self._on_paragraph_changed)
                    editor_widget.connect('remove-requested', self._on_paragraph_remove_requested)

                # Now editor_widget is no longer None
                from ui.components import ReorderableParagraphRow 
                row_widget = ReorderableParagraphRow(editor_widget)

                # Connect Row Signal 
                row_widget.connect('paragraph-reorder', self._on_paragraph_reorder)
                
                self._existing_widgets[paragraph.id] = row_widget
            
            self.paragraphs_box.append(row_widget)
            count += 1

        # TERMINATION CHECK
        if not self._paragraphs_to_add:
            self._is_loading_paragraphs = False
            
            # FIX: Restore scrolling ONLY when everything is loaded
            if self._preserved_scroll_position is not None:
                GLib.idle_add(self._restore_scroll_position, priority=GLib.PRIORITY_LOW)
            
            elif self._pending_scroll_to_bottom:
                GLib.idle_add(self._execute_pending_scroll)
                self._pending_scroll_to_bottom = False
                
            return False

        return True

    def _restore_scroll_position(self):
        """Helper to restore scroll position after refresh"""
        if hasattr(self, 'editor_scrolled') and self._preserved_scroll_position is not None:
            adj = self.editor_scrolled.get_vadjustment()
            adj.set_value(self._preserved_scroll_position)
            
            # Clears the preserved position to avoid unwanted future jumps
            self._preserved_scroll_position = None
        return False

    def _execute_pending_scroll(self):
        """Helper to execute the final scroll after loading is complete"""
        if hasattr(self, 'editor_scrolled'):
            adjustment = self.editor_scrolled.get_vadjustment()
            adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size())
        return False    

    
    def _create_image_widget(self, paragraph):
        """Create widget to display an image paragraph"""
        from pathlib import Path
        
        metadata = paragraph.get_image_metadata()
        
        # Container principal
        image_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        image_container.set_margin_top(12)
        image_container.set_margin_bottom(12)
        image_container.paragraph = paragraph  
        
        if not metadata:
            # Fallback para dados inválidos
            error_label = Gtk.Label(label=_("⚠️ Erro: Dados de imagem inválidos"))
            error_label.add_css_class('error')
            image_container.append(error_label)
            # Adiciona toolbar mesmo com erro para permitir deletar
            image_container.append(self._create_image_toolbar(paragraph))
            return image_container
        
        # Configurar alinhamento
        alignment = metadata.get('alignment', 'center')
        if alignment == 'center':
            image_container.set_halign(Gtk.Align.CENTER)
        elif alignment == 'right':
            image_container.set_halign(Gtk.Align.END)
        else:
            image_container.set_halign(Gtk.Align.START)
        
        img_path_str = metadata.get('path', '')
        img_filename = metadata.get('filename', 'desconhecido.jpg')
        img_path = Path(img_path_str)

        # Display image logic
        if img_path.exists():
            # If image exist
            try:
                texture = Gdk.Texture.new_from_filename(str(img_path))
                
                picture = Gtk.Picture()
                picture.set_paintable(texture)
                picture.set_can_shrink(True)
                picture.set_content_fit(Gtk.ContentFit.CONTAIN)
                
                # Size
                original_size = metadata.get('original_size', (800, 600))
                if original_size[1] > 0:
                    aspect_ratio = original_size[0] / original_size[1]
                else:
                    aspect_ratio = 1.33
                
                thumbnail_height = 200
                thumbnail_width = int(thumbnail_height * aspect_ratio)
                picture.set_size_request(thumbnail_width, thumbnail_height)
                
                frame = Gtk.Frame()
                frame.set_child(picture)
                image_container.append(frame)
                
            except Exception as e:
                # Error load file
                self._create_error_placeholder(image_container, img_filename, str(e))
        else:
            # File not found (Sync from other computer)
            self._create_missing_placeholder(image_container, img_filename)

        # Subtitles, if it exist
        caption = metadata.get('caption', '')
        if caption:
            caption_label = Gtk.Label(label=caption)
            caption_label.add_css_class('caption')
            caption_label.add_css_class('dim-label')
            caption_label.set_wrap(True)
            caption_label.set_max_width_chars(60)
            caption_label.set_xalign(0.5)
            image_container.append(caption_label)
        
        # Edit button always visible
        toolbar = self._create_image_toolbar(paragraph)
        image_container.append(toolbar)
        
        return image_container

    def _create_missing_placeholder(self, container, filename):
        """Creates a UI element when image is missing"""
        frame = Gtk.Frame()
        frame.add_css_class("view")
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        
        # Warning icon
        icon = Gtk.Image.new_from_icon_name("tac-image-missing-symbolic")
        icon.set_pixel_size(48)
        icon.add_css_class("warning")
        box.append(icon)
        
        # Show explanation
        lbl = Gtk.Label()
        lbl.set_markup(f"<b>{_('Imagem não encontrada')}</b>")
        box.append(lbl)
        
        lbl_file = Gtk.Label(label=filename)
        lbl_file.add_css_class("dim-label")
        lbl_file.set_ellipsize(3)
        box.append(lbl_file)
        
        hint = Gtk.Label(label=_("Clique em editar abaixo para selecionar o arquivo localmente."))
        hint.add_css_class("caption")
        hint.set_wrap(True)
        hint.set_max_width_chars(40)
        box.append(hint)
        
        frame.set_child(box)
        container.append(frame)

    def _create_error_placeholder(self, container, filename, error_msg):
        """Creates a UI element when image fails to load"""
        error_label = Gtk.Label(
            label=_("⚠️ Erro ao carregar: {}\n{}").format(filename, error_msg)
        )
        error_label.add_css_class('error')
        container.append(error_label)
    
    def _create_image_toolbar(self, paragraph):
        """Create toolbar with actions for image paragraph"""
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_halign(Gtk.Align.CENTER)
        toolbar.set_margin_top(6)

        # Edit Image button
        edit_btn = Gtk.Button()
        edit_btn.set_icon_name('tac-edit-image-symbolic')
        edit_btn.set_tooltip_text(_("Editar Imagem"))
        edit_btn.connect('clicked', lambda b: self._on_edit_image(paragraph))
        toolbar.append(edit_btn)

        # Remove button
        remove_btn = Gtk.Button()
        remove_btn.set_icon_name('tac-user-trash-symbolic')
        remove_btn.set_tooltip_text(_("Remover Imagem"))
        remove_btn.add_css_class('destructive-action')
        remove_btn.connect('clicked', lambda b: self._on_remove_image(paragraph))
        toolbar.append(remove_btn)

        return toolbar
    
    def _on_remove_image(self, paragraph):
        """Handle image removal"""
        if not self.current_project:
            return
        
        # Show confirmation dialog
        dialog = Adw.MessageDialog.new(
            self,
            _("Remover Imagem?"),
            _("Tem certeza que deseja remover esta imagem do documento?")
        )
        
        dialog.add_response("cancel", _("Cancelar"))
        dialog.add_response("remove", _("Remover"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        
        def on_response(d, response):
            if response == "remove":
                try:
                    # Remove from project
                    self.current_project.paragraphs.remove(paragraph)
                    self.current_project.update_paragraph_order()
                    
                    # Save
                    self.project_manager.save_project(self.current_project)
                    
                    # Refresh UI
                    self._refresh_paragraphs()
                    self._update_header_for_view("editor")
                    
                    self._show_toast(_("Imagem removida"))
                except Exception as e:
                    print(f"Error removing image: {e}")
                    self._show_toast(_("Erro ao remover imagem"), Adw.ToastPriority.HIGH)
            d.destroy()
        
        dialog.connect('response', on_response)
        dialog.present()

    def _on_edit_image(self, paragraph):
        """Handle image editing"""
        if not self.current_project:
            return

        from ui.dialogs import ImageDialog

        # Get paragraph index
        try:
            para_index = self.current_project.paragraphs.index(paragraph)
        except ValueError:
            print("Error: Paragraph not found in project")
            return

        # Open ImageDialog in edit mode
        dialog = ImageDialog(
            parent=self,
            project=self.current_project,
            insert_after_index=para_index,
            edit_paragraph=paragraph
        )
        dialog.connect('image-updated', self._on_image_updated)
        dialog.present()

    def _on_image_updated(self, dialog, data):
        """Handle image update from dialog"""
        updated_paragraph = data.get('paragraph')
        original_paragraph = data.get('original_paragraph')

        if not updated_paragraph or not original_paragraph:
            return

        try:
            # Find and replace the original paragraph
            index = self.current_project.paragraphs.index(original_paragraph)
            self.current_project.paragraphs[index] = updated_paragraph

            # Update order
            updated_paragraph.order = original_paragraph.order

            # Save project
            self.project_manager.save_project(self.current_project)

            # Refresh UI
            self._refresh_paragraphs()
            self._update_header_for_view("editor")

            self._show_toast(_("Imagem atualizada"))
        except (ValueError, Exception) as e:
            print(f"Error updating image: {e}")
            import traceback
            traceback.print_exc()
            self._show_toast(_("Erro ao atualizar imagem"), Adw.ToastPriority.HIGH)

    def _get_focused_text_view(self):
        """Get the currently focused TextView widget"""
        focus_widget = self.get_focus()
        
        current_widget = focus_widget
        while current_widget:
            if isinstance(current_widget, Gtk.TextView):
                return current_widget
            current_widget = current_widget.get_parent()
        
        if hasattr(self, 'paragraphs_box'):
            child = self.paragraphs_box.get_first_child()
            while child:
                if hasattr(child, 'text_view') and isinstance(child.text_view, Gtk.TextView):
                    return child.text_view
                child = child.get_next_sibling()
        
        return None

    def _get_paragraph_editor_from_text_view(self, text_view):
        """Get the ParagraphEditor that contains the given TextView"""
        if not text_view:
            return None
            
        current_widget = text_view
        while current_widget:
            if hasattr(current_widget, '__gtype_name__') and current_widget.__gtype_name__ == 'TacParagraphEditor':
                return current_widget
            current_widget = current_widget.get_parent()
        
        return None

    def _action_undo(self, action, param):
        """Handle global undo action"""
        focused_text_view = self._get_focused_text_view()
        if focused_text_view:
            buffer = focused_text_view.get_buffer()
            if buffer and hasattr(buffer, 'get_can_undo'):
                if buffer.get_can_undo():
                    buffer.undo()
                    self._show_toast(_("Desfazer"))
                    return
            
            # Fallback: Try Ctrl+Z key simulation
            try:
                focused_text_view.emit('key-pressed', Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK, 0)
                return
            except:
                pass
        
        self._show_toast(_("Nada para desfazer"))

    def _action_redo(self, action, param):
        """Handle global redo action"""
        focused_text_view = self._get_focused_text_view()
        if focused_text_view:
            buffer = focused_text_view.get_buffer()
            if buffer and hasattr(buffer, 'get_can_redo'):
                if buffer.get_can_redo():
                    buffer.redo()
                    self._show_toast(_("Refazer"))
                    return
            
            # Fallback: Try Ctrl+Shift+Z key simulation
            try:
                focused_text_view.emit('key-pressed', Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, 0)
                return
            except:
                pass
        
        self._show_toast(_("Nada para refazer"))

    # Event handlers
    def _on_create_project_from_welcome(self, widget, template_name):
        """Handle create project from welcome view"""
        self.show_new_project_dialog(project_type=template_name)

    def _on_open_project_from_welcome(self, widget, project_info):
        """Handle open project from welcome view"""
        self._load_project(project_info['id'])

    def _on_project_selected(self, widget, project_info):
        """Handle project selection from sidebar"""
        self._load_project(project_info['id'])

    def _on_paragraph_changed(self, paragraph_editor):
        """Handle paragraph content changes"""
        if self.current_project:
            self.current_project._update_modified_time()
            self._update_header_for_view("editor")
            # Update sidebar project list in real-time with current statistics
            current_stats = self.current_project.get_statistics()
            self.project_list.update_project_statistics(self.current_project.id, current_stats)
            
            # Schedule auto-save if enabled
            self._schedule_auto_save()

    def _on_paragraph_remove_requested(self, paragraph_editor, paragraph_id):
        """Handle paragraph removal request"""
        if self.current_project:
            self.current_project.remove_paragraph(paragraph_id)
            self._refresh_paragraphs()
            self._update_header_for_view("editor")
            # Update sidebar project list in real-time with current statistics
            current_stats = self.current_project.get_statistics()
            self.project_list.update_project_statistics(self.current_project.id, current_stats)

    def _on_paragraph_reorder(self, paragraph_editor, dragged_id, target_id, position):
        """
        Handle paragraph reordering manually manipulating the widgets.
        This prevents destroying the widgets during a Drop operation, 
        fixing the Gdk-WARNING runtime check failure.
        """
        if not self.current_project:
            return

        # 1. Atualizar o Modelo de Dados (Backend)
        dragged_paragraph = self.current_project.get_paragraph(dragged_id)
        target_paragraph = self.current_project.get_paragraph(target_id)

        if not dragged_paragraph or not target_paragraph:
            return
        
        current_idx = self.current_project.paragraphs.index(dragged_paragraph)
        target_idx = self.current_project.paragraphs.index(target_paragraph)

        # Logic to determine the new index
        if position == "after":
            new_idx = target_idx + 1 if current_idx < target_idx else target_idx
        else: 
            new_idx = target_idx if current_idx > target_idx else target_idx - 1
            
            if new_idx < 0: new_idx = 0

        # Move no backend
        self.current_project.move_paragraph(dragged_id, new_idx)
        
        # 2. Update the Interface
        dragged_widget = self._existing_widgets.get(dragged_id)
        target_widget = self._existing_widgets.get(target_id)
        
        if dragged_widget and target_widget:
                        
            sibling_to_insert_after = None
            
            if position == "after":
                sibling_to_insert_after = target_widget
            else:
                sibling_to_insert_after = target_widget.get_prev_sibling()

            if sibling_to_insert_after != dragged_widget:
                self.paragraphs_box.reorder_child_after(dragged_widget, sibling_to_insert_after)

            # Atualiza cabeçalho (contador de palavras, etc)
            self._update_header_for_view("editor")
        else:
            # Fallback if something goes wrong
            self._refresh_paragraphs()

    def _on_close_request(self, window):
        """Handle window close request"""
        # Cancel any pending auto-save timer
        if self.auto_save_timeout_id is not None:
            GLib.source_remove(self.auto_save_timeout_id)
            self.auto_save_timeout_id = None
        
        # If there's a pending auto-save, perform final save now
        if self.auto_save_pending and self.current_project:
            self.project_manager.save_project(self.current_project)
        
        # Save window state
        self._save_window_state()
        
        # Check if project needs saving (optional confirmation)
        if self.current_project and self.config.get('confirm_on_close', True):
            pass
        
        return False

    def _on_window_state_changed(self, window, pspec):
        """Handle window state changes"""
        self._save_window_state()

    def _on_pomodoro_clicked(self, button):
        """Handle pomodoro button click"""
        if not self.pomodoro_dialog:
            from ui.components import PomodoroDialog
            self.pomodoro_dialog = PomodoroDialog(self, self.timer)
        self.pomodoro_dialog.show_dialog()


    # Action handlers

    def _action_new_project(self, action, param):
        """Handle new project action with type parameter"""
        project_type = param.get_string() if param else "standard"
        self.show_new_project_dialog(project_type)

    def _action_toggle_sidebar(self, action, param):
        """Toggle sidebar visibility"""
        if hasattr(self, 'sidebar_toggle_button'):
            self.sidebar_toggle_button.set_active(not self.sidebar_toggle_button.get_active())

        if self.sidebar.get_visible():
            # Save position before hiding
            self._sidebar_last_position = self.paned.get_position()
            self.sidebar.set_visible(False)
            self.paned.set_position(0)
        else:
            self.sidebar.set_visible(True)
            pos = getattr(self, '_sidebar_last_position', 300)
            self.paned.set_position(pos)

    def _action_add_paragraph(self, action, param):
        """Add paragraph action"""
        if param:
            paragraph_type = ParagraphType(param.get_string())
            self._add_paragraph(paragraph_type)
    
    def _action_insert_image(self, action, param):
        """Handle insert image action"""
        if not self.current_project:
            self._show_toast(_("Nenhum projeto aberto"), Adw.ToastPriority.HIGH)
            return
        
        # Get current position (insert at end by default)
        current_index = len(self.current_project.paragraphs) - 1 if self.current_project.paragraphs else -1
        
        # Show image dialog
        dialog = ImageDialog(
            parent=self,
            project=self.current_project,
            insert_after_index=current_index
        )
        
        # Connect signal
        dialog.connect('image-added', self._on_image_added)
        
        # Present dialog
        dialog.present()

    def _action_show_welcome(self, action, param):
        """Handle show welcome action - show tour guide"""
        # Show welcome dialog first, then tour
        self.show_welcome_dialog()

        # Force the tour to show after welcome dialog is closed
        self.config.set('show_first_run_tutorial', True)
        
    def _action_backup_manager(self, action, param):
        """Handle backup manager action"""
        self.show_backup_manager_dialog()

    # Public methods called by application
    def show_new_project_dialog(self, project_type="strandard"):
        """Show new project dialog"""
        dialog = NewProjectDialog(self, project_type=project_type)
        dialog.connect('project-created', self._on_project_created)
        dialog.present()

    def show_open_project_dialog(self):
        """Show open project dialog"""
        file_chooser = Gtk.FileChooserNative.new(
            _("Abrir Projeto"),
            self,
            Gtk.FileChooserAction.OPEN,
            _("Abrir"),
            _("Cancelar")
        )

        projects_dir = self.project_manager.projects_dir
        if projects_dir.exists():
            file_chooser.set_current_folder(Gio.File.new_for_path(str(projects_dir)))

        filter_json = Gtk.FileFilter()
        filter_json.set_name(_("Projetos TAC (*.json)"))
        filter_json.add_pattern("*.json")
        file_chooser.add_filter(filter_json)

        filter_all = Gtk.FileFilter()
        filter_all.set_name(_("Todos os Arquivos"))
        filter_all.add_pattern("*")
        file_chooser.add_filter(filter_all)

        def on_response(dialog, response):
            if response == Gtk.ResponseType.ACCEPT:
                file = dialog.get_file()
                if file:
                    file_path = file.get_path()
                    project = self.project_manager.load_project(file_path)
                    if project:
                        self.current_project = project
                        self._show_editor_view()
                        self.project_list.refresh_projects()
                        self._show_toast(_("Projeto aberto: {}").format(project.name))
                    else:
                        self._show_toast(_("Falha ao abrir projeto"), Adw.ToastPriority.HIGH)
            dialog.destroy()

        file_chooser.connect('response', on_response)
        file_chooser.show()

    def save_current_project(self) -> bool:
        """Save the current project"""
        if not self.current_project:
            return False

        success = self.project_manager.save_project(self.current_project)
        if success:
            self._show_toast(_("Projeto salvo com sucesso"))
            self.project_list.refresh_projects()
            self.config.add_recent_project(self.current_project.id)
        else:
            self._show_toast(_("Falha ao salvar projeto"), Adw.ToastPriority.HIGH)

        return success
    
    def _schedule_auto_save(self):
        """Schedule an auto-save operation after a delay"""
        # Check if auto-save is enabled
        if not self.config.get('auto_save', True):
            return
        
        # Cancel existing timeout if any
        if self.auto_save_timeout_id is not None:
            GLib.source_remove(self.auto_save_timeout_id)
            self.auto_save_timeout_id = None
        
        # Get auto-save interval (default 120 seconds = 2 minutes)
        interval_seconds = self.config.get('auto_save_interval', 120)
        interval_ms = interval_seconds * 1000
        
        # Mark that auto-save is pending
        self.auto_save_pending = True
        
        # Schedule new auto-save
        self.auto_save_timeout_id = GLib.timeout_add(interval_ms, self._perform_auto_save)

    def _perform_auto_save(self):
        """Perform the actual auto-save operation"""
        # Reset timeout ID since this callback is executing
        self.auto_save_timeout_id = None
        self.auto_save_pending = False
        
        # Only save if there's a current project
        if not self.current_project:
            return False  # Don't repeat timeout
        
        # Perform save (this will trigger backup creation)
        success = self.project_manager.save_project(self.current_project)
        
        if success:
            # Silent save - no toast for auto-save to avoid interrupting user
            self.project_list.refresh_projects()
            self.config.add_recent_project(self.current_project.id)
            
            # Update header to show saved state (remove asterisk if you have one)
            self._update_header_for_view("editor")
        else:
            # Only show toast on failure
            self._show_toast(_("Salvamento automático falhou"), Adw.ToastPriority.HIGH)
        
        return False  

    def show_export_dialog(self):
        """Show export dialog"""
        if not self.current_project:
            self._show_toast(_("Nenhum projeto para exportar"), Adw.ToastPriority.HIGH)
            return

        dialog = ExportDialog(self, self.current_project, self.export_service)
        dialog.present()

    def show_preferences_dialog(self):
        """Show preferences dialog"""
        dialog = PreferencesDialog(self, self.config)
        dialog.present()

    def show_about_dialog(self):
        """Show about dialog"""
        dialog = AboutDialog(self)
        dialog.present()

    def open_ai_assistant_prompt(self):
        """Trigger the AI assistant prompt dialog."""
        self._on_ai_pdf_clicked(None)

    def show_welcome_dialog(self):
        """Show the welcome dialog"""
        dialog = WelcomeDialog(self, self.config)

        # Start tour when welcome dialog is closed (if first run)
        dialog.connect('dialog-closed', self._on_welcome_dialog_closed)

        dialog.present()

    def _on_welcome_dialog_closed(self, dialog):
        """Handle welcome dialog close - start tour if first run"""
        # Start tour after a short delay
        if self.config.get('show_first_run_tutorial', True):
            GLib.timeout_add(500, self._maybe_show_first_run_tutorial)

    def show_backup_manager_dialog(self):
        """Show the backup manager dialog"""
        dialog = BackupManagerDialog(self, self.project_manager)
        dialog.connect('database-imported', self._on_database_imported)
        dialog.present()

    def _on_database_imported(self, dialog):
        """Handle database import completion"""
        # Refresh project list
        self.project_list.refresh_projects()
        
        # Clear current project if one is open
        self.current_project = None
        
        # Show welcome view
        self._show_welcome_view()
        
        # Show success toast
        self._show_toast(_("Banco de dados importado com sucesso"), Adw.ToastPriority.HIGH)

    def _load_project(self, project_id: str):
        """Load a project by ID"""
        self._show_loading_state()

        try:
            project = self.project_manager.load_project(project_id)
            self._on_project_loaded(project, None)
        except Exception as e:
            self._on_project_loaded(None, str(e))

    def _add_paragraph(self, paragraph_type: ParagraphType):
        """Add a new paragraph"""
        if not self.current_project:
            return

        paragraph = self.current_project.add_paragraph(paragraph_type)

        paragraph_editor = ParagraphEditor(paragraph, config=self.config)
        paragraph_editor.connect('content-changed', self._on_paragraph_changed)
        paragraph_editor.connect('remove-requested', self._on_paragraph_remove_requested)
        
        # Create Wrapper
        from ui.components import ReorderableParagraphRow
        row_widget = ReorderableParagraphRow(paragraph_editor)
        row_widget.connect('paragraph-reorder', self._on_paragraph_reorder)

        self.paragraphs_box.append(row_widget)
        self._existing_widgets[paragraph.id] = row_widget 

        self._update_header_for_view("editor")
        current_stats = self.current_project.get_statistics()
        self.project_list.update_project_statistics(self.current_project.id, current_stats)

    def _on_project_created(self, dialog, project):
        """Handle new project creation"""
        self.current_project = project
        self._show_editor_view()

        self.project_list.refresh_projects()
        self._show_toast(_("Projeto criado: {}").format(project.name))

        # Show popover pointing to add button (only for first-time users)
        if self.config.get('show_post_creation_tip', True):
            GLib.timeout_add(500, self._show_post_creation_popover)

    def _show_post_creation_popover(self):
        """Show a popover pointing to the add paragraph button after project creation"""
        if not hasattr(self, 'add_button'):
            return False

        # Create popover
        popover = Gtk.Popover()
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.set_autohide(False)

        # Content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(20)
        content_box.set_margin_bottom(20)
        content_box.set_margin_start(20)
        content_box.set_margin_end(20)

        # Message
        message_label = Gtk.Label()
        message_label.set_text(_("Click here to start writing!\n\nAdd paragraphs to build your text."))
        message_label.set_wrap(True)
        message_label.set_max_width_chars(30)
        message_label.set_justify(Gtk.Justification.CENTER)
        content_box.append(message_label)

        # Got it button
        got_it_button = Gtk.Button.new_with_label(_("Entendi!"))
        got_it_button.add_css_class("suggested-action")
        got_it_button.set_halign(Gtk.Align.CENTER)

        def on_got_it_clicked(button):
            popover.popdown()
            popover.unparent()
            # Don't show this tip again
            self.config.set('show_post_creation_tip', False)
            self.config.save()

        got_it_button.connect('clicked', on_got_it_clicked)
        content_box.append(got_it_button)

        popover.set_child(content_box)
        popover.set_parent(self.add_button)
        popover.popup()

        return False  # Don't repeat timeout

    def _on_image_added(self, dialog, data):
        """Handle image added from ImageDialog"""
        if not self.current_project:
            return
        
        try:
            from datetime import datetime
            
            paragraph = data['paragraph']
            position = data['position']
            
            # Insert into project
            if position == 0:
                # Insert at beginning
                self.current_project.paragraphs.insert(0, paragraph)
            else:
                # Insert after specified paragraph (position is index + 1 from dropdown)
                self.current_project.paragraphs.insert(position, paragraph)
            
            # Update order
            self.current_project.update_paragraph_order()
            
            # Mark as modified
            self.current_project.modified_at = datetime.now()
            
            # Save project
            success = self.project_manager.save_project(self.current_project)
            
            if success:
                # Refresh UI
                self._refresh_paragraphs()
                
                # Update header
                self._update_header_for_view("editor")
                
                # Show success message
                self._show_toast(_("Imagem inserida com sucesso"))
                
                # Update statistics
                current_stats = self.current_project.get_statistics()
                self.project_list.update_project_statistics(self.current_project.id, current_stats)
            else:
                self._show_toast(_("Falha ao salvar projeto"), Adw.ToastPriority.HIGH)
        
        except Exception as e:
            print(f"Error adding image: {e}")
            import traceback
            traceback.print_exc()
            
            self._show_toast(_("Erro ao inserir imagem"), Adw.ToastPriority.HIGH)

    def _show_toast(self, message: str, priority=Adw.ToastPriority.NORMAL):
        """Show a toast notification"""
        toast = Adw.Toast.new(message)
        toast.set_priority(priority)
        self.toast_overlay.add_toast(toast)

    # AI assistant helpers
    def _on_ai_assistant_requested(self, *_args):
        if not self.ai_assistant:
            return

        if not self.config.get_ai_assistant_enabled():
            self._show_toast(
                _("Habilite o assistente de IA em Preferências ▸ Assistente de IA."),
                Adw.ToastPriority.HIGH,
            )
            return

        missing = self.ai_assistant.missing_configuration()
        if missing:
            labels = {
                "provider": _("Provedor"),
                "api_key": _("API key"),
            }
            readable = ", ".join(labels.get(item, item) for item in missing)
            self._show_toast(
                _("Configure {items} em Preferências ▸ Assistente de IA.").format(
                    items=readable
                ),
                Adw.ToastPriority.HIGH,
            )
            return

        context_text, context_label = self._collect_ai_context()
        self._show_ai_prompt_dialog(context_text, context_label)

        # Open selection window
    def _on_ai_pdf_clicked(self, btn):
        if not self.config.get_ai_assistant_enabled():
            self._show_toast(_("Habilite IA em Preferências. Chave de API necessária. Leia a Wiki em caso de dúvida."), Adw.ToastPriority.HIGH)
            return

        from ui.dialogs import AiPdfDialog
        self.pdf_loading_dialog = AiPdfDialog(self, self.ai_assistant)
        self.pdf_loading_dialog.present()

        # Add method to show result (called by ai_assistant)
    def show_ai_pdf_result_dialog(self, result_text: str):
        # 1. Close "Analysing" window if it's open
        if self.pdf_loading_dialog:
            self.pdf_loading_dialog.destroy()
            self.pdf_loading_dialog = None

        # 2. Open result window
        from ui.dialogs import AiResultDialog
        dialog = AiResultDialog(self, result_text)
        dialog.present()

        def handle_send() -> bool:
            start_iter = buffer.get_start_iter()
            end_iter = buffer.get_end_iter()
            text = buffer.get_text(start_iter, end_iter, True).strip()
            if not text:
                self._show_toast(_("Por favor adicione o texto a ser analisado."))
                return False

            context_value = context_text if include_context_switch.get_active() else None
            if self.ai_assistant.request_assistance(text, context_value):
                self._show_toast(_("O assistente de IA está processando sua solicitação..."))
                return True
            return False

        def on_response(dlg, response_id):
            if response_id == "send":
                if handle_send():
                    dlg.destroy()
                return
            dlg.destroy()

        

        def on_prompt_key_pressed(_controller, keyval, _keycode, state):
            if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and not (
                state & Gdk.ModifierType.SHIFT_MASK
            ):
                if handle_send():
                    dialog.destroy()
                return Gdk.EVENT_STOP
            return Gdk.EVENT_PROPAGATE

        

        dialog.present()

    def show_ai_response_dialog(
        self,
        reply: str,
        suggestions: List[Dict[str, str]],
    ) -> None:
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Assistente de IA"),
            body=_("Aqui está a sugestão do assistente."),
            close_response="close",
        )
        dialog.add_response("close", _("Fechar"))
        dialog.set_default_response("close")
        dialog.set_default_size(820, 640)

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )

        def add_section(title: str) -> Gtk.Box:
            frame = Gtk.Frame()
            frame.add_css_class("card")
            frame.set_hexpand(True)
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            inner.set_margin_top(12)
            inner.set_margin_bottom(12)
            inner.set_margin_start(16)
            inner.set_margin_end(16)
            heading = Gtk.Label(label=title, halign=Gtk.Align.START)
            heading.add_css_class("heading")
            inner.append(heading)
            frame.set_child(inner)
            content_box.append(frame)
            return inner

        reply_box = add_section(_("Resposta"))
        reply_view = Gtk.TextView(
            editable=False,
            cursor_visible=False,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            hexpand=True,
            vexpand=True,
        )
        reply_buffer = reply_view.get_buffer()
        reply_buffer.set_text(reply.strip())
        reply_scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        reply_scrolled.set_min_content_height(220)
        reply_scrolled.set_child(reply_view)
        reply_box.append(reply_scrolled)

        actions_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        actions_row.set_halign(Gtk.Align.START)

        copy_button = Gtk.Button(label=_("Copiar para área de transferência"))
        copy_button.connect("clicked", lambda *_a: self._copy_to_clipboard(reply))
        actions_row.append(copy_button)

        insert_button = Gtk.Button(label=_("Inserir no cursor"))
        insert_button.connect("clicked", lambda *_a: self._insert_text_into_editor(reply))
        actions_row.append(insert_button)

        reply_box.append(actions_row)

        apply_button = Gtk.Button(label=_("Aplicar correção"))
        apply_button.add_css_class("suggested-action")
        apply_button.set_sensitive(self._ai_context_target is not None)
        apply_button.connect(
            "clicked",
            lambda *_a: self._apply_ai_correction(reply),
        )
        actions_row.append(apply_button)

        if suggestions:
            suggestions_box = add_section(_("Sugestões adicionais"))
            suggestions_box.add_css_class("card")
            for suggestion in suggestions:
                text = suggestion.get("text", "").strip()
                if not text:
                    continue
                title = suggestion.get("title", "").strip()
                description = suggestion.get("description", "").strip()

                row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                row_box.set_margin_top(8)
                row_box.set_margin_bottom(8)
                row_box.set_margin_start(12)
                row_box.set_margin_end(12)

                if title:
                    heading = Gtk.Label(label=title, halign=Gtk.Align.START)
                    heading.add_css_class("heading")
                    row_box.append(heading)

                suggestion_label = Gtk.Label(
                    label=text,
                    halign=Gtk.Align.START,
                    wrap=True,
                )
                row_box.append(suggestion_label)

                if description:
                    desc_label = Gtk.Label(
                        label=description,
                        halign=Gtk.Align.START,
                        wrap=True,
                    )
                    desc_label.add_css_class("dim-label")
                    row_box.append(desc_label)

                suggestions_box.append(row_box)

        dialog.set_extra_child(content_box)
        dialog.connect("response", lambda dlg, _resp: dlg.destroy())
        dialog.present()

    def _copy_to_clipboard(self, text: str) -> None:
        display = self.get_display() or Gdk.Display.get_default()
        if not display:
            return
        clipboard = display.get_clipboard()
        clipboard.set(text)
        self._show_toast(_("Copiado para a área de transferência."))

    def _insert_text_into_editor(self, text: str) -> bool:
        text_view = self._get_focused_text_view()
        if not text_view:
            self._show_toast(
                _("Posicione o cursor dentro de um parágrafo para inserir o texto."),
                Adw.ToastPriority.HIGH,
            )
            return False

        cleaned = self._extract_ai_output(text)
        if not cleaned:
            self._show_toast(_("Nada para inserir."))
            return False

        buffer = text_view.get_buffer()
        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            buffer.delete(start, end)

        insert_mark = buffer.get_insert()
        iter_ = buffer.get_iter_at_mark(insert_mark)
        buffer.insert(iter_, cleaned + "\n\n")
        self._show_toast(_("Texto inserido no documento."))
        return True

    def _apply_ai_correction(self, text: str) -> None:
        target = getattr(self, "_ai_context_target", None)
        if not target:
            self._show_toast(
                _("Sem contexto de parágrafo disponível. Tente inserir no cursor."),
                Adw.ToastPriority.HIGH,
            )
            return

        cleaned = self._extract_ai_output(text)
        if not cleaned:
            self._show_toast(_("Nada para inserir."))
            return

        text_view = target.get("text_view")
        if not text_view:
            self._show_toast(
                _("Não foi possível determinar o parágrafo original."),
                Adw.ToastPriority.HIGH,
            )
            return

        buffer = text_view.get_buffer()
        start_iter = buffer.get_iter_at_offset(target.get("start", 0))
        end_iter = buffer.get_iter_at_offset(target.get("end", buffer.get_char_count()))

        buffer.begin_user_action()
        buffer.delete(start_iter, end_iter)
        buffer.insert(start_iter, cleaned + "\n\n")
        buffer.end_user_action()

        self._show_toast(_("Parágrafo atualizado com sugestão da IA."))
        self._ai_context_target = None

    def _extract_ai_output(self, text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            return ""

        lowered = cleaned.casefold()
        prefixes = [
            "o texto corrigido é",
            "o texto corrigido está",
            "o texto corrigido esta",
            "texto corrigido é",
            "texto corrigido",
            "texto revisado",
            "versão corrigida",
            "versão revisada",
            "correção",
            "correcao",
            "a versão corrigida da frase",
            "a versao corrigida da frase",
        ]
        for prefix in prefixes:
            if lowered.startswith(prefix):
                cleaned = cleaned[len(prefix):].lstrip(" :.-–—\n\"'""''`")
                break

        quote_pairs = {
            '"': '"',
            "'": "'",
            "\u201c": "\u201d",
            "\u2018": "\u2019",
            "\u00ab": "\u00bb",
        }
        if cleaned and cleaned[0] in quote_pairs:
            closing = quote_pairs[cleaned[0]]
            if cleaned.endswith(closing):
                cleaned = cleaned[1:-1].strip()

        # If the assistant returned explicit quoted segments, use the last quoted text.
        patterns = [
            r"'([^']+)'",
            r'"([^"]+)"',
            r"\u201c([^\u201d]+)\u201d",
            r"\u2018([^\u2019]+)\u2019",
            r"\u00ab([^\u00bb]+)\u00bb",
        ]
        matches = []
        for pattern in patterns:
            matches.extend(re.findall(pattern, cleaned))
        if matches:
            cleaned = matches[-1].strip()

        return cleaned.strip()

    # Search helpers
    def _reset_search_state(self):
        self._search_state = {'paragraph_index': -1, 'offset': -1}

    def _get_paragraph_textviews(self) -> List[Gtk.TextView]:
        views: List[Gtk.TextView] = []
        if not getattr(self, "paragraphs_box", None):
            return views
        child = self.paragraphs_box.get_first_child()
        while child:
            # Verify if is a Wrapper (ReorderableParagraphRow)
            if hasattr(child, 'editor') and hasattr(child.editor, 'text_view'):
                if child.editor.text_view:
                    views.append(child.editor.text_view)
            
            # Fallback
            elif hasattr(child, 'text_view') and child.text_view:
                views.append(child.text_view)
            child = child.get_next_sibling()
        return views

    def _on_search_text_changed(self, entry: Gtk.SearchEntry):
        self.search_query = entry.get_text().strip()
        self._reset_search_state()

    def _on_search_activate(self, entry: Gtk.SearchEntry):
        if not self.search_query:
            self._show_toast(_("Digite o texto para pesquisar."))
            return
        if not self._find_next_occurrence(restart=True):
            self._show_toast(_("Nenhuma correspondência encontrada."))

    def _on_search_next_clicked(self, _button: Gtk.Button):
        if not self.search_query:
            self._show_toast(_("Digite o texto para pesquisar."))
            return
        self._find_next_occurrence(restart=False)

    def _find_next_occurrence(self, restart: bool) -> bool:
        query = (self.search_query or "").strip()
        if not query:
            return False

        textviews = self._get_paragraph_textviews()
        if not textviews:
            self._show_toast(_("Nenhum parágrafo editável disponível."))
            return False

        query_fold = query.casefold()
        start_idx = 0
        start_offset = 0
        if not restart and self._search_state['paragraph_index'] >= 0:
            start_idx = self._search_state['paragraph_index']
            start_offset = self._search_state['offset'] + 1
        else:
            restart = True

        for idx in range(start_idx, len(textviews)):
            buffer = textviews[idx].get_buffer()
            text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
            haystack = text.casefold()
            search_offset = start_offset if (idx == start_idx and not restart) else 0
            match = haystack.find(query_fold, max(search_offset, 0))
            if match != -1:
                self._highlight_search_result(textviews[idx], match, len(query))
                self._search_state = {'paragraph_index': idx, 'offset': match}
                return True
            restart = False

        self._show_toast(_("Fim do documento alcançado."))
        self._reset_search_state()
        return False

    def _highlight_search_result(self, text_view: Gtk.TextView, start_offset: int, length: int) -> None:
        buffer = text_view.get_buffer()
        start_iter = buffer.get_iter_at_offset(start_offset)
        end_iter = buffer.get_iter_at_offset(start_offset + length)
        buffer.select_range(start_iter, end_iter)
        text_view.scroll_to_iter(start_iter, 0.25, True, 0.5, 0.1)
        text_view.grab_focus()

    def _save_window_state(self):
        """Save window state to config"""
        width, height = self.get_default_size()
        self.config.set('window_width', width)
        self.config.set('window_height', height)
        self.config.set('window_maximized', self.is_maximized())

        # Save sidebar paned position
        if hasattr(self, 'paned') and self.paned:
            if hasattr(self, 'sidebar') and self.sidebar.get_visible():
                self.config.set('sidebar_width', self.paned.get_position())

        # Save sidebar if visible
        if hasattr(self, 'sidebar_toggle_button'):
            self.config.set('sidebar_visible', self.sidebar_toggle_button.get_active())

    def _restore_window_state(self):
        """Restore window state from config"""
        if self.config.get('window_maximized', False):
            self.maximize()

        # Restore sidebar paned position
        if hasattr(self, 'paned') and self.paned:
            saved_pos = self.config.get('sidebar_width', 300)
            self.paned.set_position(saved_pos)

        # Restaura visibilidade da sidebar
        if hasattr(self, 'sidebar_toggle_button'):
            visible = self.config.get('sidebar_visible', True)
            self.sidebar_toggle_button.set_active(visible)

    def _maybe_show_welcome_dialog(self):
        """Show welcome dialog if enabled in config"""
        if self.config.get('show_welcome_dialog', True):
            self.show_welcome_dialog()
        return False

    def _maybe_show_first_run_tutorial(self):
        """Show first run tutorial with multiple steps"""
        if not self.config.get('show_first_run_tutorial', True):
            return False

        # Create and start the tour
        tour = FirstRunTour(self, self.config)
        tour.start()

        return False

    def _update_header_for_view(self, view_name: str):
        """Update header bar for current view"""
        title_widget = self.header_bar.get_title_widget()
        if view_name == "welcome":
            title_widget.set_title("TAC")
            title_widget.set_subtitle(_("Técnica da Argumentação Contínua"))
            self.save_button.set_sensitive(False)
            self.pomodoro_button.set_sensitive(False)
            self.references_button.set_sensitive(False)

        elif view_name == "editor" and self.current_project:
            title_widget.set_title(self.current_project.name)
            # Force recalculation of statistics
            stats = self.current_project.get_statistics()
            subtitle = FormatHelper.format_project_stats(stats['total_words'], stats['total_paragraphs'])
            title_widget.set_subtitle(subtitle)
            self.save_button.set_sensitive(True)
            self.pomodoro_button.set_sensitive(True)
            self.references_button.set_sensitive(True)


    def _show_loading_state(self):
        """Show loading indicator"""
        # Create loading spinner if it doesn't exist
        if not hasattr(self, 'loading_spinner'):
            self.loading_spinner = Gtk.Spinner()
            self.loading_spinner.set_size_request(48, 48)
            
        # Add to stack if not there
        if not self.main_stack.get_child_by_name("loading"):
            loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            loading_box.set_valign(Gtk.Align.CENTER)
            loading_box.set_halign(Gtk.Align.CENTER)
            
            self.loading_spinner.start()
            loading_box.append(self.loading_spinner)
            
            loading_label = Gtk.Label()
            loading_label.set_text(_("Carregando projeto..."))
            loading_label.add_css_class("dim-label")
            loading_box.append(loading_label)
            
            self.main_stack.add_named(loading_box, "loading")
        
        # Show loading
        self.main_stack.set_visible_child_name("loading")
        self._update_header_for_view("loading")

    def _on_project_loaded(self, project, error):
        """Callback when project finishes loading"""
        # Stop loading spinner
        if hasattr(self, 'loading_spinner'):
            self.loading_spinner.stop()
        
        if error:
            self._show_toast(_("Falha ao abrir projeto: {}").format(error), Adw.ToastPriority.HIGH)
            self._show_welcome_view()
            return False
        
        if project:
            self.current_project = project
            # Show editor optimized
            self._show_editor_view_optimized()
            self._show_toast(_("Projeto aberto: {}").format(project.name))
        else:
            self._show_toast(_("Falha ao abrir projeto"), Adw.ToastPriority.HIGH)
            self._show_welcome_view()
        
        return False 

    def _show_editor_view_optimized(self):
        """Show editor view with optimizations"""
        if not self.current_project:
            return
        
        # Check if editor view already exists
        editor_page = self.main_stack.get_child_by_name("editor")
        
        if not editor_page:
            # Create editor view only if it doesn't exist
            self.editor_view = self._create_editor_view()
            self.main_stack.add_named(self.editor_view, "editor")
        else:
            # Reuse existing view and only do incremental refresh
            self.editor_view = editor_page
            self._refresh_paragraphs()  # Now uses incremental update
        
        self.main_stack.set_visible_child_name("editor")
        self._update_header_for_view("editor")

    def handle_ai_pdf_error(self, error_message: str):
        """Handle errors from AI assistent while PDF analyse is runnig"""
        
        # 1. Close spinner window
        if self.pdf_loading_dialog:
            self.pdf_loading_dialog.destroy()
            self.pdf_loading_dialog = None

        # 2. Show error in dialog altert (Adw.MessageDialog)
        error_dialog = Adw.MessageDialog.new(
            self,
            _("Falha na Análise"),
            error_message
        )
        error_dialog.add_response("close", _("Fechar"))
        error_dialog.set_response_appearance("close", Adw.ResponseAppearance.DESTRUCTIVE)
        error_dialog.set_default_response("close")
        error_dialog.set_close_response("close")
        
        # Connect the signal to close the dialog
        error_dialog.connect("response", lambda dlg, resp: dlg.destroy())
        
        error_dialog.present()

    def _on_cloud_sync_clicked(self, button):
        """Handle cloud sync button click"""
        dialog = CloudSyncDialog(self)
        dialog.present()

    def _on_references_clicked(self, button):
        """Handle references to be used for quotes"""
        from ui.dialogs import ReferencesDialog
        dialog = ReferencesDialog(self)
        dialog.present()

    def _on_sidebar_toggle(self, button):
        """Handle sidebar toggle button"""
        if button.get_active():
            # Show sidebar
            self.sidebar.set_visible(True)
            pos = getattr(self, '_sidebar_last_position', self.config.get('sidebar_width', 300))
            if pos < 200:
                pos = 300
            self.paned.set_position(pos)
            button.set_icon_name('tac-sidebar-show-symbolic')
            button.set_tooltip_text(_("Ocultar Projetos (F9)"))
        else:
            # Hide sidebar
            self._sidebar_last_position = self.paned.get_position()
            self.sidebar.set_visible(False)
            self.paned.set_position(0)
            button.set_icon_name('tac-sidebar-show-symbolic')
            button.set_tooltip_text(_("Mostrar Projetos (F9)"))

    def _action_toggle_fullscreen(self, action, param):
        """Toggle fullscreen mode"""
        if self.is_fullscreen():
            self.unfullscreen()
            self.header_bar.set_visible(True)
        else:
            self.fullscreen()
            # Oculta a header bar para máximo espaço de escrita
            self.header_bar.set_visible(False)