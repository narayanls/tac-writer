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
import uuid

from core.models import Project, DEFAULT_TEMPLATES
from core.services import ProjectManager, ExportService
from core.config import Config
from utils.helpers import ValidationHelper, FileHelper
from utils.i18n import _

import webbrowser

# Try to import Dropbox SDK
try:
    import dropbox
    from dropbox import DropboxOAuth2FlowNoRedirect
    from dropbox.files import WriteMode
    from dropbox.exceptions import ApiError
    DROPBOX_AVAILABLE = True
except ImportError:
    DROPBOX_AVAILABLE = False

DROPBOX_APP_KEY = "x3h06acjg6fhbmq"

def get_system_fonts():
    """Get list of system fonts using multiple fallback methods"""
    font_names = []
    
    try:
        # Method 1: Try Pangocairo
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

    def __init__(self, parent, project_type="strandard", **kwargs):
        super().__init__(**kwargs)
        self.project_type = project_type
        
        # Adjust title based on type
        if self.project_type == 'latex':
            self.set_title(_("Novo Projeto LaTeX"))
        elif self.project_type == 'it_essay':
            # Handle IT Essay title
            self.set_title(_("Novo Projeto T.I."))
        else:
            self.set_title(_("Novo Projeto"))
            
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
        cancel_button.set_label(_("Cancelar"))
        cancel_button.connect('clicked', lambda x: self.destroy())
        header_bar.pack_start(cancel_button)

        # Create button
        self.create_button = Gtk.Button()
        self.create_button.set_label(_("Criar"))
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
        details_group.set_title(_("Detalhes do Projeto"))

        # Project name row
        name_row = Adw.ActionRow()
        name_row.set_title(_("Nome do Projeto"))
        self.name_entry = Gtk.Entry()
        self.name_entry.set_placeholder_text(_("Digite o nome do projeto..."))
        self.name_entry.set_text(_("Meu Novo Projeto"))
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
        author_row.set_title(_("Autor"))
        self.author_entry = Gtk.Entry()
        self.author_entry.set_placeholder_text(_("Seu nome..."))
        self.author_entry.set_size_request(200, -1)
        author_row.add_suffix(self.author_entry)
        details_group.add(author_row)

        parent.append(details_group)

        # Description section
        desc_group = Adw.PreferencesGroup()
        desc_group.set_title(_("Descrição"))

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
        template_group.set_title(_("Modelo"))
        template_group.set_description(_("Escolha um modelo para começar"))

        # Template selection
        self.template_combo = Gtk.ComboBoxText()
        for template in DEFAULT_TEMPLATES:
            self.template_combo.append(template.name, template.name)
        self.template_combo.set_active(0)

        template_row = Adw.ActionRow()
        template_row.set_title(_("Modelo de Documento"))
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
                raise ValueError(_("Nome do projeto não pode ser vazio"))
            
            if len(name) > 100:
                raise ValueError(_("Nome do projeto muito longo (máx 100 caracteres)"))
            
            # Create project
            project = self.project_manager.create_project(name, template_name)
            
            # Update metadata
            project.update_metadata({
                'author': author,
                'description': description,
                'type': self.project_type
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
                _("Entrada Inválida"),
                str(validation_error)
            )
            error_dialog.add_response("ok", _("OK"))
            error_dialog.present()
        
        except RuntimeError as runtime_error:
            # Runtime error - operation failed
            error_dialog = Adw.MessageDialog.new(
                self,
                _("Erro ao Criar Projeto"),
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
                _("Erro Inesperado"),
                _("Ocorreu um erro inesperado. Por favor reporte este problema:") + "\n\n" + error_msg
            )
            error_dialog.add_response("ok", _("OK"))
            error_dialog.present()


class ExportDialog(Adw.Window):
    """Dialog for exporting projects"""

    __gtype_name__ = 'TacExportDialog'

    def __init__(self, parent, project: Project, export_service: ExportService, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("Exportar Projeto"))
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
        cancel_button.set_label(_("Cancelar"))
        cancel_button.connect('clicked', lambda x: self.destroy())
        header_bar.pack_start(cancel_button)

        export_button = Gtk.Button()
        export_button.set_label(_("Exportar"))
        export_button.add_css_class("suggested-action")
        export_button.connect('clicked', self._on_export_clicked)
        header_bar.pack_end(export_button)

        content_box.append(header_bar)

        # Preferences page
        prefs_page = Adw.PreferencesPage()
        content_box.append(prefs_page)

        # Project info
        info_group = Adw.PreferencesGroup()
        info_group.set_title(_("Informações do Projeto"))
        prefs_page.add(info_group)

        name_row = Adw.ActionRow()
        name_row.set_title(_("Nome do Projeto"))
        name_row.set_subtitle(self.project.name)
        info_group.add(name_row)

        stats = self.project.get_statistics()
        stats_row = Adw.ActionRow()
        stats_row.set_title(_("Estatísticas"))
        stats_row.set_subtitle(_("{} palavras, {} parágrafos").format(stats['total_words'], stats['total_paragraphs']))
        info_group.add(stats_row)

        # Export options
        export_group = Adw.PreferencesGroup()
        export_group.set_title(_("Opções de Exportação"))
        prefs_page.add(export_group)

        # Format selection
        self.format_row = Adw.ComboRow()
        self.format_row.set_title(_("Formato"))
        format_model = Gtk.StringList()

        formats = []

        # Verify project type
        project_type = self.project.metadata.get('type')

        if project_type == 'latex':
            # if LaTex only tex format
            if self.export_service.pylatex_available:
                formats.append(("LaTeX Source (.tex)", "tex"))
            formats.append(("Texto Puro (.txt)", "txt"))

        elif project_type == 'it_essay':
            # IT Essay specific formats
            formats.append(("Markdown (.md)", "md")) # New option
            
            if self.export_service.odt_available:
                formats.append(("OpenDocument (.odt)", "odt"))
                
            if self.export_service.pylatex_available:
                formats.append(("LaTeX Source (.tex)", "tex"))
                

        else:
            # Default type (Standard)
            if self.export_service.odt_available:
                formats.append(("OpenDocument (.odt)", "odt"))
                
            if self.export_service.pdf_available:
                formats.append(("PDF (.pdf)", "pdf"))

            formats.append(("Texto Puro (.txt)", "txt"))

        self.format_data = []
        for display_name, format_code in formats:
            format_model.append(display_name)
            self.format_data.append(format_code)

        self.format_row.set_model(format_model)
        self.format_row.set_selected(0)
        export_group.add(self.format_row)

        # Include metadata
        self.metadata_row = Adw.SwitchRow()
        self.metadata_row.set_title(_("Incluir Metadados"))
        self.metadata_row.set_subtitle(_("Incluir autor, data de criação e outras informações"))
        self.metadata_row.set_active(True)
        export_group.add(self.metadata_row)

        # File location
        location_group = Adw.PreferencesGroup()
        location_group.set_title(_("Local de Saída"))
        prefs_page.add(location_group)

        self.location_row = Adw.ActionRow()
        self.location_row.set_title(_("Local de Salvamento"))
        self.location_row.set_subtitle(_("Clique para escolher o local"))

        choose_button = Gtk.Button()
        choose_button.set_label(_("Escolher..."))
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
            print(_("Aviso: Não foi possível criar diretório padrão de exportação: {}").format(e))
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
            _("Escolher Local de Exportação"),
            self,
            Gtk.FileChooserAction.SELECT_FOLDER,
            _("Selecionar"),
            _("Cancelar")
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
        button.set_label(_("Exportando..."))
        
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
                    child.set_label(_("Exportar"))
                    break
                child = child.get_prev_sibling()
        
        if success:
            success_dialog = Adw.MessageDialog.new(
                self,
                _("Exportação Concluída"),
                _("Project exported to:\n{}").format(output_path)
            )
            success_dialog.add_response("ok", _("OK"))
            
            def on_success_response(dialog, response):
                dialog.destroy()
                self.destroy()
            
            success_dialog.connect('response', on_success_response)
            success_dialog.present()
            
        else:
            error_msg = error_message if error_message else _("Ocorreu um erro ao exportar o projeto.")
            error_dialog = Adw.MessageDialog.new(
                self,
                _("Falha na Exportação"),
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
        self.set_title(_("Preferências"))
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
        general_page.set_title(_("Geral"))
        general_page.set_icon_name('tac-preferences-system-symbolic')
        self.add(general_page)

        # Appearance group
        appearance_group = Adw.PreferencesGroup()
        appearance_group.set_title(_("Aparência"))
        general_page.add(appearance_group)

        # Dark theme
        self.dark_theme_row = Adw.SwitchRow()
        self.dark_theme_row.set_title(_("Tema Escuro"))
        self.dark_theme_row.set_subtitle(_("Usar tema escuro na aplicação"))
        self.dark_theme_row.connect('notify::active', self._on_dark_theme_changed)
        appearance_group.add(self.dark_theme_row)

        # Color schemes
        self.color_scheme_row = Adw.SwitchRow()
        self.color_scheme_row.set_title(_("Esquema de Cores"))
        self.color_scheme_row.set_subtitle(_("Sobrescreve o tema com cores personalizadas"))
        self.color_scheme_row.connect('notify::active', self._on_color_scheme_toggled)
        appearance_group.add(self.color_scheme_row)

        # Color selector group
        self.colors_group = Adw.PreferencesGroup()
        self.colors_group.set_title(_("Cores Personalizadas"))
        general_page.add(self.colors_group)

        # Background color
        bg_row = Adw.ActionRow()
        bg_row.set_title(_("Cor de Fundo"))
        bg_row.set_subtitle(_("Cor principal da janela e editor"))
        self.bg_color_btn = self._create_color_picker_button()
        bg_row.add_suffix(self.bg_color_btn)
        self.colors_group.add(bg_row)

        # Font color
        font_row = Adw.ActionRow()
        font_row.set_title(_("Cor da Fonte"))
        font_row.set_subtitle(_("Cor do texto em todo o aplicativo"))
        self.font_color_btn = self._create_color_picker_button()
        font_row.add_suffix(self.font_color_btn)
        self.colors_group.add(font_row)

        # Accent Color
        accent_row = Adw.ActionRow()
        accent_row.set_title(_("Cor de Destaque"))
        accent_row.set_subtitle(_("Botões, links e elementos interativos"))
        self.accent_color_btn = self._create_color_picker_button()
        accent_row.add_suffix(self.accent_color_btn)
        self.colors_group.add(accent_row)

        # Restore default
        reset_color_row = Adw.ActionRow()
        reset_color_row.set_title(_("Restaurar Cores Padrão"))
        reset_btn = Gtk.Button(label=_("Restaurar"))
        reset_btn.add_css_class("flat")
        reset_btn.set_valign(Gtk.Align.CENTER)
        reset_btn.connect('clicked', self._on_reset_colors_clicked)
        reset_color_row.add_suffix(reset_btn)
        self.colors_group.add(reset_color_row)

        # Updates group
        updates_group = Adw.PreferencesGroup()
        updates_group.set_title(_("Atualizações"))
        general_page.add(updates_group)

        self.check_updates_row = Adw.SwitchRow()
        self.check_updates_row.set_title(_("Verificar Atualizações Automaticamente"))
        self.check_updates_row.set_subtitle(
            _("Consultar o GitHub ao iniciar para verificar se há novas versões")
        )
        self.check_updates_row.connect('notify::active', self._on_check_updates_changed)
        updates_group.add(self.check_updates_row)

        # Editor page
        editor_page = Adw.PreferencesPage()
        editor_page.set_title(_("Editor"))
        editor_page.set_icon_name('tac-accessories-text-editor-symbolic')
        self.add(editor_page)

        # Behavior group
        behavior_group = Adw.PreferencesGroup()
        behavior_group.set_title(_("Comportamento"))
        editor_page.add(behavior_group)

        # Auto save
        self.auto_save_row = Adw.SwitchRow()
        self.auto_save_row.set_title(_("Salvamento Automático"))
        self.auto_save_row.set_subtitle(_("Salvar projetos automaticamente ao editar"))
        self.auto_save_row.connect('notify::active', self._on_auto_save_changed)
        behavior_group.add(self.auto_save_row)

        # Word wrap
        self.word_wrap_row = Adw.SwitchRow()
        self.word_wrap_row.set_title(_("Quebra de Linha Automática"))
        self.word_wrap_row.set_subtitle(_("Ajustar texto à largura do editor"))
        self.word_wrap_row.connect('notify::active', self._on_word_wrap_changed)
        behavior_group.add(self.word_wrap_row)

        # AI page assistant
        ai_page = Adw.PreferencesPage()
        ai_page.set_title(_("Assistente de IA"))
        ai_page.set_icon_name('tac-document-properties-symbolic')
        self.add(ai_page)

        ai_group = Adw.PreferencesGroup()
        ai_group.set_title(_("Configurações do Assistente"))
        ai_group.set_description(
            _("Configure o provedor e credenciais para gerar sugestões.")
        )
        ai_page.add(ai_group)

         # Link to Wiki
        wiki_row = Adw.ActionRow()
        wiki_row.set_title(_("Guia de Configuração"))
        wiki_row.set_subtitle(_("Leia a documentação para saber como obter as chaves de API"))
        
        wiki_button = Gtk.Button()
        wiki_button.set_icon_name('tac-help-browser-symbolic')
        wiki_button.set_valign(Gtk.Align.CENTER)
        wiki_button.add_css_class("flat")
        wiki_button.set_tooltip_text(_("Abrir Documentação"))
        wiki_button.connect('clicked', self._on_ai_wiki_clicked)
        
        wiki_row.add_suffix(wiki_button)
        ai_group.add(wiki_row)

        self.ai_enabled_row = Adw.SwitchRow(
            title=_("Habilitar Assistente de IA"),
            subtitle=_("Permitir prompts usando provedor externo (Ctrl+Shift+I)."),
        )
        self.ai_enabled_row.connect("notify::active", self._on_ai_enabled_changed)
        ai_group.add(self.ai_enabled_row)

        self.ai_provider_row = Adw.ComboRow()
        self.ai_provider_row.set_title(_("Provedor"))
        self._ai_provider_options = [
            ("gemini", "Gemini"),
            ("openrouter", "OpenRouter.ai"),
        ]
        provider_model = Gtk.StringList.new([label for _pid, label in self._ai_provider_options])
        self.ai_provider_row.set_model(provider_model)
        self.ai_provider_row.connect("notify::selected", self._on_ai_provider_changed)
        ai_group.add(self.ai_provider_row)

        self.ai_model_row = Adw.ActionRow(
            title=_("Identificador do Modelo"),
            subtitle=_("Exemplos: gemini-2.5-flash"),
        )
        self.ai_model_entry = Gtk.Entry()
        self.ai_model_entry.set_placeholder_text(_("gemini-2.5-flash"))
        # Removed autosave on 'changed' to use button
        self.ai_model_row.add_suffix(self.ai_model_entry)
        self.ai_model_row.set_activatable_widget(self.ai_model_entry)
        ai_group.add(self.ai_model_row)

        self.ai_api_key_row = Adw.ActionRow(
            title=_("Chave da API"),
            subtitle=_("Armazenada localmente e usada para autenticação."),
        )
        self.ai_api_key_entry = Gtk.PasswordEntry(
            placeholder_text=_("Cole sua chave de API"),
            show_peek_icon=True,
            hexpand=True,
        )
        # auto save removed for use save button
        self.ai_api_key_row.add_suffix(self.ai_api_key_entry)
        self.ai_api_key_row.set_activatable_widget(self.ai_api_key_entry)
        ai_group.add(self.ai_api_key_row)

        # Save button
        save_btn = Gtk.Button(label=_("Salvar Configurações de IA"))
        save_btn.add_css_class("suggested-action")
        save_btn.add_css_class("pill")
        save_btn.set_margin_top(10)
        save_btn.set_margin_bottom(10)
        save_btn.set_halign(Gtk.Align.CENTER)
        save_btn.set_size_request(200, -1)
        save_btn.connect("clicked", self._on_save_ai_clicked)
        
        # Add button to group
        ai_group.add(save_btn)

        # List of widgets to enable/disable
        self._ai_config_widgets = [
            self.ai_provider_row,
            self.ai_model_row,
            self.ai_model_entry,
            self.ai_api_key_row,
            self.ai_api_key_entry,
            save_btn 
        ]

    def _on_ai_wiki_clicked(self, button):
        """Open the AI Assistant wiki page"""
        url = "https://github.com/narayanls/tac-writer/wiki/Fun%C3%A7%C3%B5es-Adicionais#-assistente-de-ia-para-revis%C3%A3o-textual"
        try:
            # Usar Gtk.UriLauncher is better for GTK4
            launcher = Gtk.UriLauncher.new(uri=url)
            launcher.launch(self, None, None)
        except AttributeError:
            # Fallback for older versions
            Gio.AppInfo.launch_default_for_uri(url, None)
        except Exception as e:
            print(_("Erro ao abrir wiki: {}").format(e))

    def _load_preferences(self):
        """Load preferences from config"""
        try:
            # Appearance
            self.dark_theme_row.set_active(self.config.get('use_dark_theme', False))

            # Behavior
            self.auto_save_row.set_active(self.config.get('auto_save', True))
            self.word_wrap_row.set_active(self.config.get('word_wrap', True))
            
            # AI Assistant
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
            
            self._update_ai_controls_sensitive(self.config.get_ai_assistant_enabled())
            self._update_ai_provider_ui(provider)

            # Color scheme - load buttons before switch
            self._set_color_btn(self.bg_color_btn, self.config.get_color_bg())
            self._set_color_btn(self.font_color_btn, self.config.get_color_font())
            self._set_color_btn(self.accent_color_btn, self.config.get_color_accent())
            self.color_scheme_row.set_active(self.config.get_color_scheme_enabled())
            self._update_color_controls_sensitive(self.config.get_color_scheme_enabled())
            
            # Updates
            self.check_updates_row.set_active(self.config.get('check_for_updates', True))

        except Exception as e:
            print(_("Erro ao carregar preferências: {}").format(e))

    def _on_save_ai_clicked(self, button):
        """Handle manual save of AI settings"""
        try:
            # 1. Get Provider
            index = self.ai_provider_row.get_selected()
            if 0 <= index < len(self._ai_provider_options):
                provider_id = self._ai_provider_options[index][0]
                self.config.set_ai_assistant_provider(provider_id)

            # 2. Get Model
            model = self.ai_model_entry.get_text().strip()
            self.config.set_ai_assistant_model(model)

            # 3. Get API Key
            api_key = self.ai_api_key_entry.get_text().strip()
            self.config.set_ai_assistant_api_key(api_key)

            # 4. Save to disk
            self.config.save()

            # 5. Show Feedback (Toast)
            toast = Adw.Toast.new(_("Configurações de IA Salvas"))
            toast.set_timeout(2)
            self.add_toast(toast)
            
        except Exception as e:
            print(_("Erro ao salvar configurações de IA: {}").format(e))
            error_toast = Adw.Toast.new(_("Erro ao salvar configurações"))
            self.add_toast(error_toast)

    def _on_dark_theme_changed(self, switch, pspec):
        """Handle dark theme toggle"""
        try:
            self.config.set('use_dark_theme', switch.get_active())
            self.config.save()

            # Apply theme immediately
            style_manager = Adw.StyleManager.get_default()
            if switch.get_active():
                style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            else:
                style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
        except Exception as e:
            print(_("Erro ao alterar tema: {}").format(e))

    def _on_font_family_changed(self, combo, pspec):
        """Handle font family change"""
        try:
            model = combo.get_model()
            selected_font = model.get_string(combo.get_selected())
            self.config.set('font_family', selected_font)
            self.config.save()
        except Exception as e:
            print(_("Erro ao alterar família da fonte: {}").format(e))

    def _on_font_size_changed(self, spin, pspec):
        """Handle font size change"""
        try:
            self.config.set('font_size', int(spin.get_value()))
            self.config.save()
        except Exception as e:
            print(_("Erro ao alterar tamanho da fonte: {}").format(e))

    def _on_auto_save_changed(self, switch, pspec):
        """Handle auto save toggle"""
        try:
            self.config.set('auto_save', switch.get_active())
            self.config.save()
        except Exception as e:
            print(_("Erro ao alterar salvamento automático: {}").format(e))

    def _on_word_wrap_changed(self, switch, pspec):
        """Handle word wrap toggle"""
        try:
            self.config.set('word_wrap', switch.get_active())
            self.config.save()
        except Exception as e:
            print(_("Erro ao alterar quebra de linha: {}").format(e))


    def _on_ai_enabled_changed(self, switch, pspec):
        enabled = switch.get_active()
        self.config.set_ai_assistant_enabled(enabled)
        self.config.save()
        self._update_ai_controls_sensitive(enabled)

    def _on_ai_provider_changed(self, combo_row, pspec):
        # Just updates the UI, the actual saving happens on the Save button
        index = combo_row.get_selected()
        if 0 <= index < len(self._ai_provider_options):
            provider_id = self._ai_provider_options[index][0]
            self._update_ai_provider_ui(provider_id)

    def _update_ai_controls_sensitive(self, enabled: bool) -> None:
        for widget in getattr(self, "_ai_config_widgets", []):
            widget.set_sensitive(enabled)

    def _update_ai_provider_ui(self, provider: str) -> None:
        if not provider or provider == "groq":
            provider = "gemini"

        if provider == "gemini":
            self.ai_model_entry.set_placeholder_text("gemini-2.5-flash")
            self.ai_model_row.set_subtitle(
                _("Identificador do modelo Gemini (ex: gemini-2.5-flash).")
            )
            self.ai_api_key_row.set_subtitle(_("Chave de API do Google AI Studio."))
        
        elif provider == "openrouter":
            self.ai_model_entry.set_placeholder_text("deepseek/deepseek-r1-0528:free")
            self.ai_model_row.set_subtitle(
                _("Identificador OpenRouter (ex: deepseek/deepseek-r1-0528:free).")
            )
            self.ai_api_key_row.set_subtitle(_("Chave de API do OpenRouter."))
        
        else:
            # Generic fallback
            self.ai_model_entry.set_placeholder_text(_("nome-do-modelo"))
            self.ai_model_row.set_subtitle(
                _("Identificador do modelo exigido pelo provedor.")
            )
            self.ai_api_key_row.set_subtitle(_("Chave de API usada para autenticação."))

    # Color scheme methods

    def _create_color_picker_button(self):
        """Cria um botão seletor de cor compatível com GTK 4.10+"""
        try:
            color_dialog = Gtk.ColorDialog()
            btn = Gtk.ColorDialogButton(dialog=color_dialog)
        except (AttributeError, TypeError):
            # Fallback para versões mais antigas do GTK4
            btn = Gtk.ColorButton()
            btn.set_use_alpha(False)
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect('notify::rgba', self._on_color_picker_changed)
        return btn

    def _set_color_btn(self, btn, hex_color):
        """Define a cor de um botão a partir de string hex"""
        rgba = Gdk.RGBA()
        if not rgba.parse(hex_color):
            rgba.parse('#888888')
        btn.set_rgba(rgba)

    def _on_color_scheme_toggled(self, switch, pspec):
        """Ativa/desativa o esquema de cores personalizado"""
        enabled = switch.get_active()
        self.config.set_color_scheme_enabled(enabled)
        self.config.save()
        self._update_color_controls_sensitive(enabled)
        self._push_color_scheme_to_window()

    def _on_color_picker_changed(self, btn, pspec):
        """Chamado quando qualquer cor é alterada pelo usuário"""
        if not self.color_scheme_row.get_active():
            return
        self._save_current_colors()
        self._push_color_scheme_to_window()

    def _on_reset_colors_clicked(self, btn):
        """Restaura as cores padrão"""
        self._set_color_btn(self.bg_color_btn, '#ffffff')
        self._set_color_btn(self.font_color_btn, '#2e2e2e')
        self._set_color_btn(self.accent_color_btn, '#3584e4')
        self._save_current_colors()
        self._push_color_scheme_to_window()

    def _update_color_controls_sensitive(self, enabled):
        """Ativa/desativa os controles de cores"""
        self.colors_group.set_sensitive(enabled)

    def _save_current_colors(self):
        """Salva as cores atuais dos botões no config"""
        self.config.set_color_bg(self._rgba_to_hex(self.bg_color_btn.get_rgba()))
        self.config.set_color_font(self._rgba_to_hex(self.font_color_btn.get_rgba()))
        self.config.set_color_accent(self._rgba_to_hex(self.accent_color_btn.get_rgba()))
        self.config.save()

    def _push_color_scheme_to_window(self):
        """Aplica ou remove o esquema de cores na janela principal em tempo real"""
        parent = self.get_transient_for()
        if not parent:
            return
        if self.color_scheme_row.get_active():
            if hasattr(parent, 'apply_color_scheme'):
                parent.apply_color_scheme(
                    self.config.get_color_bg(),
                    self.config.get_color_font(),
                    self.config.get_color_accent(),
                )
        else:
            if hasattr(parent, 'remove_color_scheme'):
                parent.remove_color_scheme()

    @staticmethod
    def _rgba_to_hex(rgba):
        """Converte Gdk.RGBA para string hex #rrggbb"""
        r = max(0, min(255, int(rgba.red * 255)))
        g = max(0, min(255, int(rgba.green * 255)))
        b = max(0, min(255, int(rgba.blue * 255)))
        return f'#{r:02x}{g:02x}{b:02x}'

    def _on_check_updates_changed(self, switch, pspec):
        """Handle update checking toggle"""
        try:
            self.config.set('check_for_updates', switch.get_active())
            self.config.save()
        except Exception as e:
            print(_("Erro ao alterar verificação de atualizações: {}").format(e))

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
            css_provider.load_from_data(""", -1)
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
            print(_("Erro ao aplicar CSS do diálogo de boas-vindas: {}").format(e))

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
        icon = Gtk.Image.new_from_icon_name('tac-writer')
        icon.set_pixel_size(56)
        icon.add_css_class("accent")
        title_box.append(icon)

        # Title
        title_label = Gtk.Label()
        title_label.set_markup("<span size='large' weight='bold'>" + _("O que é o Tac Writer?") + "</span>")
        title_label.set_halign(Gtk.Align.CENTER)
        title_box.append(title_label)

        content_box.append(title_box)

        # Content text
        content_text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        # CAT explanation
        cat_label = Gtk.Label()
        cat_label.set_markup("<b>" + _("Técnica da Argumentação Contínua (TAC):") + "</b>")
        cat_label.set_halign(Gtk.Align.START)
        content_text_box.append(cat_label)

        cat_desc = Gtk.Label()
        cat_desc.set_text(_("Tac Writer é uma ferramenta baseada em TAC (Técnica da Argumentação Contínua) e no método Pomodoro. TAC ajuda a escrever o desenvolvimento de uma idea de maneira organizada, separando o parágrafo em diferentes etapas. Leia a wiki para aproveitar todos os recursos. Para abrir a wiki clique no ícone '?'"))
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
        wiki_button.set_label(_("Saiba Mais - Documentação Online"))
        wiki_button.set_icon_name('tac-help-browser-symbolic')
        wiki_button.add_css_class("suggested-action")
        wiki_button.add_css_class("wiki-help-button")
        wiki_button.set_tooltip_text(_("Acesse o guia completo e tutoriais"))
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
        toggle_label.set_text(_("Mostrar este diálogo ao iniciar"))
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
        start_button.set_label(_("Vamos Começar"))
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
            print(_("Erro ao salvar preferência do diálogo de boas-vindas: {}").format(e))

    def _on_start_clicked(self, button):
        """Handle start button click"""
        # Emit signal before destroying
        self.emit('dialog-closed')
        self.destroy()
        
    def _on_wiki_clicked(self, button):
        """Handle wiki button click - open external browser"""
        wiki_url = "https://github.com/narayanls/tac-writer/wiki"
        
        try:
            # Try GTK4 native launcher
            launcher = Gtk.UriLauncher.new(uri=wiki_url)
            launcher.launch(self, None, None)
        except AttributeError:
            # Fallback: Gio.AppInfo
            try:
                Gio.AppInfo.launch_default_for_uri(wiki_url, None)
            except Exception as e:
                print(_("Não foi possível abrir URL via Gio: {}").format(e))
        except Exception as e:
            print(_("Erro ao abrir lançador: {}").format(e))


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
    dialog.set_version("1.3.1")
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
        self.set_title(_("Gerenciador de Backups"))
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
        close_button.set_label(_("Fechar"))
        close_button.connect('clicked', lambda x: self.destroy())
        header_bar.pack_start(close_button)

        # Create backup button
        create_backup_button = Gtk.Button()
        create_backup_button.set_label(_("Criar Backup"))
        create_backup_button.add_css_class("suggested-action")
        create_backup_button.connect('clicked', self._on_create_backup)
        header_bar.pack_end(create_backup_button)

        # Import button
        import_button = Gtk.Button()
        import_button.set_label(_("Importar Banco de Dados"))
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
        status_group.set_title(_("Banco de Dados Atual"))
        
        try:
            db_info = self.project_manager.get_database_info()
        except Exception as e:
            print(_("Erro ao obter info do banco de dados: {}").format(e))
            db_info = {
                'database_path': 'Unknown',
                'database_size_bytes': 0,
                'project_count': 0
            }
        
        # Database path
        path_row = Adw.ActionRow()
        path_row.set_title(_("Local do Banco de Dados"))
        path_row.set_subtitle(db_info['database_path'])
        status_group.add(path_row)

        # Database stats
        stats_row = Adw.ActionRow()
        stats_row.set_title(_("Estatísticas"))
        stats_text = _("{} projects, {} MB").format(
            db_info['project_count'],
            round(db_info['database_size_bytes'] / (1024*1024), 2)
        )
        stats_row.set_subtitle(stats_text)
        status_group.add(stats_row)

        main_box.append(status_group)

        # Backups list
        backups_group = Adw.PreferencesGroup()
        backups_group.set_title(_("Backups Disponíveis"))
        backups_group.set_description(_("Backups são salvos em Documentos/TAC Projects/database_backups"))

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
            print(_("Erro ao listar backups: {}").format(e))
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
            status_icon = Gtk.Image.new_from_icon_name('tac-emblem-ok-symbolic')
            status_icon.set_tooltip_text(_("Valid backup"))
        else:
            status_icon = Gtk.Image.new_from_icon_name('tac-dialog-warning-symbolic')
            status_icon.set_tooltip_text(_("Invalid or corrupted backup"))
            status_icon.add_css_class("warning")

        row.add_prefix(status_icon)

        # Action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Restore button
        if backup['is_valid']:
            restore_button = Gtk.Button()
            restore_button.set_icon_name('tac-document-revert-symbolic')
            restore_button.set_tooltip_text(_("Import this backup"))
            restore_button.add_css_class("flat")
            restore_button.connect('clicked', lambda btn, b=backup: self._on_restore_backup(b))
            button_box.append(restore_button)

        # Delete button
        delete_button = Gtk.Button()
        delete_button.set_icon_name('tac-user-trash-symbolic')
        delete_button.set_tooltip_text(_("Excluir backup"))
        delete_button.add_css_class("flat")
        delete_button.add_css_class("destructive-action")
        delete_button.connect('clicked', lambda btn, b=backup: self._on_delete_backup(b))
        button_box.append(delete_button)

        row.add_suffix(button_box)
        return row

    def _on_create_backup(self, button):
        """Handle create backup button"""
        button.set_sensitive(False)
        button.set_label(_("Criando..."))

        def backup_thread():
            try:
                backup_path = self.project_manager.create_manual_backup()
                GLib.idle_add(self._backup_created, backup_path, button)
            except Exception as e:
                print(_("Erro na thread de backup: {}").format(e))
                GLib.idle_add(self._backup_created, None, button)

        thread = threading.Thread(target=backup_thread, daemon=True)
        thread.start()

    def _backup_created(self, backup_path, button):
        """Callback when backup is created"""
        button.set_sensitive(True)
        button.set_label(_("Criar Backup"))

        if backup_path:
            # Show success toast in parent window
            parent_window = self.get_transient_for()
            if parent_window and hasattr(parent_window, '_show_toast'):
                parent_window._show_toast(_("Backup criado com sucesso"))
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
        """Handle import database button using Gtk.FileDialog"""
        # Criar filtros usando Gio.ListStore (padrão novo)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        
        filter_db = Gtk.FileFilter()
        filter_db.set_name(_("Arquivos de Banco de Dados (*.db)"))
        filter_db.add_pattern("*.db")
        filters.append(filter_db)

        filter_all = Gtk.FileFilter()
        filter_all.set_name(_("Todos os arquivos"))
        filter_all.add_pattern("*")
        filters.append(filter_all)

        dialog = Gtk.FileDialog()
        dialog.set_title(_("Importar Banco de Dados"))
        dialog.set_filters(filters)
        dialog.set_default_filter(filter_db)
        
        # Open the dialog and define the callback
        dialog.open(self, None, self._on_import_file_finish)

    def _on_import_file_finish(self, dialog, result):
        """Callback for file selection"""
        try:
            file = dialog.open_finish(result)
            if file:
                backup_path = Path(file.get_path())
                self._confirm_import(backup_path)
        except GLib.Error as e:
            # Occurs if the user cancels
            print(f"File selection cancelled or error: {e}")

    def _on_restore_backup(self, backup):
        """Handle restore backup button"""
        self._confirm_import(backup['path'])

    def _confirm_import(self, backup_path: Path):
        """Show confirmation dialog for import/merge"""
        # ... (código de validação existente permanece igual) ...

        # Show confirmation with options
        dialog = Adw.MessageDialog.new(
            self,
            _("Como deseja importar?"),
            _("Você selecionou um banco de dados externo. Escolha como deseja prosseguir:\n\n"
              "• Mesclar: Adiciona projetos novos e atualiza os existentes (Ideal para sincronizar PCs).\n"
              "• Substituir: Apaga tudo atual e coloca o backup no lugar.")
        )

        dialog.add_response("cancel", _("Cancelar"))
        dialog.add_response("replace", _("Substituir Tudo"))
        dialog.add_response("merge", _("Mesclar (Sincronizar)"))
        
        # Button styles
        dialog.set_response_appearance("replace", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance("merge", Adw.ResponseAppearance.SUGGESTED)
        
        dialog.set_default_response("merge")

        dialog.connect('response', lambda d, r, path=backup_path: self._import_action_selected(d, r, path))
        dialog.present()

    def _import_action_selected(self, dialog, response, backup_path):
        dialog.destroy()
        # Compare for merge
        if response == "replace":
            self._perform_import(backup_path) 
        elif response == "merge":
            self._perform_merge(backup_path) 

    def _perform_merge(self, backup_path: Path):
        """Perform the database merge"""
        loading_dialog = Adw.MessageDialog.new(
            self,
            _("Mesclando Bancos de Dados"),
            _("Analisando e sincronizando projetos...")
        )
        loading_dialog.present()

        def merge_thread():
            try:
                # Call new method in ProjectManager
                stats = self.project_manager.merge_database(str(backup_path))
                GLib.idle_add(self._merge_finished, True, stats, loading_dialog)
            except Exception as e:
                print(_("Erro na thread de merge: {}").format(e))
                GLib.idle_add(self._merge_finished, False, str(e), loading_dialog)

        thread = threading.Thread(target=merge_thread, daemon=True)
        thread.start()

    def _merge_finished(self, success, result, loading_dialog):
        loading_dialog.destroy()

        if success:
            stats = result
            msg = _("Sincronização concluída com sucesso!\n\n"
                    "• Projetos novos: {}\n"
                    "• Projetos atualizados: {}\n"
                    "• Parágrafos processados: {}").format(
                        stats['projects_added'], 
                        stats['projects_updated'],
                        stats['paragraphs_processed']
                    )
            
            success_dialog = Adw.MessageDialog.new(self, _("Sucesso"), msg)
            success_dialog.add_response("ok", _("OK"))
            
            def on_success(dlg, resp):
                dlg.destroy()
                self.emit('database-imported')
                self.destroy()
                
            success_dialog.connect('response', on_success)
            success_dialog.present()
        else:
            error_msg = result
            error_dialog = Adw.MessageDialog.new(
                self, _("Erro na Mesclagem"), 
                _("Não foi possível mesclar: {}").format(error_msg)
            )
            error_dialog.add_response("ok", _("OK"))
            error_dialog.present()
            
        return False

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
            _("Importando Banco de Dados"),
            _("Por favor aguarde enquanto o banco de dados é importado...")
        )
        loading_dialog.present()

        def import_thread():
            try:
                success = self.project_manager.import_database(backup_path)
                GLib.idle_add(self._import_finished, success, loading_dialog)
            except Exception as e:
                print(_("Erro na thread de importação: {}").format(e))
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
            _("Excluir Backup?"),
            _("Are you sure you want to delete '{}'?\n\nThis action cannot be undone.").format(backup['name'])
        )

        dialog.add_response("cancel", _("Cancelar"))
        dialog.add_response("delete", _("Excluir"))
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
                print(_("Erro ao excluir backup: {}").format(e))
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
            self.set_title(_("Editar Imagem"))
        else:
            self.set_title(_("Inserir Imagem"))

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
        cancel_button = Gtk.Button(label=_("Cancelar"))
        cancel_button.connect('clicked', lambda b: self.destroy())
        header_bar.pack_start(cancel_button)

        # Insert/Update button
        button_label = _("Atualizar") if self.edit_mode else _("Inserir")
        self.insert_button = Gtk.Button(label=button_label)
        self.insert_button.add_css_class('tac-insert-image')
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
        file_group.set_title(_("Arquivo de Imagem"))
        file_group.set_description(_("Selecione uma imagem para inserir no documento"))
        main_box.append(file_group)

        # File chooser button
        file_button_row = Adw.ActionRow()
        file_button_row.set_title(_("Selecionar Imagem"))
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
        preview_label.set_markup(f"<b>{_('Pré-visualização')}</b>")
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
        self.format_group.set_title(_("Formatação da Imagem"))
        self.format_group.set_visible(False)
        main_box.append(self.format_group)

        # Width adjustment
        width_row = Adw.ActionRow()
        width_row.set_title(_("Largura de Exibição (%)"))
        width_row.set_subtitle(_("Porcentagem da largura da página"))
        
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
        alignment_row.set_title(_("Alinhamento"))
        alignment_row.set_subtitle(_("Posição da imagem na página"))
        
        alignment_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        alignment_box.set_valign(Gtk.Align.CENTER)
        
        self.alignment_group = None
        alignments = [
            ('left', _("Esquerda")),
            ('center', _("Centro")),
            ('right', _("Direita"))
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
        caption_row.set_title(_("Legenda (opcional)"))
        self.caption_entry = caption_row
        self.format_group.add(caption_row)

        # Alt text entry
        alt_row = Adw.EntryRow()
        alt_row.set_title(_("Texto Alternativo (opcional)"))
        alt_row.set_show_apply_button(False)
        self.alt_entry = alt_row
        self.format_group.add(alt_row)

        # Position group
        self.position_group = Adw.PreferencesGroup()
        self.position_group.set_title(_("Posição no Documento"))
        self.position_group.set_visible(False)
        main_box.append(self.position_group)

        # Position selection
        position_row = Adw.ActionRow()
        position_row.set_title(_("Inserir Após"))
        position_row.set_subtitle(_("Escolha onde posicionar a imagem"))
        
        self.position_dropdown = Gtk.DropDown()
        self.position_dropdown.set_valign(Gtk.Align.CENTER)
        position_row.add_suffix(self.position_dropdown)
        self.position_group.add(position_row)
        
        self._update_position_list()

    def _update_position_list(self):
        """Update the position dropdown with current paragraphs"""
        options = [_("Início do documento")]
        
        for i, para in enumerate(self.project.paragraphs):
            from core.models import ParagraphType
            
            if para.type == ParagraphType.TITLE_1:
                text = f"📑 {para.content[:30]}"
            elif para.type == ParagraphType.TITLE_2:
                text = f"  📄 {para.content[:30]}"
            elif para.type == ParagraphType.IMAGE:
                text = f"🖼️ {_('Imagem')}"
            else:
                content_preview = para.content[:30] if para.content else _("(vazio)")
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
        file_filter.set_name(_("Arquivos de Imagem"))
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
        dialog.set_title(_("Selecionar Imagem"))
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
            print(_("Erro ao selecionar arquivo: {}").format(e))

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
                info_text = _("Tamanho: {} x {} pixels • {:.1f} KB").format(
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
            print(_("Erro ao carregar imagem: {}").format(e))
            # Show error dialog
            error_dialog = Adw.MessageDialog.new(
                self,
                _("Erro ao Carregar Imagem"),
                _("Não foi possível carregar o arquivo de imagem selecionado.") + "\n\n" + str(e)
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
            error_msg = _("Erro ao atualizar imagem") if self.edit_mode else _("Erro ao inserir imagem")
            print(f"{error_msg}: {e}")
            import traceback
            traceback.print_exc()

            error_dialog = Adw.MessageDialog.new(
                self,
                error_msg.title(),
                _("Não foi possível {} a imagem.").format(_("atualizar") if self.edit_mode else _("inserir")) + "\n\n" + str(e)
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
                
            # Set width percentage
            width_percent = metadata.get('width_percent', 80)
            self.width_scale.set_value(width_percent)

            # Try to load image
            img_path = Path(metadata.get('path', ''))
            if img_path.exists():
                self._load_image(str(img_path))
            else:
                # If image doesn't exist, shows label image name
                filename = metadata.get('filename', _('Desconhecido'))
                self.file_label.set_text(_("Arquivo faltando: {}").format(filename))
                self.file_label.add_css_class('error')
                self.info_label.set_text(_("Selecione o arquivo novamente para corrigir."))
                
                # Enable edit image
                self.format_group.set_visible(True)
                self.position_group.set_visible(True)

        except Exception as e:
            print(_("Erro ao carregar imagem existente: {}").format(e))
            import traceback
            traceback.print_exc()

class AiPdfDialog(Adw.Window):
    """Dialog for AI PDF Review"""
    __gtype_name__ = 'TacAiPdfDialog'

    def __init__(self, parent, ai_assistant, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("Revisão de PDF por IA"))
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
        icon = Gtk.Image.new_from_icon_name("tac-x-office-document-symbolic")
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
        
        select_btn = Gtk.Button(label=_("Escolher PDF..."))
        select_btn.connect("clicked", self._on_choose_file)
        select_btn.set_valign(Gtk.Align.CENTER)
        
        self.file_row.add_suffix(select_btn)
        files_group.add(self.file_row)

        # Execute Button
        self.run_btn = Gtk.Button(label=_("Executar Análise"))
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
        dialog.set_title(_("Selecionar PDF"))
        
        # Filter for PDF
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
            self.run_btn.set_label(_("Analisando (pode levar alguns minutos)"))
            self.spinner.start()
            
            # Call the method in core
            success = self.ai_assistant.request_pdf_review(self.selected_file_path)
            

class AiResultDialog(Adw.Window):
    """Dialog to show AI Results text"""
    __gtype_name__ = 'TacAiResultDialog'

    def __init__(self, parent, result_text, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("Resultados da Análise"))
        self.set_transient_for(parent)
        self.set_modal(True)
        # I increased the default size a little for comfortable reading
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
        
        # Margins so the text doesn't stick to the edge
        text_view.set_margin_top(20)
        text_view.set_margin_bottom(20)
        text_view.set_margin_start(20)
        text_view.set_margin_end(20)
        
        # Sets the text
        buff = text_view.get_buffer()
        buff.set_text(result_text)
        
        scrolled.set_child(text_view)


class CloudSyncDialog(Adw.Window):
    """Dialog for Dropbox Cloud Synchronization"""

    __gtype_name__ = 'TacCloudSyncDialog'

    def __init__(self, parent, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("Sincronização na Nuvem (Dropbox)"))
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(500, 500)
        self.set_resizable(False)
        
        self.parent_window = parent
        self.config = parent.config
        self.auth_flow = None
        
        # Estado inicial
        self.is_connected = False
        
        self._create_ui()
        self._check_existing_connection()

    def _create_ui(self):
        """Create the dialog UI"""
        # 1. Overlay for notifications
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay) 

        # 2. Box inside overlay
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(content_box)

        # Header bar
        header_bar = Adw.HeaderBar()
        content_box.append(header_bar)

        # Main content area
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        content_box.append(main_box)

        # --- Section 1: Authentication / Login ---
        auth_group = Adw.PreferencesGroup()
        auth_group.set_title(_("Configuração de Acesso"))
        auth_group.set_description(_("Para conectar, siga os passos abaixo:"))
        main_box.append(auth_group)

        # Step 1: Open Browser
        self.step1_row = Adw.ActionRow()
        self.step1_row.set_title(_("1. Autorizar no Dropbox"))
        self.step1_row.set_subtitle(_("Clique para abrir o navegador e fazer login."))
        
        login_button = Gtk.Button()
        login_button.set_label(_("Abrir Navegador"))
        login_button.add_css_class("suggested-action")
        login_button.set_valign(Gtk.Align.CENTER)
        login_button.connect("clicked", self._on_open_browser_clicked)
        
        self.step1_row.add_suffix(login_button)
        auth_group.add(self.step1_row)

        # Step 2: Enter Code
        self.step2_row = Adw.ActionRow()
        self.step2_row.set_title(_("2. Inserir Código"))
        self.step2_row.set_subtitle(_("Cole o código gerado pelo Dropbox."))
        auth_group.add(self.step2_row)

        # Entry container
        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.auth_code_entry = Gtk.Entry()
        self.auth_code_entry.set_placeholder_text(_("Ex: sl.Bz..."))
        self.auth_code_entry.set_hexpand(True)
        entry_box.append(self.auth_code_entry)

        self.connect_btn = Gtk.Button(label=_("Conectar"))
        self.connect_btn.add_css_class("suggested-action")
        self.connect_btn.connect("clicked", self._on_connect_clicked)
        entry_box.append(self.connect_btn)

        # Card wrapper for entry
        auth_card = Gtk.Frame()
        auth_card.add_css_class("card")
        auth_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        auth_inner.set_margin_start(12)
        auth_inner.set_margin_end(12)
        auth_inner.set_margin_top(12)
        auth_inner.set_margin_bottom(12)
        
        auth_inner.append(Gtk.Label(label=_("Cole o código de autorização aqui:"), xalign=0))
        auth_inner.append(entry_box)
        auth_card.set_child(auth_inner)
        
        main_box.append(auth_card)
        self.auth_card_widget = auth_card

        # Separator
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # --- Section 2: Sync Actions ---
        sync_group = Adw.PreferencesGroup()
        sync_group.set_title(_("Sincronização"))
        main_box.append(sync_group)

        self.sync_row = Adw.ActionRow()
        self.sync_row.set_title(_("Estado: Não conectado"))
        self.sync_row.set_subtitle(_("Última sincronização: Nunca"))
        
        # Status icon
        self.status_icon = Gtk.Image.new_from_icon_name("tac-dialog-warning-symbolic")
        self.sync_row.add_prefix(self.status_icon)
        
        sync_group.add(self.sync_row)

        # Big Sync Button
        self.sync_button = Gtk.Button(label=_("Sincronizar Agora"))
        self.sync_button.set_icon_name("tac-emblem-synchronizing-symbolic")
        self.sync_button.add_css_class("pill")
        self.sync_button.set_size_request(-1, 50)
        self.sync_button.set_margin_top(10)
        self.sync_button.set_sensitive(False)
        self.sync_button.connect("clicked", self._on_sync_now_clicked)
        
        main_box.append(self.sync_button)
        
        # Logout button
        self.logout_button = Gtk.Button(label=_("Desconectar Conta"))
        self.logout_button.add_css_class("flat")
        self.logout_button.add_css_class("destructive-action")
        self.logout_button.set_margin_top(10)
        self.logout_button.set_visible(False)
        self.logout_button.connect("clicked", self._on_logout_clicked)
        main_box.append(self.logout_button)

    
    def _show_toast(self, message):
        """Helper to show toast in this dialog"""
        if hasattr(self, 'toast_overlay'):
            toast = Adw.Toast.new(message)
            self.toast_overlay.add_toast(toast)
        else:
            print(f"Toast (fallback): {message}")

    def _check_existing_connection(self):
        """Verifica se já existe um token salvo na config"""
        refresh_token = self.config.get('dropbox_refresh_token')
        
        if refresh_token:
            self.is_connected = True
            self._update_ui_state(connected=True)
            self.sync_row.set_subtitle(_("Pronto para sincronizar."))

    def _update_ui_state(self, connected: bool):
        """Atualiza a UI baseada no estado de conexão"""
        if connected:
            self.sync_row.set_title(_("Estado: Conectado ao Dropbox"))
            self.status_icon.set_from_icon_name("tac-emblem-ok-symbolic")
            self.status_icon.add_css_class("success")
            
            self.sync_button.set_sensitive(True)
            self.sync_button.add_css_class("suggested-action")
            
            self.auth_code_entry.set_text(_("Conta vinculada."))
            self.auth_code_entry.set_sensitive(False)
            self.connect_btn.set_sensitive(False)
            
            self.logout_button.set_visible(True)
        else:
            self.sync_row.set_title(_("Estado: Não conectado"))
            self.status_icon.set_from_icon_name("tac-dialog-warning-symbolic")
            self.status_icon.remove_css_class("success")
            
            self.sync_button.set_sensitive(False)
            self.sync_button.remove_css_class("suggested-action")
            
            self.auth_code_entry.set_text("")
            self.auth_code_entry.set_sensitive(True)
            self.connect_btn.set_sensitive(True)
            
            self.logout_button.set_visible(False)

    def _on_open_browser_clicked(self, btn):
        """Inicia o fluxo OAuth PKCE e abre o navegador"""
        if not DROPBOX_AVAILABLE:
            self._show_toast(_("Biblioteca 'dropbox' não instalada."))
            return

        # Verify if key was definied
        try:
            if not DROPBOX_APP_KEY or DROPBOX_APP_KEY == "YOUR_APP_KEY_HERE":
                self._show_toast(_("Erro: App Key não configurada."))
                return
        except NameError:
             self._show_toast(_("Erro: App Key não encontrada."))
             return

        try:
            
            self.auth_flow = DropboxOAuth2FlowNoRedirect(
                DROPBOX_APP_KEY,
                use_pkce=True,
                token_access_type='offline'
            )

            authorize_url = self.auth_flow.start()
            
            # Try open browser
            try:
                launcher = Gtk.UriLauncher.new(uri=authorize_url)
                launcher.launch(self, None, None)
            except AttributeError:
                webbrowser.open(authorize_url)
            
            self._show_toast(_("Navegador aberto. Autorize e copie o código."))
            self.auth_code_entry.grab_focus()

        except Exception as e:
            self._show_toast(_("Erro ao iniciar autenticação: {}").format(str(e)))
            print(f"Dropbox Auth Error: {e}")

    def _on_connect_clicked(self, btn):
        """Valida o código colado e obtém os tokens"""
        code = self.auth_code_entry.get_text().strip()
        
        if not code:
            self._show_toast(_("Por favor, cole o código de autorização."))
            return
            
        if not self.auth_flow:
            self._show_toast(_("Fluxo não iniciado. Clique em Abrir Navegador."))
            return

        btn.set_sensitive(False)
        btn.set_label(_("Verificando..."))

        # Execute in thread for prevent UI freeze
        threading.Thread(target=self._finish_auth_flow, args=(code, btn), daemon=True).start()

    def _finish_auth_flow(self, code, btn):
        """Finaliza a troca do código pelo token (Background Thread)"""
        try:
            oauth_result = self.auth_flow.finish(code)
            
            
            refresh_token = oauth_result.refresh_token
            
            GLib.idle_add(self._on_auth_success, btn, refresh_token)
            
        except Exception as e:
            print(f"Auth Finish Error: {e}")
            GLib.idle_add(self._on_auth_failure, btn, str(e))

    def _on_auth_success(self, btn, refresh_token):
        """Chamado na thread principal em caso de sucesso"""
        btn.set_label(_("Conectar"))
        
        # Save in user config
        self.config.set('dropbox_refresh_token', refresh_token)
        self.config.save()
        
        self.is_connected = True
        self._update_ui_state(connected=True)
        self._show_toast(_("Conectado com sucesso!"))
        
        self.auth_flow = None

    def _on_auth_failure(self, btn, error_message):
        """Chamado na thread principal em caso de erro"""
        btn.set_sensitive(True)
        btn.set_label(_("Conectar"))
        self._show_toast(_("Código inválido ou expirado."))

    def _on_logout_clicked(self, btn):
        """Remove as credenciais salvas"""
        self.config.set('dropbox_refresh_token', None)
        self.config.save()
        
        self.is_connected = False
        self._update_ui_state(connected=False)
        self._show_toast(_("Conta desconectada."))

    def _on_sync_now_clicked(self, btn):
        """Lógica de Sincronização"""
        if not self.is_connected:
            return

        refresh_token = self.config.get('dropbox_refresh_token')
        if not refresh_token:
            self._show_toast(_("Erro: Credenciais não encontradas."))
            return

        btn.set_sensitive(False)
        btn.set_label(_("Sincronizando..."))
        self.sync_row.set_subtitle(_("Sincronização em andamento..."))
        
        # Initiate sync thread
        threading.Thread(target=self._perform_sync, args=(refresh_token, btn), daemon=True).start()


    def _perform_sync(self, refresh_token, btn):
        """
        Execute sync
        Download -> Merge -> Upload
        """
        if not DROPBOX_AVAILABLE:
            return

        try:
            dbx = dropbox.Dropbox(oauth2_refresh_token=refresh_token, app_key=DROPBOX_APP_KEY)
            
            local_db_path = self.config.database_path
            remote_path = "/tac_writer.db"
            temp_db_path = local_db_path.with_suffix('.temp_sync.db')
            
            sync_msg = ""
            stats = None

            # 1. Try to download remote file
            remote_exists = False
            try:
                # Download to temp. file
                dbx.files_download_to_file(str(temp_db_path), remote_path)
                remote_exists = True
                print("Download do Dropbox concluído.")
            except ApiError as e:
                # If "file not found", proceed to initial upload
                if e.error.is_path() and e.error.get_path().is_not_found():
                    print("Arquivo não encontrado no Dropbox. Iniciando primeiro upload.")
                    remote_exists = False
                else:
                    raise e

            # 2. Execute Merge (if something was downloaded)
            if remote_exists:
                # Use ProjectManager to access merge logic
                stats = self.parent_window.project_manager.merge_database(str(temp_db_path))
                
                # Remove temporary file
                if temp_db_path.exists():
                    os.remove(temp_db_path)
                
                if stats['projects_added'] > 0 or stats['projects_updated'] > 0:
                    sync_msg = _("Sincronizado: +{} novos, {} atualizados.").format(
                        stats['projects_added'], stats['projects_updated']
                    )
                else:
                    sync_msg = _("Sincronização concluída (sem alterações remotas).")
            else:
                sync_msg = _("Primeiro upload para a nuvem realizado.")

            # 3. Upload from local (Overwrite)
            with open(local_db_path, "rb") as f:
                dbx.files_upload(
                    f.read(), 
                    remote_path, 
                    mode=WriteMode('overwrite')
                )
            print("Upload para o Dropbox concluído.")

            # Finalize with sucess
            GLib.idle_add(self._on_sync_finished, btn, True, sync_msg)
            
        except Exception as e:
            print(f"Erro de Sync: {e}")
            
            try:
                temp_path = self.config.database_path.with_suffix('.temp_sync.db')
                if temp_path.exists():
                    os.remove(temp_path)
            except:
                pass
                
            GLib.idle_add(self._on_sync_finished, btn, False, str(e))

    def _on_sync_finished(self, btn, success, message):
        """Callback de finalização do sync"""
        btn.set_sensitive(True)
        btn.set_label(_("Sincronizar Agora"))
        
        if success:
            timestamp = datetime.now().strftime("%d/%m %H:%M")
            self.sync_row.set_subtitle(_("Última sincronização: {}").format(timestamp))
            self._show_toast(message)
            
            # Reload project list in main window
            if hasattr(self.parent_window, 'project_list'):
                self.parent_window.project_list.refresh_projects()
                
            
        else:
            self.sync_row.set_subtitle(_("Erro na última sincronização"))
            self._show_toast(_("Erro: {}").format(message))

class ReferencesDialog(Adw.Window):
    """Dialog for managing bibliographic references"""

    __gtype_name__ = 'TacReferencesDialog'

    def __init__(self, parent, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("Catálogo de Referências"))
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(600, 500)
        self.set_resizable(True)

        self.parent_window = parent
        self.project = parent.current_project
        self.project_manager = parent.project_manager

        # Ensure references list exists in metadata
        if 'references' not in self.project.metadata:
            self.project.metadata['references'] = []

        self._create_ui()
        self._refresh_list()

    def _create_ui(self):
        """Create the dialog UI"""
        # Toast Overlay for notifications
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        # Main content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(content_box)

        # Header bar
        header_bar = Adw.HeaderBar()
        content_box.append(header_bar)

        # Content Scrolled Window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content_box.append(scrolled)

        # Clamp (to center content and limit width)
        clamp = Adw.Clamp()
        clamp.set_maximum_size(800)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        scrolled.set_child(clamp)

        # Main Box inside Clamp
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        clamp.set_child(main_box)

        # --- Section 1: Add New Reference ---
        add_group = Adw.PreferencesGroup()
        add_group.set_title(_("Adicionar Nova Referência"))
        add_group.set_description(_("Cadastre autores para citar rapidamente durante a escrita."))
        main_box.append(add_group)

        # Author Entry
        self.author_row = Adw.EntryRow()
        self.author_row.set_title(_("Autor(es)"))
        self.author_row.set_show_apply_button(False)
        self.author_row.add_prefix(Gtk.Image.new_from_icon_name("tac-avatar-default-symbolic"))
        # Using placeholder to teach format
        try:
             # GTK 4.10+
            self.author_row.set_placeholder_text(_("Ex: SOBRENOME"))
        except AttributeError:
            pass 
        add_group.add(self.author_row)

        # Year Entry
        self.year_row = Adw.EntryRow()
        self.year_row.set_title(_("Ano"))
        self.year_row.set_show_apply_button(False)
        self.year_row.add_prefix(Gtk.Image.new_from_icon_name("tac-x-office-calendar-symbolic"))
        try:
            self.year_row.set_placeholder_text("2024")
        except AttributeError:
            pass
        add_group.add(self.year_row)

        # Add Button
        add_btn = Gtk.Button(label=_("Adicionar ao Catálogo"))
        add_btn.add_css_class("suggested-action")
        add_btn.add_css_class("pill")
        add_btn.set_halign(Gtk.Align.END)
        add_btn.connect("clicked", self._on_add_clicked)
        
        # Helper box for button alignment
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.append(add_btn)
        main_box.append(btn_box)

        # --- Section 2: List of References ---
        list_group = Adw.PreferencesGroup()
        list_group.set_title(_("Referências Cadastradas"))
        main_box.append(list_group)

        # ListBox to hold rows
        self.refs_listbox = Gtk.ListBox()
        self.refs_listbox.add_css_class("boxed-list")
        self.refs_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        
        # We put the listbox inside the group
        list_group.add(self.refs_listbox)
        
        # Placeholder for empty state
        self.empty_label = Gtk.Label(label=_("Nenhuma referência cadastrada."))
        self.empty_label.add_css_class("dim-label")
        self.empty_label.set_margin_top(12)
        self.empty_label.set_visible(False)
        main_box.append(self.empty_label)

    def _refresh_list(self):
        """Rebuild the list of references"""
        # Clear list
        child = self.refs_listbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.refs_listbox.remove(child)
            child = next_child

        refs = self.project.metadata.get('references', [])
        
        if not refs:
            self.refs_listbox.set_visible(False)
            self.empty_label.set_visible(True)
            return

        self.refs_listbox.set_visible(True)
        self.empty_label.set_visible(False)

        # Sort alphabetically by author
        sorted_refs = sorted(refs, key=lambda x: x.get('author', '').lower())

        for ref in sorted_refs:
            row = Adw.ActionRow()
            
            # Format: SOBRENOME, Nome (Year)
            title_text = f"{ref.get('author', 'Unknown')} ({ref.get('year', 'Nd')})"
            row.set_title(title_text)
            
            # Subtitle: Work title
            work_title = ref.get('title', '')
            if work_title:
                row.set_subtitle(work_title)

            # Delete Button
            del_btn = Gtk.Button()
            del_btn.set_icon_name("tac-user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.add_css_class("destructive-action")
            del_btn.set_tooltip_text(_("Remover referência"))
            del_btn.connect("clicked", lambda b, r=ref: self._on_delete_clicked(r))
            
            row.add_suffix(del_btn)
            self.refs_listbox.append(row)

    def _on_add_clicked(self, btn):
        """Handle adding a new reference"""
        author = self.author_row.get_text().strip().upper()
        year = self.year_row.get_text().strip()

        if not author:
            self._show_toast(_("O campo Autor é obrigatório."))
            return

        if not year:
            self._show_toast(_("O campo Ano é obrigatório."))
            return

        # Create reference object
        new_ref = {
            'id': str(uuid.uuid4()),
            'author': author,
            'year': year,
            'created_at': datetime.now().isoformat()
        }

        # Add to project metadata
        if 'references' not in self.project.metadata:
            self.project.metadata['references'] = []
            
        self.project.metadata['references'].append(new_ref)
        
        # Save project
        if self.project_manager.save_project(self.project):
            # Clear inputs
            self.author_row.set_text("")
            self.year_row.set_text("")
            
            # Refresh list
            self._refresh_list()
            self._show_toast(_("Referência adicionada com sucesso!"))
            
            # Focus back on author for rapid entry
            self.author_row.grab_focus()
        else:
            self._show_toast(_("Erro ao salvar projeto."))

    def _on_delete_clicked(self, ref_data):
        """Handle removing a reference"""
        refs = self.project.metadata.get('references', [])
        
        # Filter out the deleted item
        self.project.metadata['references'] = [r for r in refs if r['id'] != ref_data['id']]
        
        # Save and refresh
        if self.project_manager.save_project(self.project):
            self._refresh_list()
            self._show_toast(_("Referência removida."))
        else:
            self._show_toast(_("Erro ao salvar alterações."))

    def _show_toast(self, message):
        toast = Adw.Toast.new(message)
        self.toast_overlay.add_toast(toast)
