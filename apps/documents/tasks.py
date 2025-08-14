"""
Celery tasks for document processing.
Handles fetching, parsing, and extracting content from opportunity documents.
"""

import logging
import os
import requests
from typing import List, Dict, Any, Optional
from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone

from .models import Document
from apps.opportunities.models import Opportunity

logger = logging.getLogger('blackcoral.documents.tasks')


@shared_task(bind=True, max_retries=3)
def fetch_opportunity_documents(self, opportunity_id: int, document_links: Optional[List[Dict]] = None):
    """
    Fetch and store documents for an opportunity.
    
    Args:
        opportunity_id: ID of the opportunity
        document_links: Optional list of document links from API
    """
    try:
        opportunity = Opportunity.objects.get(id=opportunity_id)
        
        # Get document links from opportunity if not provided
        if not document_links:
            document_links = []
            
            # Extract from raw_data if available
            if opportunity.raw_data:
                # Resource links
                for link in opportunity.raw_data.get('resourceLinks', []):
                    document_links.append({
                        'url': link,
                        'type': 'resource',
                        'name': link.split('/')[-1] if '/' in link else 'Resource'
                    })
                
                # Additional info link
                if opportunity.raw_data.get('additionalInfoLink'):
                    document_links.append({
                        'url': opportunity.raw_data['additionalInfoLink'],
                        'type': 'additional_info',
                        'name': 'Additional Information'
                    })
        
        if not document_links:
            logger.info(f"No documents found for opportunity {opportunity_id}")
            opportunity.documents_fetched = True
            opportunity.save()
            return {'status': 'success', 'documents_count': 0}
        
        # Fetch each document
        fetched_count = 0
        for doc_info in document_links:
            try:
                # Check if document already exists
                if Document.objects.filter(
                    opportunity=opportunity,
                    source_url=doc_info['url']
                ).exists():
                    logger.debug(f"Document already exists: {doc_info['url']}")
                    continue
                
                # Fetch document
                fetch_single_document.delay(
                    opportunity_id=opportunity_id,
                    url=doc_info['url'],
                    doc_type=doc_info.get('type', 'unknown'),
                    doc_name=doc_info.get('name', 'Document')
                )
                fetched_count += 1
                
            except Exception as e:
                logger.error(f"Error queuing document fetch: {e}")
        
        opportunity.documents_fetched = True
        opportunity.save()
        
        return {
            'status': 'success',
            'documents_queued': fetched_count,
            'total_links': len(document_links)
        }
        
    except Opportunity.DoesNotExist:
        logger.error(f"Opportunity {opportunity_id} not found")
        return {'status': 'error', 'message': 'Opportunity not found'}
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def fetch_single_document(self, opportunity_id: int, url: str, doc_type: str, doc_name: str):
    """
    Fetch a single document from a URL.
    """
    try:
        opportunity = Opportunity.objects.get(id=opportunity_id)
        
        # Download document
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'BLACK CORAL Government Contracting System'
        })
        response.raise_for_status()
        
        # Determine file type from content-type or URL
        content_type = response.headers.get('Content-Type', '')
        if 'pdf' in content_type:
            file_type = 'PDF'
        elif 'word' in content_type or 'docx' in url:
            file_type = 'DOCX'
        elif 'excel' in content_type or 'xlsx' in url or 'xls' in url:
            file_type = 'XLS'
        elif 'zip' in content_type:
            file_type = 'ZIP'
        elif 'html' in content_type:
            file_type = 'HTML'
        else:
            file_type = 'OTHER'
        
        # Create document record
        document = Document.objects.create(
            opportunity=opportunity,
            title=doc_name,
            file_type=file_type,
            file_size=len(response.content),
            source_url=url,
            document_type=doc_type,
            processing_status='pending'
        )
        
        # Save file
        file_name = f"{opportunity.solicitation_number}_{document.id}.{file_type.lower()}"
        document.file_path.save(file_name, ContentFile(response.content))
        
        logger.info(f"Downloaded document: {file_name}")
        
        # Queue for processing
        parse_document.delay(document.id)
        
        return {
            'status': 'success',
            'document_id': document.id,
            'file_type': file_type
        }
        
    except requests.RequestException as e:
        logger.error(f"Error downloading document from {url}: {e}")
        raise self.retry(exc=e, countdown=600)
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def parse_document(self, document_id: int):
    """
    Parse and extract text from a document.
    """
    try:
        document = Document.objects.get(id=document_id)
        document.processing_status = 'processing'
        document.save()
        
        # Route to appropriate parser based on file type
        if document.file_type == 'PDF':
            text = parse_pdf_document(document)
        elif document.file_type in ['DOCX', 'DOC']:
            text = parse_word_document(document)
        elif document.file_type == 'HTML':
            text = parse_html_document(document)
        elif document.file_type in ['XLS', 'XLSX']:
            text = parse_excel_document(document)
        else:
            text = ''
            logger.warning(f"Unsupported file type: {document.file_type}")
        
        # Save extracted text
        document.extracted_text = text
        document.processing_status = 'completed'
        document.processed_at = timezone.now()
        document.save()
        
        logger.info(f"Parsed document {document_id}: {len(text)} characters extracted")
        
        # Trigger AI analysis if text was extracted
        if text and len(text) > 100:
            from apps.ai_integration.tasks import analyze_document
            analyze_document.delay(document_id)
        
        return {
            'status': 'success',
            'document_id': document_id,
            'text_length': len(text)
        }
        
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found")
        return {'status': 'error', 'message': 'Document not found'}
    except Exception as e:
        logger.error(f"Error parsing document: {e}")
        document.processing_status = 'failed'
        document.processing_error = str(e)
        document.save()
        raise self.retry(exc=e, countdown=600)


