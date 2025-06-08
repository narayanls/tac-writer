"""
TAC UI Package
User interface components for the TAC application using GTK4 and libadwaita
"""

from .main_window import MainWindow
from .components import (
    ParagraphEditor,
    TextEditor,
    FormatToolbar,
    ProjectListWidget,
    WelcomeView
)
from .dialogs import (
    NewProjectDialog,
    FormatDialog,
    ExportDialog,
    PreferencesDialog,
    AboutDialog
)

__all__ = [
    # Main window
    'MainWindow',
    
    # Components
    'ParagraphEditor',
    'TextEditor', 
    'FormatToolbar',
    'ProjectListWidget',
    'WelcomeView',
    
    # Dialogs
    'NewProjectDialog',
    'FormatDialog',
    'ExportDialog', 
    'PreferencesDialog',
    'AboutDialog'
]

__version__ = '1.0.0'