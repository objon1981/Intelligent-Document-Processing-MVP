# Makes docetl a package
# docetl/__init__.py
"""
DocETL Service - Document Processing Orchestration Service

This service coordinates document processing workflows by:
- Receiving document processing requests
- Managing job queues and status
- Coordinating with file-organizer and OCR services
- Providing job status and results APIs
"""

__version__ = "1.0.0"
__author__ = "Document Processing Team"

from .config import settings

__all__ = ["settings"]