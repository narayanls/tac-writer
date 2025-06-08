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
    RESEARCH_PAPER_TEMPLATE,
    DEFAULT_TEMPLATES
)
from .services import ProjectManager, ExportService

__all__ = [
    # Configuration
    'Config',
    
    # Models
    'Project',
    'Paragraph', 
    'ParagraphType',
    'DocumentTemplate',
    'ACADEMIC_ESSAY_TEMPLATE',
    'RESEARCH_PAPER_TEMPLATE', 
    'DEFAULT_TEMPLATES',
    
    # Services
    'ProjectManager',
    'ExportService'
]

__version__ = '1.0.0'