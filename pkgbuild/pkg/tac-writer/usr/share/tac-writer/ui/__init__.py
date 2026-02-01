"""
TAC UI Package
User interface components for the TAC application using GTK4 and libadwaita
"""

from .main_window import MainWindow
from .components import (
    ParagraphEditor,
    TextEditor,
    ProjectListWidget,
    WelcomeView
)
from .dialogs import (
    NewProjectDialog,
    #FormatDialog,
    ExportDialog,
    PreferencesDialog,
    AboutDialog,
    BackupManagerDialog
)

from core.config import Config

__all__ = [
    # Main window
    'MainWindow',
    
    # Components
    'ParagraphEditor',
    'TextEditor', 
    'ProjectListWidget',
    'WelcomeView',
    
    # Dialogs
    'NewProjectDialog',
    #'FormatDialog',
    'ExportDialog', 
    'PreferencesDialog',
    'AboutDialog'
    'BackupManagerDialog'
]

__version__ = Config.APP_VERSION
