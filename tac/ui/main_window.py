"""
TAC Main Window
Main application window using GTK4 and libadwaita
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GObject, GLib

from core.models import Project, ParagraphType
from core.services import ProjectManager, ExportService
from core.config import Config
from utils.helpers import TextHelper, ValidationHelper, FormatHelper
from .components import WelcomeView, ParagraphEditor, ProjectListWidget
from .dialogs import NewProjectDialog, ExportDialog, PreferencesDialog, AboutDialog


class MainWindow(Adw.ApplicationWindow):
    """Main application window"""
    
    __gtype_name__ = 'TacMainWindow'
    
    def __init__(self, application, project_manager: ProjectManager, config: Config, **kwargs):
        super().__init__(application=application, **kwargs)
        
        # Store references
        self.project_manager = project_manager
        self.config = config
        self.export_service = ExportService()
        self.current_project: Project = None
        
        # UI components
        self.header_bar = None
        self.toast_overlay = None
        self.main_stack = None
        self.welcome_view = None
        self.editor_view = None
        self.sidebar = None
        
        # Setup window
        self._setup_window()
        self._setup_ui()
        self._setup_actions()
        self._restore_window_state()
        
        print("MainWindow initialized")
    
    def _setup_window(self):
        """Setup basic window properties"""
        self.set_title("TAC - Text Analysis and Creation")
        self.set_icon_name("com.github.tac")
        
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
        self.set_content(self.toast_overlay)
        
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
        
        # Title widget
        title_widget = Adw.WindowTitle()
        title_widget.set_title("TAC")
        self.header_bar.set_title_widget(title_widget)
        
        # Left side buttons
        new_button = Gtk.Button()
        new_button.set_icon_name("document-new-symbolic")
        new_button.set_tooltip_text("New Project (Ctrl+N)")
        new_button.set_action_name("app.new_project")
        self.header_bar.pack_start(new_button)
        
        open_button = Gtk.Button()
        open_button.set_icon_name("document-open-symbolic") 
        open_button.set_tooltip_text("Open Project (Ctrl+O)")
        open_button.set_action_name("app.open_project")
        self.header_bar.pack_start(open_button)
        
        # Right side buttons
        save_button = Gtk.Button()
        save_button.set_icon_name("document-save-symbolic")
        save_button.set_tooltip_text("Save Project (Ctrl+S)")
        save_button.set_action_name("app.save_project")
        save_button.set_sensitive(False)  # Initially disabled
        self.header_bar.pack_end(save_button)
        self.save_button = save_button
        
        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_tooltip_text("Main Menu")
        self._setup_menu(menu_button)
        self.header_bar.pack_end(menu_button)
    
    def _setup_menu(self, menu_button):
        """Setup the main menu"""
        menu_model = Gio.Menu()
        
        # File section
        file_section = Gio.Menu()
        file_section.append("Export Project...", "app.export_project")
        file_section.append("Recent Projects", "win.show_recent")
        menu_model.append_section(None, file_section)
        
        # Edit section
        edit_section = Gio.Menu()
        edit_section.append("Preferences", "app.preferences")
        menu_model.append_section(None, edit_section)
        
        # Help section  
        help_section = Gio.Menu()
        help_section.append("About TAC", "app.about")
        menu_model.append_section(None, help_section)
        
        menu_button.set_menu_model(menu_model)
    
    def _setup_content_area(self, main_box):
        """Setup the main content area"""
        # Leaflet for responsive layout
        self.leaflet = Adw.Leaflet()
        self.leaflet.set_can_navigate_back(True)
        self.leaflet.set_can_navigate_forward(True)
        main_box.append(self.leaflet)
        
        # Sidebar
        self._setup_sidebar()
        
        # Main content stack
        self.main_stack = Adw.ViewStack()
        self.main_stack.set_vexpand(True)
        self.main_stack.set_hexpand(True)
        self.leaflet.append(self.main_stack)
    
    def _setup_sidebar(self):
        """Setup the sidebar"""
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.set_size_request(300, -1)
        sidebar_box.add_css_class("sidebar")
        
        # Sidebar header
        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_show_end_title_buttons(False)
        sidebar_title = Adw.WindowTitle()
        sidebar_title.set_title("Projects")
        sidebar_header.set_title_widget(sidebar_title)
        sidebar_box.append(sidebar_header)
        
        # Project list
        self.project_list = ProjectListWidget(self.project_manager)
        self.project_list.connect('project-selected', self._on_project_selected)
        sidebar_box.append(self.project_list)
        
        self.leaflet.append(sidebar_box)
        self.sidebar = sidebar_box
    
    def _setup_actions(self):
        """Setup window-specific actions"""
        actions = [
            ('show_recent', self._action_show_recent),
            ('toggle_sidebar', self._action_toggle_sidebar),
            ('add_paragraph', self._action_add_paragraph, 's'),  # 's' = string parameter
        ]
        
        for action_data in actions:
            if len(action_data) == 3:
                # Action with parameter - use string to create VariantType
                action = Gio.SimpleAction.new(action_data[0], GLib.VariantType.new(action_data[2]))
            else:
                # Simple action
                action = Gio.SimpleAction.new(action_data[0], None)
            
            action.connect('activate', action_data[1])
            self.add_action(action)
    
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
    
    def _create_editor_view(self) -> Gtk.Widget:
        """Create the editor view for current project"""
        # Main editor container
        editor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Scrolled window for paragraphs
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        
        # Paragraphs container
        self.paragraphs_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.paragraphs_box.set_spacing(12)
        self.paragraphs_box.set_margin_start(20)
        self.paragraphs_box.set_margin_end(20)
        self.paragraphs_box.set_margin_top(20)
        self.paragraphs_box.set_margin_bottom(20)
        
        scrolled.set_child(self.paragraphs_box)
        editor_box.append(scrolled)
        
        # Add existing paragraphs
        self._refresh_paragraphs()
        
        # Add paragraph toolbar
        toolbar = self._create_paragraph_toolbar()
        editor_box.append(toolbar)
        
        return editor_box
    
    def _create_paragraph_toolbar(self) -> Gtk.Widget:
        """Create toolbar for adding paragraphs"""
        toolbar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        toolbar_box.set_spacing(6)
        toolbar_box.set_margin_start(20)
        toolbar_box.set_margin_end(20)
        toolbar_box.set_margin_top(10)
        toolbar_box.set_margin_bottom(20)
        toolbar_box.add_css_class("toolbar")
        
        # Add paragraph buttons
        paragraph_types = [
            ("Introduction", ParagraphType.INTRODUCTION, "list-add-symbolic"),
            ("Topic", ParagraphType.TOPIC, "format-text-bold-symbolic"),
            ("Argument", ParagraphType.ARGUMENT, "format-justify-left-symbolic"),
            ("Quote", ParagraphType.ARGUMENT_QUOTE, "format-quote-close-symbolic"),
            ("Conclusion", ParagraphType.CONCLUSION, "object-select-symbolic"),
        ]
        
        for label, ptype, icon in paragraph_types:
            button = Gtk.Button()
            button.set_label(f"Add {label}")
            button.set_icon_name(icon)
            button.connect('clicked', lambda btn, pt=ptype: self._add_paragraph(pt))
            toolbar_box.append(button)
        
        return toolbar_box
    
    def _refresh_paragraphs(self):
        """Refresh the paragraphs display"""
        if not self.current_project:
            return
        
        # Clear existing paragraphs
        child = self.paragraphs_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.paragraphs_box.remove(child)
            child = next_child
        
        # Add paragraphs
        for paragraph in self.current_project.paragraphs:
            paragraph_editor = ParagraphEditor(paragraph)
            paragraph_editor.connect('content-changed', self._on_paragraph_changed)
            paragraph_editor.connect('remove-requested', self._on_paragraph_remove_requested)
            self.paragraphs_box.append(paragraph_editor)
    
    def _update_header_for_view(self, view_name: str):
        """Update header bar for current view"""
        if view_name == "welcome":
            title_widget = self.header_bar.get_title_widget()
            title_widget.set_title("TAC")
            title_widget.set_subtitle("Text Analysis and Creation")
            self.save_button.set_sensitive(False)
        elif view_name == "editor" and self.current_project:
            title_widget = self.header_bar.get_title_widget()
            title_widget.set_title(self.current_project.name)
            
            # Show project statistics in subtitle
            stats = self.current_project.get_statistics()
            subtitle = f"{stats['total_words']} words • {stats['total_paragraphs']} paragraphs"
            title_widget.set_subtitle(subtitle)
            
            self.save_button.set_sensitive(True)
    
    # Event handlers
    def _on_create_project_from_welcome(self, widget, template_name):
        """Handle create project from welcome view"""
        self.show_new_project_dialog()
    
    def _on_open_project_from_welcome(self, widget, project_info):
        """Handle open project from welcome view"""
        self._load_project(project_info['id'])
    
    def _on_project_selected(self, widget, project_info):
        """Handle project selection from sidebar"""
        self._load_project(project_info['id'])
    
    def _on_paragraph_changed(self, paragraph_editor):
        """Handle paragraph content changes"""
        if self.current_project:
            # Update project modification time
            self.current_project._update_modified_time()
            self._update_header_for_view("editor")
    
    def _on_paragraph_remove_requested(self, paragraph_editor, paragraph_id):
        """Handle paragraph removal request"""
        if self.current_project:
            self.current_project.remove_paragraph(paragraph_id)
            self._refresh_paragraphs()
            self._update_header_for_view("editor")
    
    def _on_close_request(self, window):
        """Handle window close request"""
        self._save_window_state()
        
        # Auto-save current project
        if self.current_project:
            self.save_current_project()
        
        return False  # Allow closing
    
    def _on_window_state_changed(self, window, pspec):
        """Handle window state changes"""
        self._save_window_state()
    
    # Action handlers
    def _action_show_recent(self, action, param):
        """Show recent projects"""
        # TODO: Implement recent projects view
        pass
    
    def _action_toggle_sidebar(self, action, param):
        """Toggle sidebar visibility"""
        # TODO: Implement sidebar toggle
        pass
    
    def _action_add_paragraph(self, action, param):
        """Add paragraph action"""
        if param:
            paragraph_type = ParagraphType(param.get_string())
            self._add_paragraph(paragraph_type)
    
    # Public methods called by application
    def show_new_project_dialog(self):
        """Show new project dialog"""
        dialog = NewProjectDialog(self)
        dialog.connect('project-created', self._on_project_created)
        dialog.present()
    
    def show_open_project_dialog(self):
        """Show open project dialog"""
        # For now, just show the sidebar if not visible
        self.leaflet.set_visible_child(self.sidebar)
    
    def save_current_project(self) -> bool:
        """Save the current project"""
        if not self.current_project:
            return False
        
        success = self.project_manager.save_project(self.current_project)
        
        if success:
            self._show_toast("Project saved successfully")
            # Update recent projects
            project_path = str(self.project_manager.get_project_path(self.current_project))
            self.config.add_recent_project(project_path)
        else:
            self._show_toast("Failed to save project", Adw.ToastPriority.HIGH)
        
        return success
    
    def show_export_dialog(self):
        """Show export dialog"""
        if not self.current_project:
            self._show_toast("No project to export", Adw.ToastPriority.HIGH)
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
    
    # Helper methods
    def _load_project(self, project_id: str):
        """Load a project"""
        project = self.project_manager.load_project(project_id)
        if project:
            self.current_project = project
            self._show_editor_view()
            self._show_toast(f"Opened project: {project.name}")
        else:
            self._show_toast(f"Failed to open project", Adw.ToastPriority.HIGH)
    
    def _add_paragraph(self, paragraph_type: ParagraphType):
        """Add a new paragraph"""
        if not self.current_project:
            return
        
        paragraph = self.current_project.add_paragraph(paragraph_type)
        self._refresh_paragraphs()
        self._update_header_for_view("editor")
        
        # Focus the new paragraph
        # TODO: Scroll to and focus new paragraph
    
    def _on_project_created(self, dialog, project):
        """Handle new project creation"""
        self.current_project = project
        self._show_editor_view()
        self._show_toast(f"Created project: {project.name}")
    
    def _show_toast(self, message: str, priority=Adw.ToastPriority.NORMAL):
        """Show a toast notification"""
        toast = Adw.Toast.new(message)
        toast.set_priority(priority)
        self.toast_overlay.add_toast(toast)
    
    def _save_window_state(self):
        """Save window state to config"""
        width, height = self.get_default_size()
        self.config.set('window_width', width)
        self.config.set('window_height', height)
        self.config.set('window_maximized', self.is_maximized())
    
    def _restore_window_state(self):
        """Restore window state from config"""
        if self.config.get('window_maximized', False):
            self.maximize()