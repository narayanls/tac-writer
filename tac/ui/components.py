"""
TAC UI Components
Reusable UI components for the TAC application
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GObject, Pango

from core.models import Paragraph, ParagraphType, DEFAULT_TEMPLATES
from core.services import ProjectManager
from utils.helpers import TextHelper, FormatHelper


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
        # App icon and title
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_halign(Gtk.Align.CENTER)
        
        # Icon
        icon = Gtk.Image.new_from_icon_name("document-edit-symbolic")
        icon.set_pixel_size(96)
        icon.add_css_class("welcome-icon")
        content_box.append(icon)
        
        # Title
        title = Gtk.Label()
        title.set_markup("<span size='xx-large' weight='bold'>Welcome to TAC</span>")
        title.set_halign(Gtk.Align.CENTER)
        content_box.append(title)
        
        # Subtitle
        subtitle = Gtk.Label()
        subtitle.set_markup("<span size='large'>Text Analysis and Creation</span>")
        subtitle.set_halign(Gtk.Align.CENTER)
        subtitle.add_css_class("dim-label")
        content_box.append(subtitle)
        
        # Description
        description = Gtk.Label()
        description.set_text("Create structured academic texts with guided paragraph types")
        description.set_halign(Gtk.Align.CENTER)
        description.set_wrap(True)
        description.set_max_width_chars(50)
        content_box.append(description)
        
        self.append(content_box)
    
    def _create_template_section(self):
        """Create template selection section"""
        template_group = Adw.PreferencesGroup()
        template_group.set_title("Start Writing")
        template_group.set_description("Choose a template to get started")
        
        # Template cards
        for template in DEFAULT_TEMPLATES:
            row = Adw.ActionRow()
            row.set_title(template.name)
            row.set_subtitle(template.description)
            
            # Start button
            start_button = Gtk.Button()
            start_button.set_label("Start")
            start_button.add_css_class("suggested-action")
            start_button.set_valign(Gtk.Align.CENTER)
            start_button.connect('clicked', lambda btn, tmpl=template.name: self.emit('create-project', tmpl))
            
            row.add_suffix(start_button)
            template_group.add(row)
        
        self.append(template_group)
    
    def _create_recent_section(self):
        """Create recent projects section"""
        # TODO: Implement recent projects display
        # This would show recently opened projects
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
        self.search_entry.set_placeholder_text("Search projects...")
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
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.add_css_class("heading")
        header_box.append(name_label)
        
        # Spacer
        header_box.append(Gtk.Box())
        header_box.set_hexpand(True)
        
        # Modification date
        if project_info.get('modified_at'):
            from datetime import datetime
            try:
                modified_dt = datetime.fromisoformat(project_info['modified_at'])
                date_label = Gtk.Label()
                date_label.set_text(FormatHelper.format_datetime(modified_dt, 'short'))
                date_label.add_css_class("caption")
                date_label.add_css_class("dim-label")
                header_box.append(date_label)
            except:
                pass
        
        box.append(header_box)
        
        # Statistics
        stats = project_info.get('statistics', {})
        if stats:
            stats_label = Gtk.Label()
            words = stats.get('total_words', 0)
            paragraphs = stats.get('total_paragraphs', 0)
            stats_text = f"{words} words • {paragraphs} paragraphs"
            stats_label.set_text(stats_text)
            stats_label.set_halign(Gtk.Align.START)
            stats_label.add_css_class("caption")
            stats_label.add_css_class("dim-label")
            box.append(stats_label)
        
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


class ParagraphEditor(Gtk.Box):
    """Editor for individual paragraphs"""
    
    __gtype_name__ = 'TacParagraphEditor'
    __gsignals__ = {
        'content-changed': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'remove-requested': (GObject.SIGNAL_RUN_FIRST, None, (str,)),
    }
    
    def __init__(self, paragraph: Paragraph, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        
        self.paragraph = paragraph
        self.text_view = None
        self.text_buffer = None
        
        self.set_spacing(8)
        self.add_css_class("card")
        self.set_margin_start(4)
        self.set_margin_end(4)
        self.set_margin_top(4)
        self.set_margin_bottom(4)
        
        # Create header
        self._create_header()
        
        # Create text editor
        self._create_text_editor()
        
        # Apply initial formatting
        self._apply_formatting()
    
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
        
        # Word count
        self.word_count_label = Gtk.Label()
        self.word_count_label.add_css_class("caption")
        self.word_count_label.add_css_class("dim-label")
        self._update_word_count()
        header_box.append(self.word_count_label)
        
        # Format button
        format_button = Gtk.Button()
        format_button.set_icon_name("format-text-bold-symbolic")
        format_button.set_tooltip_text("Format paragraph")
        format_button.add_css_class("flat")
        format_button.connect('clicked', self._on_format_clicked)
        header_box.append(format_button)
        
        # Remove button
        remove_button = Gtk.Button()
        remove_button.set_icon_name("edit-delete-symbolic")
        remove_button.set_tooltip_text("Remove paragraph")
        remove_button.add_css_class("flat")
        remove_button.connect('clicked', self._on_remove_clicked)
        header_box.append(remove_button)
        
        self.append(header_box)
    
    def _create_text_editor(self):
        """Create the text editing area"""
        # Text buffer
        self.text_buffer = Gtk.TextBuffer()
        self.text_buffer.set_text(self.paragraph.content)
        self.text_buffer.connect('changed', self._on_text_changed)
        
        # Text view
        self.text_view = Gtk.TextView()
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
    
    def _get_type_label(self) -> str:
        """Get display label for paragraph type"""
        type_labels = {
            ParagraphType.INTRODUCTION: "Introduction",
            ParagraphType.TOPIC: "Topic Sentence",
            ParagraphType.ARGUMENT: "Argument",
            ParagraphType.ARGUMENT_QUOTE: "Argument with Quote",
            ParagraphType.CONCLUSION: "Conclusion",
            ParagraphType.TRANSITION: "Transition"
        }
        return type_labels.get(self.paragraph.type, "Paragraph")
    
    def _apply_formatting(self):
        """Apply formatting to text view based on paragraph settings"""
        formatting = self.paragraph.formatting
        
        # Create CSS for font styling
        font_family = formatting.get('font_family', 'Liberation Sans')
        font_size = formatting.get('font_size', 12)
        
        css_style = f"""
        textview {{
            font-family: "{font_family}";
            font-size: {font_size}pt;
        }}
        """
        
        # Apply bold/italic through CSS if needed
        if formatting.get('bold', False):
            css_style += "textview { font-weight: bold; }"
        
        if formatting.get('italic', False):
            css_style += "textview { font-style: italic; }"
        
        # Create CSS provider
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css_style.encode())
        
        # Apply to text view
        style_context = self.text_view.get_style_context()
        style_context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        # Apply indentation for quotes
        if self.paragraph.type == ParagraphType.ARGUMENT_QUOTE:
            self.text_view.set_left_margin(40)
            self.text_view.set_right_margin(40)
    
    def _update_word_count(self):
        """Update word count display"""
        word_count = self.paragraph.get_word_count()
        self.word_count_label.set_text(f"{word_count} words")
    
    def _on_text_changed(self, buffer):
        """Handle text changes"""
        # Get text from buffer
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        text = buffer.get_text(start_iter, end_iter, False)
        
        # Update paragraph content
        self.paragraph.update_content(text)
        
        # Update word count
        self._update_word_count()
        
        # Emit signal
        self.emit('content-changed')
    
    def _on_format_clicked(self, button):
        """Handle format button click"""
        # TODO: Show format dialog
        print(f"Format paragraph {self.paragraph.id}")
    
    def _on_remove_clicked(self, button):
        """Handle remove button click"""
        # Show confirmation dialog
        dialog = Adw.MessageDialog.new(
            self.get_root(),
            "Remove Paragraph?",
            "This action cannot be undone."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
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


class TextEditor(Gtk.Box):
    """Advanced text editor component"""
    
    __gtype_name__ = 'TacTextEditor'
    __gsignals__ = {
        'content-changed': (GObject.SIGNAL_RUN_FIRST, None, (str,)),
    }
    
    def __init__(self, initial_text: str = "", **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        
        # Text buffer and view
        self.text_buffer = Gtk.TextBuffer()
        self.text_buffer.set_text(initial_text)
        self.text_buffer.connect('changed', self._on_text_changed)
        
        self.text_view = Gtk.TextView()
        self.text_view.set_buffer(self.text_buffer)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_accepts_tab(True)
        
        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(self.text_view)
        scrolled.set_vexpand(True)
        
        self.append(scrolled)
    
    def get_text(self) -> str:
        """Get current text content"""
        start_iter = self.text_buffer.get_start_iter()
        end_iter = self.text_buffer.get_end_iter()
        return self.text_buffer.get_text(start_iter, end_iter, False)
    
    def set_text(self, text: str):
        """Set text content"""
        self.text_buffer.set_text(text)
    
    def _on_text_changed(self, buffer):
        """Handle text changes"""
        text = self.get_text()
        self.emit('content-changed', text)


class FormatToolbar(Gtk.Box):
    """Toolbar for text formatting options"""
    
    __gtype_name__ = 'TacFormatToolbar'
    __gsignals__ = {
        'format-changed': (GObject.SIGNAL_RUN_FIRST, None, (str, object)),
    }
    
    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, **kwargs)
        
        self.set_spacing(6)
        self.add_css_class("toolbar")
        
        # Font family
        self.font_combo = Gtk.ComboBoxText()
        fonts = ["Liberation Sans", "Liberation Serif", "Times New Roman", "Arial", "Calibri"]
        for font in fonts:
            self.font_combo.append_text(font)
        self.font_combo.set_active(0)
        self.font_combo.connect('changed', lambda w: self.emit('format-changed', 'font_family', w.get_active_text()))
        self.append(self.font_combo)
        
        # Font size
        self.size_spin = Gtk.SpinButton()
        self.size_spin.set_range(8, 72)
        self.size_spin.set_value(12)
        self.size_spin.set_increments(1, 2)
        self.size_spin.connect('value-changed', lambda w: self.emit('format-changed', 'font_size', int(w.get_value())))
        self.append(self.size_spin)
        
        # Separator
        self.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        
        # Bold button
        self.bold_button = Gtk.ToggleButton()
        self.bold_button.set_icon_name("format-text-bold-symbolic")
        self.bold_button.set_tooltip_text("Bold")
        self.bold_button.connect('toggled', lambda w: self.emit('format-changed', 'bold', w.get_active()))
        self.append(self.bold_button)
        
        # Italic button
        self.italic_button = Gtk.ToggleButton()
        self.italic_button.set_icon_name("format-text-italic-symbolic")
        self.italic_button.set_tooltip_text("Italic")
        self.italic_button.connect('toggled', lambda w: self.emit('format-changed', 'italic', w.get_active()))
        self.append(self.italic_button)
        
        # Underline button
        self.underline_button = Gtk.ToggleButton()
        self.underline_button.set_icon_name("format-text-underline-symbolic")
        self.underline_button.set_tooltip_text("Underline")
        self.underline_button.connect('toggled', lambda w: self.emit('format-changed', 'underline', w.get_active()))
        self.append(self.underline_button)
    
    def update_from_formatting(self, formatting: dict):
        """Update toolbar state from formatting dictionary"""
        # Update font family
        font_family = formatting.get('font_family', 'Liberation Sans')
        for i in range(self.font_combo.get_model().iter_n_children(None)):
            if self.font_combo.get_model().get_value(self.font_combo.get_model().iter_nth_child(None, i), 0) == font_family:
                self.font_combo.set_active(i)
                break
        
        # Update font size
        self.size_spin.set_value(formatting.get('font_size', 12))
        
        # Update toggle buttons
        self.bold_button.set_active(formatting.get('bold', False))
        self.italic_button.set_active(formatting.get('italic', False))
        self.underline_button.set_active(formatting.get('underline', False))