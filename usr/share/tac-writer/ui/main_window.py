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
from .components import WelcomeView, ParagraphEditor, ProjectListWidget, SpellCheckHelper, PomodoroTimer, FirstRunTour
from .dialogs import NewProjectDialog, ExportDialog, PreferencesDialog, AboutDialog, WelcomeDialog, BackupManagerDialog, ImageDialog



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
        self.set_title(_("TAC - Continuous Argumentation Technique"))
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
        # Use Gtk.DrawingArea to ensure background is rendered
        self.tour_dark_overlay = Gtk.DrawingArea()
        self.tour_dark_overlay.set_vexpand(True)
        self.tour_dark_overlay.set_hexpand(True)
        self.tour_dark_overlay.add_css_class('dark-overlay')
        self.tour_dark_overlay.set_visible(False)
        self.tour_dark_overlay.set_can_target(False)  # Don't block mouse events
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

        # Title widget
        title_widget = Adw.WindowTitle()
        title_widget.set_title("TAC")
        self.header_bar.set_title_widget(title_widget)

        # Left side buttons
        self.new_project_button = Gtk.Button()
        self.new_project_button.set_icon_name('document-new-symbolic')
        self.new_project_button.set_tooltip_text(_("New Project (Ctrl+N)"))
        self.new_project_button.set_action_name("app.new_project")
        self.header_bar.pack_start(self.new_project_button)

        # Pomodoro Timer Button
        self.pomodoro_button = Gtk.Button()
        self.pomodoro_button.set_icon_name('alarm-symbolic')
        self.pomodoro_button.set_tooltip_text(_("Pomodoro Timer"))
        self.pomodoro_button.connect('clicked', self._on_pomodoro_clicked)
        self.pomodoro_button.set_sensitive(False)
        self.header_bar.pack_start(self.pomodoro_button)

        # Right side buttons
        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name('open-menu-symbolic')
        menu_button.set_tooltip_text(_("Main Menu"))
        self._setup_menu(menu_button)
        self.header_bar.pack_end(menu_button)

        save_button = Gtk.Button()
        save_button.set_icon_name('document-save-symbolic')
        save_button.set_tooltip_text(_("Save Project (Ctrl+S)"))
        save_button.set_action_name("app.save_project")
        save_button.set_sensitive(False)
        self.header_bar.pack_end(save_button)
        self.save_button = save_button

        # AI assistant button
        self.ai_button = Gtk.Button()
        self.ai_button.set_icon_name('avatar-default-symbolic')
        self.ai_button.set_tooltip_text(_("Ask AI Assistant (Ctrl+Shift+I)"))
        self.ai_button.connect('clicked', self._on_ai_pdf_clicked)
        self.header_bar.pack_end(self.ai_button)

        # Search box
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(_("Search..."))
        self.search_entry.set_width_chars(18)
        self.search_entry.connect("search-changed", self._on_search_text_changed)
        self.search_entry.connect("activate", self._on_search_activate)
        search_box.append(self.search_entry)

        self.search_next_button = Gtk.Button.new_from_icon_name('go-down-symbolic')
        self.search_next_button.set_tooltip_text(_("Find next occurrence"))
        self.search_next_button.add_css_class("flat")
        self.search_next_button.connect("clicked", self._on_search_next_clicked)
        search_box.append(self.search_next_button)

        self.header_bar.pack_end(search_box)

        

    def _setup_menu(self, menu_button):
        """Setup the main menu"""
        menu_model = Gio.Menu()

        # File section
        file_section = Gio.Menu()
        file_section.append(_("Export Project..."), "app.export_project")
        file_section.append(_("Backup Manager..."), "win.backup_manager")
        menu_model.append_section(None, file_section)

        # Edit section
        edit_section = Gio.Menu()
        edit_section.append(_("Undo"), "win.undo")
        edit_section.append(_("Redo"), "win.redo")
        menu_model.append_section(None, edit_section)

        # Preferences section
        preferences_section = Gio.Menu()
        preferences_section.append(_("Preferences"), "app.preferences")
        menu_model.append_section(None, preferences_section)

        # Help section
        help_section = Gio.Menu()
        help_section.append(_("Welcome Guide"), "win.show_welcome")
        help_section.append(_("Ask AI Assistant"), "app.ai_assistant")
        help_section.append(_("About TAC"), "app.about")
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
        sidebar_title.set_title(_("Projects"))
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
            ('toggle_sidebar', self._action_toggle_sidebar),
            ('add_paragraph', self._action_add_paragraph, 's'),
            ('insert_image', self._action_insert_image),
            ('show_welcome', self._action_show_welcome),
            ('undo', self._action_undo),
            ('redo', self._action_redo),
            ('backup_manager', self._action_backup_manager),
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
        self.add_button.set_label(_("Add Paragraph"))
        self.add_button.set_icon_name('list-add-symbolic')
        self.add_button.add_css_class("suggested-action")

        # Create menu model
        menu_model = Gio.Menu()
        paragraph_types = [
            (_("Title 1"), ParagraphType.TITLE_1),
            (_("Title 2"), ParagraphType.TITLE_2),
            (_("Introduction"), ParagraphType.INTRODUCTION),
            (_("Argument"), ParagraphType.ARGUMENT),
            (_("Argument Resumption"), ParagraphType.ARGUMENT_RESUMPTION),
            (_("Quote"), ParagraphType.QUOTE),
            (_("Epigraph"), ParagraphType.EPIGRAPH),
            (_("Conclusion"), ParagraphType.CONCLUSION),
        ]

        for label, ptype in paragraph_types:
            menu_model.append(label, f"win.add_paragraph('{ptype.value}')")

        self.add_button.set_menu_model(menu_model)
        toolbar_box.append(self.add_button)
        
        # Add image button
        image_button = Gtk.Button()
        image_button.set_label(_("Insert Image"))
        image_button.set_icon_name('insert-image-symbolic')
        image_button.set_tooltip_text(_("Insert Image (Ctrl+Alt+I)"))
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
        top_button.set_icon_name('go-up-symbolic')
        top_button.set_tooltip_text(_("Go to beginning"))
        top_button.add_css_class("circular")
        top_button.add_css_class("flat")
        top_button.set_size_request(40, 40)
        top_button.connect('clicked', self._on_scroll_to_top)
        nav_container.append(top_button)

        # Go to bottom button
        bottom_button = Gtk.Button()
        bottom_button.set_icon_name('go-down-symbolic')
        bottom_button.set_tooltip_text(_("Go to end"))
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
        if hasattr(self, 'editor_scrolled'):
            adjustment = self.editor_scrolled.get_vadjustment()
            adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size())

    def _refresh_paragraphs(self):
        """Refresh paragraphs display with optimized loading"""
        if not self.current_project:
            return
    
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
    
        child = self.paragraphs_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.paragraphs_box.remove(child)
            child = next_child
    
        self._paragraphs_to_add = list(self.current_project.paragraphs)
        self._existing_widgets = existing_widgets

        GLib.idle_add(self._process_next_paragraph)

    def _process_next_paragraph(self):
        """Process next paragraph for asynchronous loading"""
        if not self._paragraphs_to_add:
            return False

        paragraph = self._paragraphs_to_add.pop(0)
        
        # Check if it's an image paragraph
        if paragraph.type == ParagraphType.IMAGE:
            if paragraph.id in self._existing_widgets:
                widget = self._existing_widgets[paragraph.id]
                self.paragraphs_box.append(widget)
            else:
                image_widget = self._create_image_widget(paragraph)
                self.paragraphs_box.append(image_widget)
                self._existing_widgets[paragraph.id] = image_widget
        else:
            if paragraph.id in self._existing_widgets:
                widget = self._existing_widgets[paragraph.id]
                self.paragraphs_box.append(widget)
            else:
                paragraph_editor = ParagraphEditor(paragraph, config=self.config)
                paragraph_editor.connect('content-changed', self._on_paragraph_changed)
                paragraph_editor.connect('remove-requested', self._on_paragraph_remove_requested)
                paragraph_editor.connect('paragraph-reorder', self._on_paragraph_reorder)
                self.paragraphs_box.append(paragraph_editor)
                self._existing_widgets[paragraph.id] = paragraph_editor

        return True
    
    def _create_image_widget(self, paragraph):
        """Create widget to display an image paragraph"""
        from pathlib import Path
        
        metadata = paragraph.get_image_metadata()
        if not metadata:
            # Fallback for malformed image paragraph
            error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            error_label = Gtk.Label(label=_("⚠️ Error: Invalid image data"))
            error_label.add_css_class('error')
            error_box.append(error_label)
            error_box.paragraph = paragraph  # Store reference
            return error_box
        
        # Create main container
        image_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        image_container.set_margin_top(12)
        image_container.set_margin_bottom(12)
        image_container.paragraph = paragraph  # Store reference for tracking
        
        # Set alignment
        alignment = metadata.get('alignment', 'center')
        if alignment == 'center':
            image_container.set_halign(Gtk.Align.CENTER)
        elif alignment == 'right':
            image_container.set_halign(Gtk.Align.END)
        else:
            image_container.set_halign(Gtk.Align.START)
        
        # Try to load and display image
        try:
            img_path = Path(metadata['path'])
            if img_path.exists():
                texture = Gdk.Texture.new_from_filename(str(img_path))
                
                # Create picture widget
                picture = Gtk.Picture()
                picture.set_paintable(texture)
                picture.set_can_shrink(True)
                picture.set_content_fit(Gtk.ContentFit.CONTAIN)
                
                # Set size - Always display as 200px height thumbnail
                # Calculate width maintaining aspect ratio
                original_size = metadata.get('original_size', (800, 600))
                aspect_ratio = original_size[0] / original_size[1]
                thumbnail_height = 200
                thumbnail_width = int(thumbnail_height * aspect_ratio)
                
                picture.set_size_request(thumbnail_width, thumbnail_height)
                
                # Add frame
                frame = Gtk.Frame()
                frame.set_child(picture)
                image_container.append(frame)
                
                # Add caption if exists
                caption = metadata.get('caption', '')
                if caption:
                    caption_label = Gtk.Label(label=caption)
                    caption_label.add_css_class('caption')
                    caption_label.add_css_class('dim-label')
                    caption_label.set_wrap(True)
                    caption_label.set_max_width_chars(60)
                    caption_label.set_xalign(0.5)
                    image_container.append(caption_label)
                
                # Add toolbar for image actions
                toolbar = self._create_image_toolbar(paragraph)
                image_container.append(toolbar)
            
            else:
                # Image file not found
                placeholder = Gtk.Label(
                    label=_("⚠️ Image not found: {}").format(metadata.get('filename', 'unknown'))
                )
                placeholder.add_css_class('warning')
                image_container.append(placeholder)
        
        except Exception as e:
            # Error loading image
            error_label = Gtk.Label(
                label=_("⚠️ Error loading image: {}").format(str(e))
            )
            error_label.add_css_class('error')
            image_container.append(error_label)
        
        return image_container
    
    def _create_image_toolbar(self, paragraph):
        """Create toolbar with actions for image paragraph"""
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_halign(Gtk.Align.CENTER)
        toolbar.set_margin_top(6)

        # Edit button
        edit_btn = Gtk.Button()
        edit_btn.set_icon_name('document-edit-symbolic')
        edit_btn.set_tooltip_text(_("Edit Image"))
        edit_btn.connect('clicked', lambda b: self._on_edit_image(paragraph))
        toolbar.append(edit_btn)

        # Remove button
        remove_btn = Gtk.Button()
        remove_btn.set_icon_name('user-trash-symbolic')
        remove_btn.set_tooltip_text(_("Remove Image"))
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
            _("Remove Image?"),
            _("Are you sure you want to remove this image from the document?")
        )
        
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("remove", _("Remove"))
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
                    
                    self._show_toast(_("Image removed"))
                except Exception as e:
                    print(f"Error removing image: {e}")
                    self._show_toast(_("Error removing image"), Adw.ToastPriority.HIGH)
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

            self._show_toast(_("Image updated"))
        except (ValueError, Exception) as e:
            print(f"Error updating image: {e}")
            import traceback
            traceback.print_exc()
            self._show_toast(_("Error updating image"), Adw.ToastPriority.HIGH)

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
                    self._show_toast(_("Undo"))
                    return
            
            # Fallback: Try Ctrl+Z key simulation
            try:
                focused_text_view.emit('key-pressed', Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK, 0)
                return
            except:
                pass
        
        self._show_toast(_("Nothing to undo"))

    def _action_redo(self, action, param):
        """Handle global redo action"""
        focused_text_view = self._get_focused_text_view()
        if focused_text_view:
            buffer = focused_text_view.get_buffer()
            if buffer and hasattr(buffer, 'get_can_redo'):
                if buffer.get_can_redo():
                    buffer.redo()
                    self._show_toast(_("Redo"))
                    return
            
            # Fallback: Try Ctrl+Shift+Z key simulation
            try:
                focused_text_view.emit('key-pressed', Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, 0)
                return
            except:
                pass
        
        self._show_toast(_("Nothing to redo"))

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
        """Handle paragraph reordering"""
        if not self.current_project:
            return

        dragged_paragraph = self.current_project.get_paragraph(dragged_id)
        target_paragraph = self.current_project.get_paragraph(target_id)

        if not dragged_paragraph or not target_paragraph:
            return
        
        current_position = self.current_project.paragraphs.index(dragged_paragraph)
        target_position = self.current_project.paragraphs.index(target_paragraph)

        if position == "after":
            new_position = target_position + 1 if current_position < target_position else target_position
        else: # "before"
            new_position = target_position if current_position > target_position else target_position -1
        
        self.current_project.move_paragraph(dragged_id, new_position)
        self._refresh_paragraphs()
        self._update_header_for_view("editor")
        self._show_toast(_("Paragraph reordered"))

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
            # Could add unsaved changes dialog here
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
    def _action_toggle_sidebar(self, action, param):
        """Toggle sidebar visibility"""
        pass

    def _action_add_paragraph(self, action, param):
        """Add paragraph action"""
        if param:
            paragraph_type = ParagraphType(param.get_string())
            self._add_paragraph(paragraph_type)
    
    def _action_insert_image(self, action, param):
        """Handle insert image action"""
        if not self.current_project:
            self._show_toast(_("No project open"), Adw.ToastPriority.HIGH)
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
        # by temporarily enabling it
        self.config.set('show_first_run_tutorial', True)
        
    def _action_backup_manager(self, action, param):
        """Handle backup manager action"""
        self.show_backup_manager_dialog()

    # Public methods called by application
    def show_new_project_dialog(self):
        """Show new project dialog"""
        dialog = NewProjectDialog(self)
        dialog.connect('project-created', self._on_project_created)
        dialog.present()

    def show_open_project_dialog(self):
        """Show open project dialog"""
        file_chooser = Gtk.FileChooserNative.new(
            _("Open Project"),
            self,
            Gtk.FileChooserAction.OPEN,
            _("Open"),
            _("Cancel")
        )

        projects_dir = self.project_manager.projects_dir
        if projects_dir.exists():
            file_chooser.set_current_folder(Gio.File.new_for_path(str(projects_dir)))

        filter_json = Gtk.FileFilter()
        filter_json.set_name(_("TAC Projects (*.json)"))
        filter_json.add_pattern("*.json")
        file_chooser.add_filter(filter_json)

        filter_all = Gtk.FileFilter()
        filter_all.set_name(_("All Files"))
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
                        self._show_toast(_("Opened project: {}").format(project.name))
                    else:
                        self._show_toast(_("Failed to open project"), Adw.ToastPriority.HIGH)
            dialog.destroy()

        file_chooser.connect('response', on_response)
        file_chooser.show()

    def save_current_project(self) -> bool:
        """Save the current project"""
        if not self.current_project:
            return False

        success = self.project_manager.save_project(self.current_project)
        if success:
            self._show_toast(_("Project saved successfully"))
            self.project_list.refresh_projects()
            self.config.add_recent_project(self.current_project.id)
        else:
            self._show_toast(_("Failed to save project"), Adw.ToastPriority.HIGH)

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
            self._show_toast(_("Auto-save failed"), Adw.ToastPriority.HIGH)
        
        return False  # Don't repeat the timeout

    def show_export_dialog(self):
        """Show export dialog"""
        if not self.current_project:
            self._show_toast(_("No project to export"), Adw.ToastPriority.HIGH)
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
        self._show_toast(_("Database imported successfully"), Adw.ToastPriority.HIGH)

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
        paragraph_editor.connect('paragraph-reorder', self._on_paragraph_reorder)
        self.paragraphs_box.append(paragraph_editor)

        self._update_header_for_view("editor")
        # Update sidebar project list in real-time with current statistics
        current_stats = self.current_project.get_statistics()
        self.project_list.update_project_statistics(self.current_project.id, current_stats)

    def _on_project_created(self, dialog, project):
        """Handle new project creation"""
        self.current_project = project
        self._show_editor_view()

        self.project_list.refresh_projects()
        self._show_toast(_("Created project: {}").format(project.name))

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
        got_it_button = Gtk.Button.new_with_label(_("Got it!"))
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
                self._show_toast(_("Image inserted successfully"))
                
                # Update statistics
                current_stats = self.current_project.get_statistics()
                self.project_list.update_project_statistics(self.current_project.id, current_stats)
            else:
                self._show_toast(_("Failed to save project"), Adw.ToastPriority.HIGH)
        
        except Exception as e:
            print(f"Error adding image: {e}")
            import traceback
            traceback.print_exc()
            
            self._show_toast(_("Error inserting image"), Adw.ToastPriority.HIGH)

    def _show_toast(self, message: str, priority=Adw.ToastPriority.NORMAL):
        """Show a toast notification"""
        toast = Adw.Toast.new(message)
        toast.set_priority(priority)
        self.toast_overlay.add_toast(toast)

    # --- AI assistant helpers -------------------------------------------------
    def _on_ai_assistant_requested(self, *_args):
        if not self.ai_assistant:
            return

        if not self.config.get_ai_assistant_enabled():
            self._show_toast(
                _("Enable the AI assistant in Preferences ▸ AI Assistant."),
                Adw.ToastPriority.HIGH,
            )
            return

        missing = self.ai_assistant.missing_configuration()
        if missing:
            labels = {
                "provider": _("Provider"),
                "api_key": _("API key"),
            }
            readable = ", ".join(labels.get(item, item) for item in missing)
            self._show_toast(
                _("Configure {items} in Preferences ▸ AI Assistant.").format(
                    items=readable
                ),
                Adw.ToastPriority.HIGH,
            )
            return

        context_text, context_label = self._collect_ai_context()
        self._show_ai_prompt_dialog(context_text, context_label)

        # Adicione este método na MainWindow para abrir o diálogo de seleção
    def _on_ai_pdf_clicked(self, btn):
        if not self.config.get_ai_assistant_enabled():
            self._show_toast(_("Enable AI in Preferences. API key is required. Read Wiki if there is any doubt."), Adw.ToastPriority.HIGH)
            return

        from ui.dialogs import AiPdfDialog
        self.pdf_loading_dialog = AiPdfDialog(self, self.ai_assistant)
        self.pdf_loading_dialog.present()

    # Adicione este método para exibir o resultado (chamado pelo ai_assistant)
    def show_ai_pdf_result_dialog(self, result_text: str):
        # 1. Fecha a janela de "Analisando..." se ela estiver aberta
        if self.pdf_loading_dialog:
            self.pdf_loading_dialog.destroy()
            self.pdf_loading_dialog = None

        # 2. Abre a janela de resultado (com o layout corrigido)
        from ui.dialogs import AiResultDialog
        dialog = AiResultDialog(self, result_text)
        dialog.present()

        def handle_send() -> bool:
            start_iter = buffer.get_start_iter()
            end_iter = buffer.get_end_iter()
            text = buffer.get_text(start_iter, end_iter, True).strip()
            if not text:
                self._show_toast(_("Please enter a question for the assistant."))
                return False

            context_value = context_text if include_context_switch.get_active() else None
            if self.ai_assistant.request_assistance(text, context_value):
                self._show_toast(_("The AI assistant is processing your request..."))
                return True
            return False

        def on_response(dlg, response_id):
            if response_id == "send":
                if handle_send():
                    dlg.destroy()
                return
            dlg.destroy()

        #key_controller = Gtk.EventControllerKey.new()
        #buffer.connect("changed", lambda *_args: update_suggestions())

        def on_prompt_key_pressed(_controller, keyval, _keycode, state):
            if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and not (
                state & Gdk.ModifierType.SHIFT_MASK
            ):
                if handle_send():
                    dialog.destroy()
                return Gdk.EVENT_STOP
            return Gdk.EVENT_PROPAGATE

        #key_controller.connect("key-pressed", on_prompt_key_pressed)
        #text_view.add_controller(key_controller)

        dialog.connect("response", on_response)
        dialog.present()

    def show_ai_response_dialog(
        self,
        reply: str,
        suggestions: List[Dict[str, str]],
    ) -> None:
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("AI Assistant"),
            body=_("Here is the assistant's suggestion."),
            close_response="close",
        )
        dialog.add_response("close", _("Close"))
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

        reply_box = add_section(_("Response"))
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

        copy_button = Gtk.Button(label=_("Copy to clipboard"))
        copy_button.connect("clicked", lambda *_a: self._copy_to_clipboard(reply))
        actions_row.append(copy_button)

        insert_button = Gtk.Button(label=_("Insert at cursor"))
        insert_button.connect("clicked", lambda *_a: self._insert_text_into_editor(reply))
        actions_row.append(insert_button)

        reply_box.append(actions_row)

        apply_button = Gtk.Button(label=_("Apply correction"))
        apply_button.add_css_class("suggested-action")
        apply_button.set_sensitive(self._ai_context_target is not None)
        apply_button.connect(
            "clicked",
            lambda *_a: self._apply_ai_correction(reply),
        )
        actions_row.append(apply_button)

        if suggestions:
            suggestions_box = add_section(_("Additional suggestions"))
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
        self._show_toast(_("Copied to clipboard."))

    def _insert_text_into_editor(self, text: str) -> bool:
        text_view = self._get_focused_text_view()
        if not text_view:
            self._show_toast(
                _("Place the cursor inside a paragraph to insert the text."),
                Adw.ToastPriority.HIGH,
            )
            return False

        cleaned = self._extract_ai_output(text)
        if not cleaned:
            self._show_toast(_("Nothing to insert."))
            return False

        buffer = text_view.get_buffer()
        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            buffer.delete(start, end)

        insert_mark = buffer.get_insert()
        iter_ = buffer.get_iter_at_mark(insert_mark)
        buffer.insert(iter_, cleaned + "\n\n")
        self._show_toast(_("Text inserted into the document."))
        return True

    def _apply_ai_correction(self, text: str) -> None:
        target = getattr(self, "_ai_context_target", None)
        if not target:
            self._show_toast(
                _("No paragraph context available. Try inserting at the cursor."),
                Adw.ToastPriority.HIGH,
            )
            return

        cleaned = self._extract_ai_output(text)
        if not cleaned:
            self._show_toast(_("Nothing to insert."))
            return

        text_view = target.get("text_view")
        if not text_view:
            self._show_toast(
                _("Could not determine the original paragraph."),
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

        self._show_toast(_("Paragraph updated with AI suggestion."))
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
                cleaned = cleaned[len(prefix):].lstrip(" :.-–—\n\"'“”‘’`")
                break

        quote_pairs = {
            '"': '"',
            "'": "'",
            "“": "”",
            "‘": "’",
            "«": "»",
        }
        if cleaned and cleaned[0] in quote_pairs:
            closing = quote_pairs[cleaned[0]]
            if cleaned.endswith(closing):
                cleaned = cleaned[1:-1].strip()

        # If the assistant returned explicit quoted segments, use the last quoted text.
        patterns = [
            r"'([^']+)'",
            r'"([^"]+)"',
            r"“([^”]+)”",
            r"‘([^’]+)’",
            r"«([^»]+)»",
        ]
        matches = []
        for pattern in patterns:
            matches.extend(re.findall(pattern, cleaned))
        if matches:
            cleaned = matches[-1].strip()

        return cleaned.strip()

    # --- Search helpers -------------------------------------------------------
    def _reset_search_state(self):
        self._search_state = {'paragraph_index': -1, 'offset': -1}

    def _get_paragraph_textviews(self) -> List[Gtk.TextView]:
        views: List[Gtk.TextView] = []
        if not getattr(self, "paragraphs_box", None):
            return views
        child = self.paragraphs_box.get_first_child()
        while child:
            text_view = getattr(child, "text_view", None)
            if text_view:
                views.append(text_view)
            child = child.get_next_sibling()
        return views

    def _on_search_text_changed(self, entry: Gtk.SearchEntry):
        self.search_query = entry.get_text().strip()
        self._reset_search_state()

    def _on_search_activate(self, entry: Gtk.SearchEntry):
        if not self.search_query:
            self._show_toast(_("Enter text to search."))
            return
        if not self._find_next_occurrence(restart=True):
            self._show_toast(_("No matches found."))

    def _on_search_next_clicked(self, _button: Gtk.Button):
        if not self.search_query:
            self._show_toast(_("Enter text to search."))
            return
        self._find_next_occurrence(restart=False)

    def _find_next_occurrence(self, restart: bool) -> bool:
        query = (self.search_query or "").strip()
        if not query:
            return False

        textviews = self._get_paragraph_textviews()
        if not textviews:
            self._show_toast(_("No editable paragraphs available."))
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

        self._show_toast(_("Reached the end of the document."))
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

    def _restore_window_state(self):
        """Restore window state from config"""
        if self.config.get('window_maximized', False):
            self.maximize()

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
            title_widget.set_subtitle(_("Continuous Argumentation Technique"))
            self.save_button.set_sensitive(False)
            self.pomodoro_button.set_sensitive(False)

        elif view_name == "editor" and self.current_project:
            title_widget.set_title(self.current_project.name)
            # Force recalculation of statistics
            stats = self.current_project.get_statistics()
            subtitle = FormatHelper.format_project_stats(stats['total_words'], stats['total_paragraphs'])
            title_widget.set_subtitle(subtitle)
            self.save_button.set_sensitive(True)
            self.pomodoro_button.set_sensitive(True)

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
            loading_label.set_text(_("Loading project..."))
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
            self._show_toast(_("Failed to open project: {}").format(error), Adw.ToastPriority.HIGH)
            self._show_welcome_view()
            return False
        
        if project:
            self.current_project = project
            # Show editor optimized
            self._show_editor_view_optimized()
            self._show_toast(_("Opened project: {}").format(project.name))
        else:
            self._show_toast(_("Failed to open project"), Adw.ToastPriority.HIGH)
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
        """Lida com erros vindos do assistente de IA durante análise de PDF"""
        
        # 1. Fecha a janela de "Analisando..." (o spinner)
        if self.pdf_loading_dialog:
            self.pdf_loading_dialog.destroy()
            self.pdf_loading_dialog = None

        # 2. Mostra o erro em um diálogo de alerta (Adw.MessageDialog)
        # Isso é melhor que o toast pois obriga o usuário a ler e fechar
        error_dialog = Adw.MessageDialog.new(
            self,
            _("Analysis Failure"),
            error_message
        )
        error_dialog.add_response("close", _("Close"))
        error_dialog.set_response_appearance("close", Adw.ResponseAppearance.DESTRUCTIVE)
        error_dialog.set_default_response("close")
        error_dialog.set_close_response("close")
        
        # Conecta o sinal para fechar o diálogo
        error_dialog.connect("response", lambda dlg, resp: dlg.destroy())
        
        error_dialog.present()