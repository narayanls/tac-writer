"""
TAC UI Dialogs
Dialog windows for the TAC application using GTK4 and libadwaita
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GObject, Gio, Gdk, Pango, GLib

import os
import sqlite3
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

from core.models import Project, DEFAULT_TEMPLATES
from core.services import ProjectManager, ExportService
from core.config import Config
from utils.helpers import ValidationHelper, FileHelper
from utils.i18n import _


def get_system_fonts():
    """Get list of system fonts using multiple fallback methods"""
    font_names = []
    
    try:
        # Method 1: Try PangoCairo
        gi.require_version('PangoCairo', '1.0')
        from gi.repository import PangoCairo
        font_map = PangoCairo.font_map_get_default()
        families = font_map.list_families()
        for family in families:
            font_names.append(family.get_name())
    except (ImportError, ValueError) as e:
        try:
            # Method 2: Try Pango context
            context = Pango.Context()
            font_map = context.get_font_map()
            families = font_map.list_families()
            for family in families:
                font_names.append(family.get_name())
        except Exception as e2:
            try:
                # Method 3: Use fontconfig command
                result = subprocess.run(['fc-list', ':', 'family'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    font_names = set()
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            family = line.split(',')[0].strip()
                            font_names.add(family)
                    font_names = sorted(list(font_names))
            except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError) as e3:
                # Fallback fonts
                font_names = ["Liberation Serif", "DejaVu Sans", "Ubuntu", "Cantarell"]
    
    if not font_names:
        font_names = ["Liberation Serif"]
    
    return sorted(font_names)


class NewProjectDialog(Adw.Window):
    """Dialog for creating new projects"""

    __gtype_name__ = 'TacNewProjectDialog'

    __gsignals__ = {
        'project-created': (GObject.SIGNAL_RUN_FIRST, None, (object,)),
    }

    def __init__(self, parent, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("New Project"))
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(600, 700)
        self.set_resizable(True)

        # Get project manager from parent
        self.project_manager = parent.project_manager

        # Create UI
        self._create_ui()

    def _create_ui(self):
        """Create the dialog UI"""
        # Main content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content_box)

        # Header bar
        header_bar = Adw.HeaderBar()
        header_bar.set_show_end_title_buttons(False)

        # Cancel button
        cancel_button = Gtk.Button()
        cancel_button.set_label(_("Cancel"))
        cancel_button.connect('clicked', lambda x: self.destroy())
        header_bar.pack_start(cancel_button)

        # Create button
        self.create_button = Gtk.Button()
        self.create_button.set_label(_("Create"))
        self.create_button.add_css_class("suggested-action")
        self.create_button.set_sensitive(False)
        self.create_button.connect('clicked', self._on_create_clicked)
        header_bar.pack_end(self.create_button)

        content_box.append(header_bar)

        # Scrolled window for content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(600)
        content_box.append(scrolled)

        # Main content
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)
        main_box.set_spacing(32)
        scrolled.set_child(main_box)

        # Project details section
        self._create_details_section(main_box)

        # Template selection section
        self._create_template_section(main_box)

    def _create_details_section(self, parent):
        """Create project details section"""
        details_group = Adw.PreferencesGroup()
        details_group.set_title(_("Project Details"))

        # Project name row
        name_row = Adw.ActionRow()
        name_row.set_title(_("Project Name"))
        self.name_entry = Gtk.Entry()
        self.name_entry.set_placeholder_text(_("Enter project name..."))
        self.name_entry.set_text(_("My New Project"))
        self.name_entry.set_size_request(200, -1)
        self.name_entry.connect('changed', self._on_name_changed)
        self.name_entry.connect('activate', self._on_name_activate)

        # Initial validation check
        self._on_name_changed(self.name_entry)

        # Focus and select all text for easy replacement
        self.name_entry.grab_focus()
        self.name_entry.select_region(0, -1)

        name_row.add_suffix(self.name_entry)
        details_group.add(name_row)

        # Author row
        author_row = Adw.ActionRow()
        author_row.set_title(_("Author"))
        self.author_entry = Gtk.Entry()
        self.author_entry.set_placeholder_text(_("Your name..."))
        self.author_entry.set_size_request(200, -1)
        author_row.add_suffix(self.author_entry)
        details_group.add(author_row)

        parent.append(details_group)

        # Description section
        desc_group = Adw.PreferencesGroup()
        desc_group.set_title(_("Description"))

        # Description text view in a frame
        desc_frame = Gtk.Frame()
        desc_frame.set_margin_start(12)
        desc_frame.set_margin_end(12)
        desc_frame.set_margin_top(8)
        desc_frame.set_margin_bottom(12)

        desc_scrolled = Gtk.ScrolledWindow()
        desc_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        desc_scrolled.set_size_request(-1, 120)

        self.description_view = Gtk.TextView()
        self.description_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.description_view.set_margin_start(8)
        self.description_view.set_margin_end(8)
        self.description_view.set_margin_top(8)
        self.description_view.set_margin_bottom(8)

        desc_scrolled.set_child(self.description_view)
        desc_frame.set_child(desc_scrolled)

        desc_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        desc_box.append(desc_group)
        desc_box.append(desc_frame)

        parent.append(desc_box)

    def _create_template_section(self, parent):
        """Create template selection section"""
        template_group = Adw.PreferencesGroup()
        template_group.set_title(_("Template"))
        template_group.set_description(_("Choose a template to start with"))

        # Template selection
        self.template_combo = Gtk.ComboBoxText()
        for template in DEFAULT_TEMPLATES:
            self.template_combo.append(template.name, template.name)
        self.template_combo.set_active(0)

        template_row = Adw.ActionRow()
        template_row.set_title(_("Document Template"))
        template_row.add_suffix(self.template_combo)
        template_group.add(template_row)

        # Template description
        self.template_desc_label = Gtk.Label()
        self.template_desc_label.set_wrap(True)
        self.template_desc_label.set_halign(Gtk.Align.START)
        self.template_desc_label.add_css_class("caption")
        self.template_desc_label.set_margin_start(12)
        self.template_desc_label.set_margin_end(12)
        self.template_desc_label.set_margin_bottom(12)

        # Update description
        self.template_combo.connect('changed', self._on_template_changed)
        self._on_template_changed(self.template_combo)

        template_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        template_box.append(template_group)
        template_box.append(self.template_desc_label)

        parent.append(template_box)

    def _on_name_activate(self, entry):
        """Handle Enter key in name field"""
        if self.create_button.get_sensitive():
            self._on_create_clicked(self.create_button)

    def _on_name_changed(self, entry):
        """Handle project name changes"""
        name = entry.get_text().strip()
        is_valid, error_msg = ValidationHelper.is_valid_project_name(name)
        
        self.create_button.set_sensitive(is_valid)
        
        if not is_valid and name:
            entry.add_css_class("error")
            entry.set_tooltip_text(error_msg)
        else:
            entry.remove_css_class("error")
            entry.set_tooltip_text("")

    def _on_template_changed(self, combo):
        """Handle template selection changes"""
        template_name = combo.get_active_id()
        for template in DEFAULT_TEMPLATES:
            if template.name == template_name:
                self.template_desc_label.set_text(template.description)
                break

    def _on_create_clicked(self, button):
        """Handle create button click"""
        # Get form data
        name = self.name_entry.get_text().strip()
        author = self.author_entry.get_text().strip()
        template_name = self.template_combo.get_active_id()

        # Get description
        desc_buffer = self.description_view.get_buffer()
        start_iter = desc_buffer.get_start_iter()
        end_iter = desc_buffer.get_end_iter()
        description = desc_buffer.get_text(start_iter, end_iter, False).strip()

        try:
            # Validate inputs
            if not name:
                raise ValueError(_("Project name cannot be empty"))
            
            if len(name) > 100:
                raise ValueError(_("Project name is too long (max 100 characters)"))
            
            # Create project
            project = self.project_manager.create_project(name, template_name)
            
            # Update metadata
            project.update_metadata({
                'author': author,
                'description': description
            })
            
            # Save project
            if not self.project_manager.save_project(project):
                raise RuntimeError(_("Failed to save project to database"))
            
            # Emit signal and close
            self.emit('project-created', project)
            self.destroy()
            
        except ValueError as validation_error:
            # Validation error - user input problem
            error_dialog = Adw.MessageDialog.new(
                self,
                _("Invalid Input"),
                str(validation_error)
            )
            error_dialog.add_response("ok", _("OK"))
            error_dialog.present()
        
        except RuntimeError as runtime_error:
            # Runtime error - operation failed
            error_dialog = Adw.MessageDialog.new(
                self,
                _("Error Creating Project"),
                str(runtime_error)
            )
            error_dialog.add_response("ok", _("OK"))
            error_dialog.present()
        
        except Exception as e:
            # Unexpected error - show technical details
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
            error_dialog = Adw.MessageDialog.new(
                self,
                _("Unexpected Error"),
                _("An unexpected error occurred. Please report this issue:") + "\n\n" + error_msg
            )
            error_dialog.add_response("ok", _("OK"))
            error_dialog.present()


class ExportDialog(Adw.Window):
    """Dialog for exporting projects"""

    __gtype_name__ = 'TacExportDialog'

    def __init__(self, parent, project: Project, export_service: ExportService, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("Export Project"))
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(550, 550)
        self.set_resizable(True)

        self.project = project
        self.export_service = export_service

        self._create_ui()

    def _create_ui(self):
        """Create the dialog UI"""
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content_box)

        # Header bar
        header_bar = Adw.HeaderBar()

        cancel_button = Gtk.Button()
        cancel_button.set_label(_("Cancel"))
        cancel_button.connect('clicked', lambda x: self.destroy())
        header_bar.pack_start(cancel_button)

        export_button = Gtk.Button()
        export_button.set_label(_("Export"))
        export_button.add_css_class("suggested-action")
        export_button.connect('clicked', self._on_export_clicked)
        header_bar.pack_end(export_button)

        content_box.append(header_bar)

        # Preferences page
        prefs_page = Adw.PreferencesPage()
        content_box.append(prefs_page)

        # Project info
        info_group = Adw.PreferencesGroup()
        info_group.set_title(_("Project Information"))
        prefs_page.add(info_group)

        name_row = Adw.ActionRow()
        name_row.set_title(_("Project Name"))
        name_row.set_subtitle(self.project.name)
        info_group.add(name_row)

        stats = self.project.get_statistics()
        stats_row = Adw.ActionRow()
        stats_row.set_title(_("Statistics"))
        stats_row.set_subtitle(_("{} words, {} paragraphs").format(stats['total_words'], stats['total_paragraphs']))
        info_group.add(stats_row)

        # Export options
        export_group = Adw.PreferencesGroup()
        export_group.set_title(_("Export Options"))
        prefs_page.add(export_group)

        # Format selection
        self.format_row = Adw.ComboRow()
        self.format_row.set_title(_("Format"))
        format_model = Gtk.StringList()

        formats = [
            ("ODT", "odt"),
            ("TXT", "txt"),
            ("PDF", "pdf")
        ]

        self.format_data = []
        for display_name, format_code in formats:
            format_model.append(display_name)
            self.format_data.append(format_code)

        self.format_row.set_model(format_model)
        self.format_row.set_selected(0)
        export_group.add(self.format_row)

        # Include metadata
        self.metadata_row = Adw.SwitchRow()
        self.metadata_row.set_title(_("Include Metadata"))
        self.metadata_row.set_subtitle(_("Include author, creation date, and other project information"))
        self.metadata_row.set_active(True)
        export_group.add(self.metadata_row)

        # File location
        location_group = Adw.PreferencesGroup()
        location_group.set_title(_("Output Location"))
        prefs_page.add(location_group)

        self.location_row = Adw.ActionRow()
        self.location_row.set_title(_("Save Location"))
        self.location_row.set_subtitle(_("Click to choose location"))

        choose_button = Gtk.Button()
        choose_button.set_label(_("Choose..."))
        choose_button.set_valign(Gtk.Align.CENTER)
        choose_button.connect('clicked', self._on_choose_location)
        self.location_row.add_suffix(choose_button)

        location_group.add(self.location_row)

        # Initialize with default location - TAC Projects subfolder
        documents_dir = self._get_documents_directory()
        default_location = documents_dir / "TAC Projects"
        try:
            default_location.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(_("Warning: Could not create default export directory: {}").format(e))
            default_location = documents_dir
        
        self.selected_location = default_location
        self.location_row.set_subtitle(str(default_location))

    def _get_documents_directory(self) -> Path:
        """Get user's Documents directory in a language-aware way"""
        home = Path.home()
        
        # Try XDG user dirs first (Linux)
        try:
            result = subprocess.run(['xdg-user-dir', 'DOCUMENTS'], 
                                capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                documents_path = Path(result.stdout.strip())
                if documents_path.exists():
                    return documents_path
        except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Try common localized directory names
        possible_names = [
            'Documents',    # English, French
            'Documentos',   # Portuguese, Spanish
            'Dokumente',    # German
            'Documenti',    # Italian
            'Документы',    # Russian
            'Документи',    # Bulgarian, Ukrainian
            'Dokumenty',    # Czech, Polish, Slovak
            'Dokumenter',   # Danish, Norwegian
            'Έγγραφα',      # Greek
            'Dokumendid',   # Estonian
            'Asiakirjat',   # Finnish
            'מסמכים',       # Hebrew
            'Dokumenti',    # Croatian
            'Dokumentumok', # Hungarian
            'Skjöl',        # Icelandic
            'ドキュメント',     # Japanese
            '문서',          # Korean
            'Documenten',   # Dutch
            'Documente',    # Romanian
            'Dokument',     # Swedish
            'Belgeler',     # Turkish
            '文档',          # Chinese
        ]
        
        for name in possible_names:
            candidate = home / name
            if candidate.exists() and candidate.is_dir():
                return candidate
        
        # Fallback: create Documents if none exist
        documents_dir = home / 'Documentos'  # Default to Portuguese
        try:
            documents_dir.mkdir(exist_ok=True)
        except OSError:
            pass
        return documents_dir

    def _on_choose_location(self, button):
        """Handle location selection"""
        file_chooser = Gtk.FileChooserNative.new(
            _("Choose Export Location"),
            self,
            Gtk.FileChooserAction.SELECT_FOLDER,
            _("Select"),
            _("Cancel")
        )

        file_chooser.set_current_folder(Gio.File.new_for_path(str(self.selected_location)))
        file_chooser.connect('response', self._on_location_selected)
        file_chooser.show()

    def _on_location_selected(self, dialog, response):
        """Handle location selection response"""
        if response == Gtk.ResponseType.ACCEPT:
            folder = dialog.get_file()
            if folder:
                self.selected_location = folder.get_path()
                self.location_row.set_subtitle(str(self.selected_location))

    def _on_export_clicked(self, button):
        """Handle export button click"""
        button.set_sensitive(False)
        button.set_label(_("Exporting..."))
        
        # Get selected format
        selected_index = self.format_row.get_selected()
        format_code = self.format_data[selected_index]

        # Generate filename
        safe_name = FileHelper.get_safe_filename(self.project.name)
        filename = FileHelper.ensure_extension(safe_name, format_code)

        output_path = Path(self.selected_location) / filename

        # Ensure unique filename
        output_path = FileHelper.find_available_filename(output_path)

        # Store reference to button for cleanup
        self.export_button = button

        # Execute export in separate thread
        def export_thread():
            try:
                success = self.export_service.export_project(
                    self.project,
                    str(output_path),
                    format_code
                )
                
                # Use idle_add_once to prevent multiple callbacks
                GLib.idle_add(self._export_finished, success, str(output_path), None)
                
            except Exception as e:
                GLib.idle_add(self._export_finished, False, str(output_path), str(e))
        
        thread = threading.Thread(target=export_thread, daemon=True)
        thread.start()
    
    def _export_finished(self, success, output_path, error_message):
        """Callback executed in main thread when export finishes"""
        header = self.get_titlebar()
        if header:
            child = header.get_last_child()
            while child:
                if isinstance(child, Gtk.Button):
                    child.set_sensitive(True)
                    child.set_label(_("Export"))
                    break
                child = child.get_prev_sibling()
        
        if success:
            success_dialog = Adw.MessageDialog.new(
                self,
                _("Export Successful"),
                _("Project exported to:\n{}").format(output_path)
            )
            success_dialog.add_response("ok", _("OK"))
            
            def on_success_response(dialog, response):
                dialog.destroy()
                self.destroy()
            
            success_dialog.connect('response', on_success_response)
            success_dialog.present()
            
        else:
            error_msg = error_message if error_message else _("An error occurred while exporting the project.")
            error_dialog = Adw.MessageDialog.new(
                self,
                _("Export Failed"),
                error_msg
            )
            error_dialog.add_response("ok", _("OK"))
            error_dialog.present()
        
        return False


class PreferencesDialog(Adw.PreferencesWindow):
    """Preferences dialog"""

    __gtype_name__ = 'TacPreferencesDialog'

    def __init__(self, parent, config: Config, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("Preferences"))
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(700, 600)
        self.set_resizable(True)

        self.config = config

        self._create_ui()
        self._load_preferences()

    def _create_ui(self):
        """Create the preferences UI"""
        # General page
        general_page = Adw.PreferencesPage()
        general_page.set_title(_("General"))
        general_page.set_icon_name('preferences-system-symbolic')
        self.add(general_page)

        # Appearance group
        appearance_group = Adw.PreferencesGroup()
        appearance_group.set_title(_("Appearance"))
        general_page.add(appearance_group)

        # Dark theme
        self.dark_theme_row = Adw.SwitchRow()
        self.dark_theme_row.set_title(_("Dark Theme"))
        self.dark_theme_row.set_subtitle(_("Use dark theme for the application"))
        self.dark_theme_row.connect('notify::active', self._on_dark_theme_changed)
        appearance_group.add(self.dark_theme_row)

        # Editor page
        editor_page = Adw.PreferencesPage()
        editor_page.set_title(_("Editor"))
        editor_page.set_icon_name('accessories-text-editor-symbolic')
        self.add(editor_page)

        '''# Font group
        font_group = Adw.PreferencesGroup()
        font_group.set_title(_("Default Font"))
        editor_page.add(font_group)

        # Font family
        self.font_family_row = Adw.ComboRow()
        self.font_family_row.set_title(_("Font Family"))
        font_model = Gtk.StringList()

        # Get system fonts
        try:
            font_names = get_system_fonts()
        except Exception as e:
            print(_("Error loading system fonts: {}").format(e))
            font_names = ["Liberation Serif", "DejaVu Sans", "Ubuntu"]
        
        for font_name in font_names:
            font_model.append(font_name)

        self.font_family_row.set_model(font_model)
        self.font_family_row.connect('notify::selected', self._on_font_family_changed)
        font_group.add(self.font_family_row)

        # Font size
        adjustment = Gtk.Adjustment(value=12, lower=8, upper=72, step_increment=1, page_increment=2)
        self.font_size_row = Adw.SpinRow()
        self.font_size_row.set_title(_("Font Size"))
        self.font_size_row.set_adjustment(adjustment)
        self.font_size_row.connect('notify::value', self._on_font_size_changed)
        font_group.add(self.font_size_row)'''

        # Behavior group
        behavior_group = Adw.PreferencesGroup()
        behavior_group.set_title(_("Behavior"))
        editor_page.add(behavior_group)

        # Auto save
        self.auto_save_row = Adw.SwitchRow()
        self.auto_save_row.set_title(_("Auto Save"))
        self.auto_save_row.set_subtitle(_("Automatically save projects while editing"))
        self.auto_save_row.connect('notify::active', self._on_auto_save_changed)
        behavior_group.add(self.auto_save_row)

        # Word wrap
        self.word_wrap_row = Adw.SwitchRow()
        self.word_wrap_row.set_title(_("Word Wrap"))
        self.word_wrap_row.set_subtitle(_("Wrap text to fit the editor width"))
        self.word_wrap_row.connect('notify::active', self._on_word_wrap_changed)
        behavior_group.add(self.word_wrap_row)

        # Show line numbers
        self.line_numbers_row = Adw.SwitchRow()
        self.line_numbers_row.set_title(_("Show Line Numbers"))
        self.line_numbers_row.set_subtitle(_("Display line numbers in the editor"))
        self.line_numbers_row.connect('notify::active', self._on_line_numbers_changed)
        behavior_group.add(self.line_numbers_row)

        # AI assistant page
        ai_page = Adw.PreferencesPage()
        ai_page.set_title(_("AI Assistant"))
        ai_page.set_icon_name('applications-science-symbolic')
        self.add(ai_page)

        ai_group = Adw.PreferencesGroup()
        ai_group.set_title(_("Assistant Settings"))
        ai_group.set_description(
            _("Configure the provider and credentials used to generate suggestions.")
        )
        ai_page.add(ai_group)

        self.ai_enabled_row = Adw.SwitchRow(
            title=_("Enable AI Assistant"),
            subtitle=_("Allow prompts to use an external provider (Ctrl+Shift+I)."),
        )
        self.ai_enabled_row.connect("notify::active", self._on_ai_enabled_changed)
        ai_group.add(self.ai_enabled_row)

        self.ai_provider_row = Adw.ComboRow()
        self.ai_provider_row.set_title(_("Provider"))
        self._ai_provider_options = [
            ("gemini", "Gemini"),
            ("openrouter", "OpenRouter.ai"),
        ]
        provider_model = Gtk.StringList.new([label for _pid, label in self._ai_provider_options])
        self.ai_provider_row.set_model(provider_model)
        self.ai_provider_row.connect("notify::selected", self._on_ai_provider_changed)
        ai_group.add(self.ai_provider_row)

        self.ai_model_row = Adw.ActionRow(
            title=_("Model Identifier"),
            subtitle=_("Examples:gemini-2.5-flash."),
        )
        self.ai_model_entry = Gtk.Entry()
        self.ai_model_entry.set_placeholder_text(_("gemini-2.5-flash"))
        self.ai_model_entry.connect("changed", self._on_ai_model_changed)
        self.ai_model_row.add_suffix(self.ai_model_entry)
        self.ai_model_row.set_activatable_widget(self.ai_model_entry)
        ai_group.add(self.ai_model_row)

        self.ai_api_key_row = Adw.ActionRow(
            title=_("API Key"),
            subtitle=_("Stored locally and used to authenticate requests."),
        )
        self.ai_api_key_entry = Gtk.PasswordEntry(
            placeholder_text=_("Paste your API key"),
            show_peek_icon=True,
            hexpand=True,
        )
        self.ai_api_key_entry.connect("changed", self._on_ai_api_key_changed)
        self.ai_api_key_row.add_suffix(self.ai_api_key_entry)
        self.ai_api_key_row.set_activatable_widget(self.ai_api_key_entry)
        ai_group.add(self.ai_api_key_row)

        self.ai_openrouter_site_row = Adw.ActionRow(
            title=_("Site URL (optional)"),
            subtitle=_("Used as HTTP Referer header for OpenRouter rankings."),
        )
        self.ai_openrouter_site_entry = Gtk.Entry(
            placeholder_text=_("https://example.com"),
        )
        self.ai_openrouter_site_entry.connect(
            "changed", self._on_openrouter_site_url_changed
        )
        self.ai_openrouter_site_row.add_suffix(self.ai_openrouter_site_entry)
        self.ai_openrouter_site_row.set_activatable_widget(
            self.ai_openrouter_site_entry
        )
        ai_group.add(self.ai_openrouter_site_row)

        self.ai_openrouter_title_row = Adw.ActionRow(
            title=_("Site title (optional)"),
            subtitle=_("Sent via X-Title header for OpenRouter rankings."),
        )
        self.ai_openrouter_title_entry = Gtk.Entry(
            placeholder_text=_("My Project"),
        )
        self.ai_openrouter_title_entry.connect(
            "changed", self._on_openrouter_site_name_changed
        )
        self.ai_openrouter_title_row.add_suffix(self.ai_openrouter_title_entry)
        self.ai_openrouter_title_row.set_activatable_widget(
            self.ai_openrouter_title_entry
        )
        ai_group.add(self.ai_openrouter_title_row)

        self._ai_config_widgets = [
            self.ai_provider_row,
            self.ai_model_row,
            self.ai_model_entry,
            self.ai_api_key_row,
            self.ai_api_key_entry,
            self.ai_openrouter_site_row,
            self.ai_openrouter_site_entry,
            self.ai_openrouter_title_row,
            self.ai_openrouter_title_entry,
        ]

    def _load_preferences(self):
        """Load preferences from config"""
        try:
            # Appearance
            self.dark_theme_row.set_active(self.config.get('use_dark_theme', False))

            # Font
            font_family = self.config.get('font_family', 'Liberation Serif')
            model = self.font_family_row.get_model()
            for i in range(model.get_n_items()):
                if model.get_string(i) == font_family:
                    self.font_family_row.set_selected(i)
                    break

            self.font_size_row.set_value(self.config.get('font_size', 12))

            # Behavior
            self.auto_save_row.set_active(self.config.get('auto_save', True))
            self.word_wrap_row.set_active(self.config.get('word_wrap', True))
            self.line_numbers_row.set_active(self.config.get('show_line_numbers', True))
            self.ai_enabled_row.set_active(self.config.get_ai_assistant_enabled())
            provider = self.config.get_ai_assistant_provider()
            provider_ids = [pid for pid, _label in self._ai_provider_options]
            try:
                self.ai_provider_row.set_selected(provider_ids.index(provider))
            except ValueError:
                self.ai_provider_row.set_selected(0)
                provider = provider_ids[0]
            self.ai_model_entry.set_text(self.config.get_ai_assistant_model() or "")
            self.ai_api_key_entry.set_text(self.config.get_ai_assistant_api_key() or "")
            self.ai_openrouter_site_entry.set_text(self.config.get_openrouter_site_url() or "")
            self.ai_openrouter_title_entry.set_text(self.config.get_openrouter_site_name() or "")
            self._update_ai_controls_sensitive(self.config.get_ai_assistant_enabled())
            self._update_ai_provider_ui(provider)
            
        except Exception as e:
            print(_("Error loading preferences: {}").format(e))

    def _on_dark_theme_changed(self, switch, pspec):
        """Handle dark theme toggle"""
        try:
            self.config.set('use_dark_theme', switch.get_active())

            # Apply theme immediately
            style_manager = Adw.StyleManager.get_default()
            if switch.get_active():
                style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            else:
                style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
        except Exception as e:
            print(_("Error changing theme: {}").format(e))

    def _on_font_family_changed(self, combo, pspec):
        """Handle font family change"""
        try:
            model = combo.get_model()
            selected_font = model.get_string(combo.get_selected())
            self.config.set('font_family', selected_font)
        except Exception as e:
            print(_("Error changing font family: {}").format(e))

    def _on_font_size_changed(self, spin, pspec):
        """Handle font size change"""
        try:
            self.config.set('font_size', int(spin.get_value()))
        except Exception as e:
            print(_("Error changing font size: {}").format(e))

    def _on_auto_save_changed(self, switch, pspec):
        """Handle auto save toggle"""
        try:
            self.config.set('auto_save', switch.get_active())
        except Exception as e:
            print(_("Error changing auto save: {}").format(e))

    def _on_word_wrap_changed(self, switch, pspec):
        """Handle word wrap toggle"""
        try:
            self.config.set('word_wrap', switch.get_active())
        except Exception as e:
            print(_("Error changing word wrap: {}").format(e))

    def _on_line_numbers_changed(self, switch, pspec):
        """Handle line numbers toggle"""
        try:
            self.config.set('show_line_numbers', switch.get_active())
        except Exception as e:
            print(_("Error changing line numbers: {}").format(e))

    def _on_ai_enabled_changed(self, switch, pspec):
        enabled = switch.get_active()
        self.config.set_ai_assistant_enabled(enabled)
        self._update_ai_controls_sensitive(enabled)

    def _on_ai_provider_changed(self, combo_row, pspec):
        index = combo_row.get_selected()
        if 0 <= index < len(self._ai_provider_options):
            provider_id = self._ai_provider_options[index][0]
            self.config.set_ai_assistant_provider(provider_id)
            self._update_ai_provider_ui(provider_id)

    def _on_ai_model_changed(self, entry):
        self.config.set_ai_assistant_model(entry.get_text().strip())

    def _on_ai_api_key_changed(self, entry):
        self.config.set_ai_assistant_api_key(entry.get_text().strip())

    def _on_openrouter_site_url_changed(self, entry):
        self.config.set_openrouter_site_url(entry.get_text().strip())

    def _on_openrouter_site_name_changed(self, entry):
        self.config.set_openrouter_site_name(entry.get_text().strip())

    def _update_ai_controls_sensitive(self, enabled: bool) -> None:
        for widget in getattr(self, "_ai_config_widgets", []):
            widget.set_sensitive(enabled)

    def _update_ai_provider_ui(self, provider: str) -> None:
        # Se o provider vier vazio ou inválido (ex: antigo groq), define um padrão
        if not provider or provider == "groq":
            provider = "gemini"

        if provider == "gemini":
            self.ai_model_entry.set_placeholder_text("gemini-2.5-flash")
            self.ai_model_row.set_subtitle(
                _("Gemini model identifier (for example: gemini-2.5-flash).")
            )
            self.ai_api_key_row.set_subtitle(_("Google AI Studio API key."))
            self.ai_openrouter_site_row.set_visible(False)
            self.ai_openrouter_title_row.set_visible(False)
        
        elif provider == "openrouter":
            self.ai_model_entry.set_placeholder_text("x-ai/grok-4.1-fast:free")
            self.ai_model_row.set_subtitle(
                _("OpenRouter model identifier (for example: x-ai/grok-4.1-fast:free).")
            )
            self.ai_api_key_row.set_subtitle(_("OpenRouter API key."))
            self.ai_openrouter_site_row.set_visible(True)
            self.ai_openrouter_title_row.set_visible(True)
        
        else:
            # Fallback genérico
            self.ai_model_entry.set_placeholder_text(_("model-name"))
            self.ai_model_row.set_subtitle(
                _("Model identifier required by the selected provider.")
            )
            self.ai_api_key_row.set_subtitle(_("API key used to authenticate requests."))
            self.ai_openrouter_site_row.set_visible(False)
            self.ai_openrouter_title_row.set_visible(False)


class WelcomeDialog(Adw.Window):
    """Welcome dialog explaining TAC Writer and CAT technique"""

    __gtype_name__ = 'TacWelcomeDialog'

    __gsignals__ = {
        'dialog-closed': (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, parent, config: Config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_resizable(True)
        self.config = config

        # Smaller window size since we removed content
        self.set_default_size(600, 500)

        # Create UI
        self._create_ui()

    def _create_ui(self):
        """Create the welcome dialog UI"""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # HeaderBar with custom style
        headerbar = Adw.HeaderBar()
        headerbar.set_show_title(False)
        headerbar.add_css_class("flat")

        # Apply custom CSS to reduce header padding
        try:
            css_provider = Gtk.CssProvider()
            css_provider.load_from_data(b"""
            headerbar {
                min-height: 24px;
                padding: 2px 6px;
            }
            """)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
        except Exception as e:
            print(_("Error applying welcome dialog CSS: {}").format(e))

        main_box.append(headerbar)

        # ScrolledWindow for content
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_vexpand(True)

        # Content container
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content_box.set_margin_top(8)
        content_box.set_margin_bottom(16)
        content_box.set_margin_start(20)
        content_box.set_margin_end(20)

        # Icon and title
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title_box.set_halign(Gtk.Align.CENTER)

        # App icon
        icon = Gtk.Image.new_from_icon_name('document-edit-symbolic')
        icon.set_pixel_size(56)
        icon.add_css_class("accent")
        title_box.append(icon)

        # Title
        title_label = Gtk.Label()
        title_label.set_markup("<span size='large' weight='bold'>" + _("What is TAC Writer?") + "</span>")
        title_label.set_halign(Gtk.Align.CENTER)
        title_box.append(title_label)

        content_box.append(title_box)

        # Content text
        content_text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        # CAT explanation
        cat_label = Gtk.Label()
        cat_label.set_markup("<b>" + _("Continuous Argumentation Technique (TAC in Portuguese):") + "</b>")
        cat_label.set_halign(Gtk.Align.START)
        content_text_box.append(cat_label)

        cat_desc = Gtk.Label()
        cat_desc.set_text(_("Tac Writer is a tool based on the TAC technique (Continued Argumentation Technique) and the Pomodoro method. TAC technique helps writers develop an idea in an organized manner, separating the paragraph into different stages. Read wiki to take advantage of all the resources. To open wiki click on '?' icon"))
        cat_desc.set_wrap(True)
        cat_desc.set_halign(Gtk.Align.CENTER)
        cat_desc.set_justify(Gtk.Justification.LEFT)
        cat_desc.set_max_width_chars(60)
        content_text_box.append(cat_desc)

        # Wiki link section
        wiki_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        wiki_box.set_halign(Gtk.Align.CENTER)
        wiki_box.set_margin_top(16)

        wiki_button = Gtk.Button()
        wiki_button.set_label(_("Learn More - Online Documentation"))
        wiki_button.set_icon_name('help-browser-symbolic')
        wiki_button.add_css_class("suggested-action")
        wiki_button.add_css_class("wiki-help-button")
        wiki_button.set_tooltip_text(_("Access the complete guide and tutorials"))
        wiki_button.connect('clicked', self._on_wiki_clicked)
        wiki_box.append(wiki_button)

        content_text_box.append(wiki_box)
        content_box.append(content_text_box)

        # Separator before switch
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(8)
        content_box.append(separator)

        # Show on startup toggle
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        toggle_box.set_margin_top(8)

        toggle_label = Gtk.Label()
        toggle_label.set_text(_("Show this dialog on startup"))
        toggle_label.set_hexpand(True)
        toggle_label.set_halign(Gtk.Align.START)
        toggle_box.append(toggle_label)

        self.show_switch = Gtk.Switch()
        self.show_switch.set_active(self.config.get('show_welcome_dialog', True))
        self.show_switch.connect('notify::active', self._on_switch_toggled)
        self.show_switch.set_valign(Gtk.Align.CENTER)
        toggle_box.append(self.show_switch)
        content_box.append(toggle_box)

        # Start button
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(16)

        start_button = Gtk.Button()
        start_button.set_label(_("Let's Start"))
        start_button.add_css_class("suggested-action")
        start_button.connect('clicked', self._on_start_clicked)
        button_box.append(start_button)

        content_box.append(button_box)

        # Add content_box to ScrolledWindow
        scrolled_window.set_child(content_box)
        main_box.append(scrolled_window)

        # Set the content
        self.set_content(main_box)

    def _on_switch_toggled(self, switch, gparam):
        """Handle switch toggle"""
        try:
            self.config.set('show_welcome_dialog', switch.get_active())
            self.config.save()
        except Exception as e:
            print(_("Error saving welcome dialog preference: {}").format(e))

    def _on_start_clicked(self, button):
        """Handle start button click"""
        # Emit signal before destroying
        self.emit('dialog-closed')
        self.destroy()
        
    def _on_wiki_clicked(self, button):
        """Handle wiki button click - open external browser"""
        import webbrowser
        
        wiki_url = "https://github.com/big-comm/comm-tac-writer/wiki"
        
        try:
            # Try to open with default browser
            webbrowser.open(wiki_url)
        except Exception:
            # Fallback: try xdg-open on Linux
            try:
                subprocess.run(['xdg-open', wiki_url], check=False)
            except Exception as e:
                print(_("Could not open wiki URL: {}").format(e))


def AboutDialog(parent):
    """Create and show about dialog"""
    dialog = Adw.AboutWindow()
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    # Get config instance to access version info
    config = Config()

    # Application information
    dialog.set_application_name(config.APP_NAME)
    dialog.set_application_icon("tac-writer")
    dialog.set_version(config.APP_VERSION)
    dialog.set_developer_name(_(config.APP_DESCRIPTION))
    dialog.set_website(config.APP_WEBSITE)

    # Description
    dialog.set_comments(_(config.APP_DESCRIPTION))

    # License
    dialog.set_license_type(Gtk.License.GPL_3_0)

    # Credits
    dialog.set_developers([
        f"{', '.join(config.APP_DEVELOPERS)} {config.APP_WEBSITE}"
    ])
    dialog.set_designers(config.APP_DESIGNERS)

    dialog.set_copyright(config.APP_COPYRIGHT)

    return dialog


class BackupManagerDialog(Adw.Window):
    """Dialog for managing database backups"""

    __gtype_name__ = 'TacBackupManagerDialog'

    __gsignals__ = {
        'database-imported': (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, parent, project_manager: ProjectManager, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("Backup Manager"))
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(700, 500)
        self.set_resizable(True)

        self.project_manager = project_manager
        self.backups_list = []

        self._create_ui()
        self._refresh_backups()

    def _create_ui(self):
        """Create the backup manager UI"""
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content_box)

        # Header bar
        header_bar = Adw.HeaderBar()
        
        # Close button
        close_button = Gtk.Button()
        close_button.set_label(_("Close"))
        close_button.connect('clicked', lambda x: self.destroy())
        header_bar.pack_start(close_button)

        # Create backup button
        create_backup_button = Gtk.Button()
        create_backup_button.set_label(_("Create Backup"))
        create_backup_button.add_css_class("suggested-action")
        create_backup_button.connect('clicked', self._on_create_backup)
        header_bar.pack_end(create_backup_button)

        # Import button
        import_button = Gtk.Button()
        import_button.set_label(_("Import Database"))
        import_button.connect('clicked', self._on_import_database)
        header_bar.pack_end(import_button)

        content_box.append(header_bar)

        # Main content
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)
        main_box.set_spacing(16)

        # Status group
        status_group = Adw.PreferencesGroup()
        status_group.set_title(_("Current Database"))
        
        try:
            db_info = self.project_manager.get_database_info()
        except Exception as e:
            print(_("Error getting database info: {}").format(e))
            db_info = {
                'database_path': 'Unknown',
                'database_size_bytes': 0,
                'project_count': 0
            }
        
        # Database path
        path_row = Adw.ActionRow()
        path_row.set_title(_("Database Location"))
        path_row.set_subtitle(db_info['database_path'])
        status_group.add(path_row)

        # Database stats
        stats_row = Adw.ActionRow()
        stats_row.set_title(_("Statistics"))
        stats_text = _("{} projects, {} MB").format(
            db_info['project_count'],
            round(db_info['database_size_bytes'] / (1024*1024), 2)
        )
        stats_row.set_subtitle(stats_text)
        status_group.add(stats_row)

        main_box.append(status_group)

        # Backups list
        backups_group = Adw.PreferencesGroup()
        backups_group.set_title(_("Available Backups"))
        backups_group.set_description(_("Backups are stored in Documents/TAC Projects/database_backups"))

        # Scrolled window for backups
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(200)

        self.backups_listbox = Gtk.ListBox()
        self.backups_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.backups_listbox.add_css_class("boxed-list")

        scrolled.set_child(self.backups_listbox)
        
        backups_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        backups_box.append(backups_group)
        backups_box.append(scrolled)
        
        main_box.append(backups_box)
        
        scrolled_main = Gtk.ScrolledWindow()
        scrolled_main.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_main.set_child(main_box)
        content_box.append(scrolled_main)

    def _refresh_backups(self):
        """Refresh the backups list"""
        # Clear existing items
        child = self.backups_listbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.backups_listbox.remove(child)
            child = next_child

        # Load backups
        try:
            self.backups_list = self.project_manager.list_available_backups()
        except Exception as e:
            print(_("Error listing backups: {}").format(e))
            self.backups_list = []

        if not self.backups_list:
            # Show empty state
            empty_row = Adw.ActionRow()
            empty_row.set_title(_("No backups found"))
            empty_row.set_subtitle(_("Create a backup or import an existing database file"))
            self.backups_listbox.append(empty_row)
            return

        # Add backup rows
        for backup in self.backups_list:
            row = self._create_backup_row(backup)
            self.backups_listbox.append(row)

    def _create_backup_row(self, backup: Dict[str, Any]):
        """Create a row for a backup"""
        row = Adw.ActionRow()
        
        # Title and subtitle
        row.set_title(backup['name'])
        
        size_mb = backup['size'] / (1024 * 1024)
        created_str = backup['created_at'].strftime('%Y-%m-%d %H:%M')
        subtitle = _("{:.1f} MB • {} projects • {}").format(
            size_mb, backup['project_count'], created_str
        )
        row.set_subtitle(subtitle)

        # Status indicator
        if backup['is_valid']:
            status_icon = Gtk.Image.new_from_icon_name('emblem-ok-symbolic')
            status_icon.set_tooltip_text(_("Valid backup"))
        else:
            status_icon = Gtk.Image.new_from_icon_name('dialog-warning-symbolic')
            status_icon.set_tooltip_text(_("Invalid or corrupted backup"))
            status_icon.add_css_class("warning")

        row.add_prefix(status_icon)

        # Action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Restore button
        if backup['is_valid']:
            restore_button = Gtk.Button()
            restore_button.set_icon_name('document-revert-symbolic')
            restore_button.set_tooltip_text(_("Import this backup"))
            restore_button.add_css_class("flat")
            restore_button.connect('clicked', lambda btn, b=backup: self._on_restore_backup(b))
            button_box.append(restore_button)

        # Delete button
        delete_button = Gtk.Button()
        delete_button.set_icon_name('user-trash-symbolic')
        delete_button.set_tooltip_text(_("Delete backup"))
        delete_button.add_css_class("flat")
        delete_button.add_css_class("destructive-action")
        delete_button.connect('clicked', lambda btn, b=backup: self._on_delete_backup(b))
        button_box.append(delete_button)

        row.add_suffix(button_box)
        return row

    def _on_create_backup(self, button):
        """Handle create backup button"""
        button.set_sensitive(False)
        button.set_label(_("Creating..."))

        def backup_thread():
            try:
                backup_path = self.project_manager.create_manual_backup()
                GLib.idle_add(self._backup_created, backup_path, button)
            except Exception as e:
                print(_("Error in backup thread: {}").format(e))
                GLib.idle_add(self._backup_created, None, button)

        thread = threading.Thread(target=backup_thread, daemon=True)
        thread.start()

    def _backup_created(self, backup_path, button):
        """Callback when backup is created"""
        button.set_sensitive(True)
        button.set_label(_("Create Backup"))

        if backup_path:
            # Show success toast in parent window
            parent_window = self.get_transient_for()
            if parent_window and hasattr(parent_window, '_show_toast'):
                parent_window._show_toast(_("Backup created successfully"))
            self._refresh_backups()
        else:
            # Show error dialog
            error_dialog = Adw.MessageDialog.new(
                self,
                _("Backup Failed"),
                _("Could not create backup. Check the console for details.")
            )
            error_dialog.add_response("ok", _("OK"))
            error_dialog.present()

        return False

    def _on_import_database(self, button):
        """Handle import database button"""
        file_chooser = Gtk.FileChooserNative.new(
            _("Import Database"),
            self,
            Gtk.FileChooserAction.OPEN,
            _("Import"),
            _("Cancel")
        )

        # Set filter for database files
        filter_db = Gtk.FileFilter()
        filter_db.set_name(_("Database files (*.db)"))
        filter_db.add_pattern("*.db")
        file_chooser.add_filter(filter_db)

        filter_all = Gtk.FileFilter()
        filter_all.set_name(_("All files"))
        filter_all.add_pattern("*")
        file_chooser.add_filter(filter_all)

        file_chooser.connect('response', self._on_import_file_selected)
        file_chooser.show()

    def _on_import_file_selected(self, dialog, response):
        """Handle file selection for import"""
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                backup_path = Path(file.get_path())
                self._confirm_import(backup_path)
        dialog.destroy()

    def _on_restore_backup(self, backup):
        """Handle restore backup button"""
        self._confirm_import(backup['path'])

    def _confirm_import(self, backup_path: Path):
        """Show confirmation dialog for import"""
        # Validate backup first
        try:
            if not self.project_manager._validate_backup_file(backup_path):
                error_dialog = Adw.MessageDialog.new(
                    self,
                    _("Invalid Backup"),
                    _("The selected file is not a valid TAC database backup.")
                )
                error_dialog.add_response("ok", _("OK"))
                error_dialog.present()
                return
        except Exception as e:
            print(_("Error validating backup: {}").format(e))
            return

        # Get backup info
        try:
            with sqlite3.connect(backup_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM projects")
                project_count = cursor.fetchone()[0]
        except sqlite3.Error as e:
            print(_("Error reading backup info: {}").format(e))
            project_count = 0

        # Show confirmation
        dialog = Adw.MessageDialog.new(
            self,
            _("Import Database?"),
            _("This will replace your current database with the selected backup.\n\n"
              "The backup contains {} projects.\n\n"
              "Your current database will be backed up before importing.").format(project_count)
        )

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("import", _("Import"))
        dialog.set_response_appearance("import", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")

        dialog.connect('response', lambda d, r, path=backup_path: self._import_confirmed(d, r, path))
        dialog.present()

    def _import_confirmed(self, dialog, response, backup_path):
        """Handle import confirmation"""
        dialog.destroy()
        
        if response == "import":
            self._perform_import(backup_path)

    def _perform_import(self, backup_path: Path):
        """Perform the database import"""
        # Show loading state
        loading_dialog = Adw.MessageDialog.new(
            self,
            _("Importing Database"),
            _("Please wait while the database is being imported...")
        )
        loading_dialog.present()

        def import_thread():
            try:
                success = self.project_manager.import_database(backup_path)
                GLib.idle_add(self._import_finished, success, loading_dialog)
            except Exception as e:
                print(_("Error in import thread: {}").format(e))
                GLib.idle_add(self._import_finished, False, loading_dialog)

        thread = threading.Thread(target=import_thread, daemon=True)
        thread.start()

    def _import_finished(self, success, loading_dialog):
        """Callback when import is finished"""
        loading_dialog.destroy()

        if success:
            # Show success and emit signal
            success_dialog = Adw.MessageDialog.new(
                self,
                _("Import Successful"),
                _("Database imported successfully. The application will refresh to show the imported projects.")
            )
            success_dialog.add_response("ok", _("OK"))
            
            def on_success_response(dialog, response):
                dialog.destroy()
                self.emit('database-imported')
                self.destroy()
            
            success_dialog.connect('response', on_success_response)
            success_dialog.present()
        else:
            # Show error
            error_dialog = Adw.MessageDialog.new(
                self,
                _("Import Failed"),
                _("Could not import the database. Your current database remains unchanged.")
            )
            error_dialog.add_response("ok", _("OK"))
            error_dialog.present()

        return False

    def _on_delete_backup(self, backup):
        """Handle delete backup button"""
        dialog = Adw.MessageDialog.new(
            self,
            _("Delete Backup?"),
            _("Are you sure you want to delete '{}'?\n\nThis action cannot be undone.").format(backup['name'])
        )

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")

        dialog.connect('response', lambda d, r, b=backup: self._delete_confirmed(d, r, b))
        dialog.present()

    def _delete_confirmed(self, dialog, response, backup):
        """Handle delete confirmation"""
        if response == "delete":
            try:
                success = self.project_manager.delete_backup(backup['path'])
                if success:
                    self._refresh_backups()
            except Exception as e:
                print(_("Error deleting backup: {}").format(e))
        dialog.destroy()


class ImageDialog(Adw.Window):
    """Dialog for adding images to the document"""

    __gtype_name__ = 'TacImageDialog'

    __gsignals__ = {
        'image-added': (GObject.SIGNAL_RUN_FIRST, None, (object,)),
        'image-updated': (GObject.SIGNAL_RUN_FIRST, None, (object,)),
    }

    def __init__(self, parent, project, insert_after_index: int = -1, edit_paragraph=None, **kwargs):
        super().__init__(**kwargs)

        self.edit_mode = edit_paragraph is not None
        self.edit_paragraph = edit_paragraph

        if self.edit_mode:
            self.set_title(_("Edit Image"))
        else:
            self.set_title(_("Insert Image"))

        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(700, 600)
        self.set_resizable(True)

        self.project = project
        self.insert_after_index = insert_after_index
        self.selected_file = None
        self.image_preview = None
        self.original_size = None

        self.config = Config()

        # Create UI
        self._create_ui()

        # If editing, load existing image data
        if self.edit_mode:
            self._load_existing_image()

    def _create_ui(self):
        """Create the dialog UI"""
        # Main content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content_box)

        # Header bar
        header_bar = Adw.HeaderBar()
        header_bar.set_show_end_title_buttons(False)

        # Cancel button
        cancel_button = Gtk.Button(label=_("Cancel"))
        cancel_button.connect('clicked', lambda b: self.destroy())
        header_bar.pack_start(cancel_button)

        # Insert/Update button
        button_label = _("Update") if self.edit_mode else _("Insert")
        self.insert_button = Gtk.Button(label=button_label)
        self.insert_button.add_css_class('suggested-action')
        self.insert_button.set_sensitive(self.edit_mode)  # Enabled in edit mode by default
        self.insert_button.connect('clicked', self._on_insert_clicked)
        header_bar.pack_end(self.insert_button)

        content_box.append(header_bar)

        # Scrolled window for content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content_box.append(scrolled)

        # Main content box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        scrolled.set_child(main_box)

        # File selection group
        file_group = Adw.PreferencesGroup()
        file_group.set_title(_("Image File"))
        file_group.set_description(_("Select an image file to insert into your document"))
        main_box.append(file_group)

        # File chooser button
        file_button_row = Adw.ActionRow()
        file_button_row.set_title(_("Select Image"))
        self.file_label = Gtk.Label(label=_("No file selected"))
        self.file_label.add_css_class('dim-label')
        file_button_row.add_suffix(self.file_label)
        
        choose_button = Gtk.Button(label=_("Browse..."))
        choose_button.set_valign(Gtk.Align.CENTER)
        choose_button.connect('clicked', self._on_choose_file)
        file_button_row.add_suffix(choose_button)
        file_group.add(file_button_row)

        # Image preview
        self.preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.preview_box.set_visible(False)
        main_box.append(self.preview_box)

        preview_label = Gtk.Label()
        preview_label.set_markup(f"<b>{_('Preview')}</b>")
        preview_label.set_xalign(0)
        self.preview_box.append(preview_label)

        # Preview frame
        preview_frame = Gtk.Frame()
        preview_frame.set_halign(Gtk.Align.CENTER)
        self.preview_box.append(preview_frame)

        self.preview_image = Gtk.Picture()
        self.preview_image.set_can_shrink(True)
        self.preview_image.set_content_fit(Gtk.ContentFit.CONTAIN)
        preview_frame.set_child(self.preview_image)

        # Image info label
        self.info_label = Gtk.Label()
        self.info_label.add_css_class('dim-label')
        self.info_label.set_xalign(0)
        self.preview_box.append(self.info_label)

        # Formatting group
        self.format_group = Adw.PreferencesGroup()
        self.format_group.set_title(_("Image Formatting"))
        self.format_group.set_visible(False)
        main_box.append(self.format_group)

        # Width adjustment
        width_row = Adw.ActionRow()
        width_row.set_title(_("Display Width (%)"))
        width_row.set_subtitle(_("Percentage of page width"))
        
        width_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        width_box.set_valign(Gtk.Align.CENTER)
        
        self.width_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 100, 5)
        self.width_scale.set_value(80)
        self.width_scale.set_draw_value(True)
        self.width_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.width_scale.set_hexpand(True)
        self.width_scale.set_size_request(200, -1)
        width_box.append(self.width_scale)
        
        width_row.add_suffix(width_box)
        self.format_group.add(width_row)

        # Alignment selection
        alignment_row = Adw.ActionRow()
        alignment_row.set_title(_("Alignment"))
        alignment_row.set_subtitle(_("Image position on the page"))
        
        alignment_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        alignment_box.set_valign(Gtk.Align.CENTER)
        
        self.alignment_group = None
        alignments = [
            ('left', _("Left")),
            ('center', _("Center")),
            ('right', _("Right"))
        ]
        
        for value, label in alignments:
            radio = Gtk.CheckButton(label=label)
            if self.alignment_group is None:
                self.alignment_group = radio
                radio.set_active(True)  # Center is default
            else:
                radio.set_group(self.alignment_group)
                if value == 'center':
                    radio.set_active(True)
            
            radio.alignment_value = value
            alignment_box.append(radio)
        
        alignment_row.add_suffix(alignment_box)
        self.format_group.add(alignment_row)

        # Caption entry
        caption_row = Adw.EntryRow()
        caption_row.set_title(_("Caption (optional)"))
        self.caption_entry = caption_row
        self.format_group.add(caption_row)

        # Alt text entry
        alt_row = Adw.EntryRow()
        alt_row.set_title(_("Alternative Text (optional)"))
        alt_row.set_show_apply_button(False)
        self.alt_entry = alt_row
        self.format_group.add(alt_row)

        # Position group
        self.position_group = Adw.PreferencesGroup()
        self.position_group.set_title(_("Position in Document"))
        self.position_group.set_visible(False)
        main_box.append(self.position_group)

        # Position selection
        position_row = Adw.ActionRow()
        position_row.set_title(_("Insert After"))
        position_row.set_subtitle(_("Choose where to place the image"))
        
        self.position_dropdown = Gtk.DropDown()
        self.position_dropdown.set_valign(Gtk.Align.CENTER)
        position_row.add_suffix(self.position_dropdown)
        self.position_group.add(position_row)
        
        self._update_position_list()

    def _update_position_list(self):
        """Update the position dropdown with current paragraphs"""
        options = [_("Beginning of document")]
        
        for i, para in enumerate(self.project.paragraphs):
            from core.models import ParagraphType
            
            if para.type == ParagraphType.TITLE_1:
                text = f"📑 {para.content[:30]}"
            elif para.type == ParagraphType.TITLE_2:
                text = f"  📄 {para.content[:30]}"
            elif para.type == ParagraphType.IMAGE:
                text = f"🖼️ {_('Image')}"
            else:
                content_preview = para.content[:30] if para.content else _("(empty)")
                text = f"  {content_preview}"
            
            if len(para.content) > 30:
                text += "..."
            
            options.append(text)
        
        string_list = Gtk.StringList()
        for option in options:
            string_list.append(option)
        
        self.position_dropdown.set_model(string_list)
        
        # Set default position
        if self.insert_after_index >= 0 and self.insert_after_index < len(options) - 1:
            self.position_dropdown.set_selected(self.insert_after_index + 1)
        else:
            self.position_dropdown.set_selected(0)

    def _on_choose_file(self, button):
        """Handle file chooser button click"""
        file_filter = Gtk.FileFilter()
        file_filter.set_name(_("Image Files"))
        file_filter.add_mime_type("image/png")
        file_filter.add_mime_type("image/jpeg")
        file_filter.add_mime_type("image/webp")
        file_filter.add_pattern("*.png")
        file_filter.add_pattern("*.jpg")
        file_filter.add_pattern("*.jpeg")
        file_filter.add_pattern("*.webp")
        
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(file_filter)
        
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Select Image"))
        dialog.set_filters(filters)
        dialog.set_default_filter(file_filter)
        
        dialog.open(self, None, self._on_file_selected)

    def _on_file_selected(self, dialog, result):
        """Handle file selection"""
        try:
            file = dialog.open_finish(result)
            if file:
                file_path = file.get_path()
                self._load_image(file_path)
        except Exception as e:
            print(_("Error selecting file: {}").format(e))

    def _load_image(self, file_path: str):
        """Load and display the selected image"""
        try:
            from PIL import Image
            import os
            
            # Store file info
            self.selected_file = Path(file_path)
            
            # Update file label
            self.file_label.set_text(self.selected_file.name)
            self.file_label.remove_css_class('dim-label')
            
            # Load image to get dimensions
            with Image.open(file_path) as img:
                self.original_size = img.size
                
                # Get file size
                file_size = os.path.getsize(file_path) / 1024  # KB
                
                # Update info label
                info_text = _("Size: {} x {} pixels  •  {:.1f} KB").format(
                    self.original_size[0], 
                    self.original_size[1],
                    file_size
                )
                self.info_label.set_text(info_text)
            
            # Load preview
            texture = Gdk.Texture.new_from_filename(file_path)
            self.preview_image.set_paintable(texture)
            self.preview_image.set_size_request(400, 300)
            
            # Show preview and formatting options
            self.preview_box.set_visible(True)
            self.format_group.set_visible(True)
            self.position_group.set_visible(True)
            self.insert_button.set_sensitive(True)
            
        except Exception as e:
            print(_("Error loading image: {}").format(e))
            # Show error dialog
            error_dialog = Adw.MessageDialog.new(
                self,
                _("Error Loading Image"),
                _("Could not load the selected image file.") + "\n\n" + str(e)
            )
            error_dialog.add_response("ok", _("OK"))
            error_dialog.present()

    def _get_selected_alignment(self):
        """Get the selected alignment value"""
        for child in self.alignment_group.get_parent().observe_children():
            radio = child
            if hasattr(radio, 'alignment_value') and radio.get_active():
                return radio.alignment_value
        
        # Fallback: iterate differently
        alignment_box = self.alignment_group.get_parent()
        child = alignment_box.get_first_child()
        while child:
            if isinstance(child, Gtk.CheckButton) and child.get_active():
                if hasattr(child, 'alignment_value'):
                    return child.alignment_value
            child = child.get_next_sibling()
        
        return 'center'  # Default

    def _on_insert_clicked(self, button):
        """Handle insert/update button click"""
        try:
            # In edit mode, we can update without selecting a new file
            # In insert mode, we need a file selected
            if not self.edit_mode and (not self.selected_file or not self.original_size):
                return

            # Determine image file info
            if self.selected_file:
                # New image selected - copy to project directory
                images_dir = self.config.data_dir / 'images' / self.project.id
                images_dir.mkdir(parents=True, exist_ok=True)

                import shutil
                dest_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.selected_file.name}"
                dest_path = images_dir / dest_filename
                shutil.copy2(self.selected_file, dest_path)

                img_filename = dest_filename
                img_path = str(dest_path)
                img_original_size = self.original_size
            elif self.edit_mode:
                # No new image - keep existing image
                existing_metadata = self.edit_paragraph.get_image_metadata()
                img_filename = existing_metadata.get('filename')
                img_path = existing_metadata.get('path')
                img_original_size = existing_metadata.get('original_size')
            else:
                return

            # Calculate display size based on width percentage
            width_percent = self.width_scale.get_value()
            display_width = int(img_original_size[0] * (width_percent / 100))
            aspect_ratio = img_original_size[1] / img_original_size[0]
            display_height = int(display_width * aspect_ratio)

            # Get selected alignment
            alignment = self._get_selected_alignment()

            # Get caption and alt text
            caption = self.caption_entry.get_text()
            alt_text = self.alt_entry.get_text()

            # Create image paragraph
            from core.models import Paragraph, ParagraphType
            image_para = Paragraph(ParagraphType.IMAGE)
            image_para.set_image_metadata(
                filename=img_filename,
                path=img_path,
                original_size=img_original_size,
                display_size=(display_width, display_height),
                alignment=alignment,
                caption=caption,
                alt_text=alt_text,
                width_percent=width_percent
            )

            if self.edit_mode:
                # Emit update signal
                self.emit('image-updated', {
                    'paragraph': image_para,
                    'original_paragraph': self.edit_paragraph
                })
            else:
                # Get insert position
                selected_index = self.position_dropdown.get_selected()
                insert_position = selected_index  # 0 = beginning, 1 = after first para, etc.

                # Emit insert signal
                self.emit('image-added', {'paragraph': image_para, 'position': insert_position})

            self.destroy()

        except Exception as e:
            error_msg = _("Error updating image") if self.edit_mode else _("Error inserting image")
            print(f"{error_msg}: {e}")
            import traceback
            traceback.print_exc()

            error_dialog = Adw.MessageDialog.new(
                self,
                error_msg.title(),
                _("Could not {} the image.").format(_("update") if self.edit_mode else _("insert")) + "\n\n" + str(e)
            )
            error_dialog.add_response("ok", _("OK"))
            error_dialog.present()

    def _load_existing_image(self):
        """Load existing image data when in edit mode"""
        if not self.edit_paragraph:
            return

        metadata = self.edit_paragraph.get_image_metadata()
        if not metadata:
            return

        try:
            from pathlib import Path

            # Load the existing image file
            img_path = Path(metadata.get('path', ''))
            if img_path.exists():
                self._load_image(str(img_path))

                # Set width percentage
                width_percent = metadata.get('width_percent', 80)
                self.width_scale.set_value(width_percent)

                # Set alignment
                alignment = metadata.get('alignment', 'center')
                alignment_box = self.alignment_group.get_parent()
                child = alignment_box.get_first_child()
                while child:
                    if isinstance(child, Gtk.CheckButton) and hasattr(child, 'alignment_value'):
                        if child.alignment_value == alignment:
                            child.set_active(True)
                            break
                    child = child.get_next_sibling()

                # Set caption
                caption = metadata.get('caption', '')
                if caption:
                    self.caption_entry.set_text(caption)

                # Set alt text
                alt_text = metadata.get('alt_text', '')
                if alt_text:
                    self.alt_entry.set_text(alt_text)

        except Exception as e:
            print(_("Error loading existing image: {}").format(e))
            import traceback
            traceback.print_exc()

class AiPdfDialog(Adw.Window):
    """Dialog for AI PDF Review"""
    __gtype_name__ = 'TacAiPdfDialog'

    def __init__(self, parent, ai_assistant, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("PDF Review by AI"))
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(600, 400)
        self.set_resizable(True)

        self.ai_assistant = ai_assistant
        self.selected_file_path = None

        self._create_ui()

    def _create_ui(self):
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_content(content_box)

        # Header
        header = Adw.HeaderBar()
        content_box.append(header)

        # Main Area
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        main_box.set_valign(Gtk.Align.CENTER)
        content_box.append(main_box)

        # Icon
        icon = Gtk.Image.new_from_icon_name("application-pdf-symbolic")
        icon.set_pixel_size(64)
        main_box.append(icon)

        # Instructions
        label = Gtk.Label(
            label=_("Select a PDF file of your text for review.\n"
                    "The AI ​​will perform a spelling, grammar, and semantic analysis.\n"
                    "IMPORTANT: Consider the 10,000 character limit for free APIs. Splitting your text into multiple files may be an alternative to paid API."),
            justify=Gtk.Justification.CENTER,
            wrap=True
        )
        main_box.append(label)

        # File Selection Group
        files_group = Adw.PreferencesGroup()
        main_box.append(files_group)

        self.file_row = Adw.ActionRow(title=_("No file selected"))
        
        select_btn = Gtk.Button(label=_("Choose PDF..."))
        select_btn.connect("clicked", self._on_choose_file)
        select_btn.set_valign(Gtk.Align.CENTER)
        
        self.file_row.add_suffix(select_btn)
        files_group.add(self.file_row)

        # Execute Button
        self.run_btn = Gtk.Button(label=_("Run Analysis"))
        self.run_btn.add_css_class("suggested-action")
        self.run_btn.add_css_class("pill")
        self.run_btn.set_halign(Gtk.Align.CENTER)
        self.run_btn.set_size_request(200, 50)
        self.run_btn.set_sensitive(False)
        self.run_btn.connect("clicked", self._on_run_clicked)
        main_box.append(self.run_btn)

        # Spinner (Loading)
        self.spinner = Gtk.Spinner()
        self.spinner.set_halign(Gtk.Align.CENTER)
        main_box.append(self.spinner)

    def _on_choose_file(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Select PDF"))
        
        # Filtro para PDF
        pdf_filter = Gtk.FileFilter()
        pdf_filter.set_name("PDF files")
        pdf_filter.add_pattern("*.pdf")
        
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(pdf_filter)
        dialog.set_filters(filters)
        dialog.set_default_filter(pdf_filter)

        dialog.open(self, None, self._on_file_open_finish)

    def _on_file_open_finish(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.selected_file_path = file.get_path()
                self.file_row.set_title(os.path.basename(self.selected_file_path))
                self.run_btn.set_sensitive(True)
        except Exception as e:
            print(f"Error selecting file: {e}")

    def _on_run_clicked(self, btn):
        if self.selected_file_path:
            self.run_btn.set_sensitive(False)
            self.run_btn.set_label(_("Analyzing (may take a few minutes)"))
            self.spinner.start()
            
            # Chama o método no core
            success = self.ai_assistant.request_pdf_review(self.selected_file_path)
            

class AiResultDialog(Adw.Window):
    """Dialog to show AI Results text"""
    __gtype_name__ = 'TacAiResultDialog'

    def __init__(self, parent, result_text, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("Analysis Results"))
        self.set_transient_for(parent)
        self.set_modal(True)
        # Aumentei um pouco o tamanho padrão para leitura confortável
        self.set_default_size(900, 700)

        # Container Principal
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(box)
        
        # Header
        header = Adw.HeaderBar()
        box.append(header)

        # Scrolled Window (Importante: vexpand=True para ocupar a altura)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        box.append(scrolled)

        # Text View
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        text_view.set_vexpand(True)
        text_view.set_hexpand(True)
        
        # Margens para o texto não colar na borda
        text_view.set_margin_top(20)
        text_view.set_margin_bottom(20)
        text_view.set_margin_start(20)
        text_view.set_margin_end(20)
        
        # Define o texto
        buff = text_view.get_buffer()
        buff.set_text(result_text)
        
        scrolled.set_child(text_view)