def parse_pdf_document(document: Document) -> str:
    """Parse PDF document and extract text."""
    try:
        import fitz  # PyMuPDF
        
        text = []
        with fitz.open(document.file_path.path) as pdf:
            for page_num, page in enumerate(pdf):
                page_text = page.get_text()
                if page_text:
                    text.append(f"Page {page_num + 1}:\n{page_text}")
        
        return '\n\n'.join(text)
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        return ''


def parse_word_document(document: Document) -> str:
    """Parse Word document and extract text."""
    try:
        from docx import Document as DocxDocument
        
        doc = DocxDocument(document.file_path.path)
        text = []
        
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text.append(paragraph.text)
        
        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = '\t'.join(cell.text for cell in row.cells)
                if row_text.strip():
                    text.append(row_text)
        
        return '\n\n'.join(text)
    except Exception as e:
        logger.error(f"Error parsing Word document: {e}")
        return ''


def parse_html_document(document: Document) -> str:
    """Parse HTML document and extract text."""
    try:
        from bs4 import BeautifulSoup
        
        with open(document.file_path.path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text and clean it up
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    except Exception as e:
        logger.error(f"Error parsing HTML: {e}")
        return ''


def parse_excel_document(document: Document) -> str:
    """Parse Excel document and extract text."""
    try:
        import pandas as pd
        
        # Read all sheets
        excel_file = pd.ExcelFile(document.file_path.path)
        text = []
        
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name)
            text.append(f"Sheet: {sheet_name}")
            text.append(df.to_string())
        
        return '\n\n'.join(text)
    except Exception as e:
        logger.error(f"Error parsing Excel: {e}")
        return ''


@shared_task
def process_pending_documents():
    """
    Process all pending documents (runs periodically).
    """
    pending_docs = Document.objects.filter(processing_status='pending')
    
    for doc in pending_docs[:10]:  # Process max 10 at a time
        parse_document.delay(doc.id)
    
    return {
        'status': 'success',
        'documents_queued': min(pending_docs.count(), 10)
    }


@shared_task
def cleanup_old_documents():
    """
    Clean up old documents from inactive opportunities.
    """
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=180)
    
    old_documents = Document.objects.filter(
        opportunity__is_active=False,
        created_at__lt=cutoff_date
    )
    
    count = 0
    for doc in old_documents:
        if doc.file_path:
            doc.file_path.delete()
        doc.delete()
        count += 1
    
    return {
        'status': 'success',
        'deleted_count': count
    }