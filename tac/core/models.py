"""
TAC Data Models
Pure data models for projects, paragraphs and documents
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class ParagraphType(Enum):
    """Types of paragraphs in academic writing"""
    TOPIC = "topic"                    # Topic sentence paragraph
    ARGUMENT = "argument"              # Argumentation paragraph
    ARGUMENT_QUOTE = "argument_quote"  # Argumentation with quotation
    CONCLUSION = "conclusion"          # Conclusion paragraph
    INTRODUCTION = "introduction"      # Introduction paragraph
    TRANSITION = "transition"          # Transition paragraph


class Paragraph:
    """Represents a single paragraph in a document"""
    
    def __init__(self, paragraph_type: ParagraphType, content: str = "", 
                 paragraph_id: Optional[str] = None):
        self.id = paragraph_id or str(uuid.uuid4())
        self.type = paragraph_type
        self.content = content
        self.created_at = datetime.now()
        self.modified_at = self.created_at
        self.order = 0
        
        # Formatting options
        self.formatting = {
            'font_family': 'Liberation Sans',
            'font_size': 12,
            'line_spacing': 1.5,
            'alignment': 'left',
            'indent_first_line': 1.25,  # cm
            'indent_left': 0.0,         # cm
            'indent_right': 0.0,        # cm
            'bold': False,
            'italic': False,
            'underline': False,
        }
        
        # Special formatting for quotes
        if paragraph_type == ParagraphType.ARGUMENT_QUOTE:
            self.formatting.update({
                'indent_left': 4.0,
                'italic': True,
                'font_size': 11
            })
    
    def update_content(self, content: str) -> None:
        """Update paragraph content"""
        self.content = content
        self.modified_at = datetime.now()
    
    def update_formatting(self, formatting_updates: Dict[str, Any]) -> None:
        """Update paragraph formatting"""
        self.formatting.update(formatting_updates)
        self.modified_at = datetime.now()
    
    def get_word_count(self) -> int:
        """Get word count for this paragraph"""
        return len(self.content.split()) if self.content else 0
    
    def get_character_count(self, include_spaces: bool = True) -> int:
        """Get character count for this paragraph"""
        if not self.content:
            return 0
        return len(self.content) if include_spaces else len(self.content.replace(' ', ''))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert paragraph to dictionary"""
        return {
            'id': self.id,
            'type': self.type.value,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'order': self.order,
            'formatting': self.formatting.copy()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Paragraph':
        """Create paragraph from dictionary"""
        paragraph = cls(
            paragraph_type=ParagraphType(data['type']),
            content=data.get('content', ''),
            paragraph_id=data.get('id')
        )
        
        paragraph.created_at = datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        paragraph.modified_at = datetime.fromisoformat(data.get('modified_at', datetime.now().isoformat()))
        paragraph.order = data.get('order', 0)
        
        if 'formatting' in data:
            paragraph.formatting.update(data['formatting'])
        
        return paragraph


class Project:
    """Represents a writing project with multiple paragraphs"""
    
    def __init__(self, name: str, project_id: Optional[str] = None):
        self.id = project_id or str(uuid.uuid4())
        self.name = name
        self.created_at = datetime.now()
        self.modified_at = self.created_at
        self.paragraphs: List[Paragraph] = []
        
        # Project metadata
        self.metadata = {
            'author': '',
            'description': '',
            'tags': [],
            'version': '1.0',
            'language': 'en',
            'subject': '',
            'institution': '',
            'course': '',
            'professor': '',
            'due_date': None,
        }
        
        # Document formatting
        self.document_formatting = {
            'page_size': 'A4',
            'margins': {
                'top': 2.5,
                'bottom': 2.5,
                'left': 3.0,
                'right': 3.0
            },
            'line_spacing': 1.5,
            'font_family': 'Liberation Sans',
            'font_size': 12,
            'header_footer': {
                'show_page_numbers': True,
                'show_header': False,
                'show_footer': False,
                'header_text': '',
                'footer_text': ''
            }
        }
    
    def add_paragraph(self, paragraph_type: ParagraphType, content: str = "", 
                     position: Optional[int] = None) -> Paragraph:
        """Add a new paragraph to the project"""
        paragraph = Paragraph(paragraph_type, content)
        
        if position is None:
            paragraph.order = len(self.paragraphs)
            self.paragraphs.append(paragraph)
        else:
            paragraph.order = position
            self.paragraphs.insert(position, paragraph)
            self._reorder_paragraphs()
        
        self._update_modified_time()
        return paragraph
    
    def remove_paragraph(self, paragraph_id: str) -> bool:
        """Remove a paragraph by ID"""
        original_count = len(self.paragraphs)
        self.paragraphs = [p for p in self.paragraphs if p.id != paragraph_id]
        
        if len(self.paragraphs) < original_count:
            self._reorder_paragraphs()
            self._update_modified_time()
            return True
        return False
    
    def get_paragraph(self, paragraph_id: str) -> Optional[Paragraph]:
        """Get a paragraph by ID"""
        for paragraph in self.paragraphs:
            if paragraph.id == paragraph_id:
                return paragraph
        return None
    
    def move_paragraph(self, paragraph_id: str, new_position: int) -> bool:
        """Move a paragraph to a new position"""
        paragraph = self.get_paragraph(paragraph_id)
        if not paragraph:
            return False
        
        # Remove from current position
        self.paragraphs = [p for p in self.paragraphs if p.id != paragraph_id]
        
        # Insert at new position
        new_position = max(0, min(new_position, len(self.paragraphs)))
        self.paragraphs.insert(new_position, paragraph)
        
        self._reorder_paragraphs()
        self._update_modified_time()
        return True
    
    def get_statistics(self) -> Dict[str, int]:
        """Get project statistics"""
        total_words = sum(p.get_word_count() for p in self.paragraphs)
        total_chars = sum(p.get_character_count() for p in self.paragraphs)
        total_chars_no_spaces = sum(p.get_character_count(False) for p in self.paragraphs)
        
        # Count paragraphs by type
        type_counts = {}
        for paragraph_type in ParagraphType:
            type_counts[paragraph_type.value] = sum(
                1 for p in self.paragraphs if p.type == paragraph_type
            )
        
        return {
            'total_paragraphs': len(self.paragraphs),
            'total_words': total_words,
            'total_characters': total_chars,
            'total_characters_no_spaces': total_chars_no_spaces,
            'paragraph_types': type_counts
        }
    
    def update_metadata(self, metadata_updates: Dict[str, Any]) -> None:
        """Update project metadata"""
        self.metadata.update(metadata_updates)
        self._update_modified_time()
    
    def update_document_formatting(self, formatting_updates: Dict[str, Any]) -> None:
        """Update document formatting"""
        self.document_formatting.update(formatting_updates)
        self._update_modified_time()
    
    def _reorder_paragraphs(self) -> None:
        """Reorder paragraph numbers"""
        for i, paragraph in enumerate(self.paragraphs):
            paragraph.order = i
    
    def _update_modified_time(self) -> None:
        """Update the modification timestamp"""
        self.modified_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'metadata': self.metadata.copy(),
            'document_formatting': self.document_formatting.copy(),
            'paragraphs': [p.to_dict() for p in self.paragraphs],
            'statistics': self.get_statistics()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Create project from dictionary"""
        project = cls(
            name=data['name'],
            project_id=data.get('id')
        )
        
        project.created_at = datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        project.modified_at = datetime.fromisoformat(data.get('modified_at', datetime.now().isoformat()))
        
        if 'metadata' in data:
            project.metadata.update(data['metadata'])
        
        if 'document_formatting' in data:
            project.document_formatting.update(data['document_formatting'])
        
        # Load paragraphs
        if 'paragraphs' in data:
            project.paragraphs = [
                Paragraph.from_dict(p_data) for p_data in data['paragraphs']
            ]
            # Sort by order
            project.paragraphs.sort(key=lambda p: p.order)
        
        return project


class DocumentTemplate:
    """Template for creating new documents"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.paragraph_structure: List[ParagraphType] = []
        self.default_formatting = {}
        self.metadata_template = {}
    
    def create_project(self, project_name: str) -> Project:
        """Create a new project based on this template"""
        project = Project(project_name)
        
        # Apply template metadata
        project.metadata.update(self.metadata_template)
        
        # Apply template formatting
        if self.default_formatting:
            project.document_formatting.update(self.default_formatting)
        
        # Create paragraphs from structure
        for paragraph_type in self.paragraph_structure:
            project.add_paragraph(paragraph_type)
        
        return project


# Predefined templates
ACADEMIC_ESSAY_TEMPLATE = DocumentTemplate(
    name="Academic Essay",
    description="Standard academic essay structure"
)
ACADEMIC_ESSAY_TEMPLATE.paragraph_structure = [
    ParagraphType.INTRODUCTION,
    ParagraphType.TOPIC,
    ParagraphType.ARGUMENT,
    ParagraphType.ARGUMENT_QUOTE,
    ParagraphType.CONCLUSION
]

RESEARCH_PAPER_TEMPLATE = DocumentTemplate(
    name="Research Paper",
    description="Extended research paper structure"
)
RESEARCH_PAPER_TEMPLATE.paragraph_structure = [
    ParagraphType.INTRODUCTION,
    ParagraphType.TOPIC,
    ParagraphType.ARGUMENT,
    ParagraphType.ARGUMENT_QUOTE,
    ParagraphType.TRANSITION,
    ParagraphType.ARGUMENT,
    ParagraphType.ARGUMENT_QUOTE,
    ParagraphType.CONCLUSION
]

DEFAULT_TEMPLATES = [
    ACADEMIC_ESSAY_TEMPLATE,
    RESEARCH_PAPER_TEMPLATE
]