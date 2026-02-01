"""
TAC Core Package
Core functionality for the TAC application including models, services and configuration
"""

from .config import Config
from .models import (
    Project, 
    Paragraph, 
    ParagraphType, 
    DocumentTemplate,
    ACADEMIC_ESSAY_TEMPLATE,
    DEFAULT_TEMPLATES
    
)
from .services import ProjectManager, ExportService
from .ai_assistant import WritingAiAssistant

__all__ = [
    # Configuration
    'Config',
    
    # Models
    'Project',
    'Paragraph', 
    'ParagraphType',
    'DocumentTemplate',
    'ACADEMIC_ESSAY_TEMPLATE',
    'DEFAULT_TEMPLATES',
    
    # Services
    'ProjectManager',
    'ExportService',
    'WritingAiAssistant'
]

__version__ = Config.APP_VERSION
