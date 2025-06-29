# ocr_processor.py
import io
from multiprocessing.pool import MapResult
import pytesseract
import cv2
import numpy as np
from PIL import Image
from pdf2image import convert_from_bytes
import tempfile
import os
import logging
from typing import List, Tuple, Dict
import time
from datetime import datetime
from models import OCRResult, TextBlock


logger = logging.getLogger(__name__)

class OCRProcessor:
    def __init__(self, settings):
        self.settings = settings
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        
        # Create temp directory if it doesn't exist
        os.makedirs(settings.temp_dir, exist_ok=True)
    
    async def process_file(self, file_content: bytes, filename: str, 
                          language: str = "eng", file_id: str = None, # type: ignore
                          confidence_threshold: float = 30.0) -> OCRResult:
        """Process a file and extract text using OCR"""
        start_time = time.time()
        
        try:
            # Validate language
            if language not in self.settings.supported_languages:
                raise ValueError(f"Unsupported language: {language}")
            
            # Determine file type and process accordingly
            file_ext = filename.lower().split('.')[-1]
            
            if file_ext == 'pdf':
                pages = await self._process_pdf(file_content)
            elif file_ext in ['jpg', 'jpeg', 'png', 'tiff', 'tif', 'bmp']:
                pages = [await self._process_image(file_content)]
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
            
            # Extract text from all pages
            text_blocks = []
            full_text_parts = []
            confidences = []
            
            for page_num, page_image in enumerate(pages, 1):
                page_blocks = await self._extract_text_from_image(
                    page_image, language, page_num, confidence_threshold
                )
                text_blocks.extend(page_blocks)
                
                # Collect page text and confidences
                page_text = "\n".join([block.text for block in page_blocks])
                if page_text.strip():
                    full_text_parts.append(f"--- Page {page_num} ---\n{page_text}")
                
                page_confidences = [block.confidence for block in page_blocks if block.confidence > 0]
                confidences.extend(page_confidences)
            
            # Calculate overall confidence
            overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            processing_time = time.time() - start_time
            
            return OCRResult(
                file_id=file_id,
                processing_time=round(processing_time, 2),
                total_pages=len(pages),
                language=language,
                overall_confidence=round(overall_confidence, 2),
                text_blocks=text_blocks,
                full_text="\n\n".join(full_text_parts),
                metadata={
                    "filename": filename,
                    "file_size": len(file_content),
                    "confidence_threshold": confidence_threshold,
                    "total_text_blocks": len(text_blocks)
                },
                timestamp=datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            logger.error(f"OCR processing failed: {str(e)}")
            raise
    
    async def _process_pdf(self, pdf_content: bytes) -> List[np.ndarray]:
        """Convert PDF to images"""
        try:
            images = convert_from_bytes(pdf_content, dpi=300)
            return [np.array(img) for img in images]
        except Exception as e:
            logger.error(f"PDF conversion failed: {str(e)}")
            raise ValueError(f"Failed to process PDF: {str(e)}")
    
    async def _process_image(self, image_content: bytes) -> np.ndarray:
        """Process image file"""
        try:
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_content))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            return np.array(image)
        except Exception as e:
            logger.error(f"Image processing failed: {str(e)}")
            raise ValueError(f"Failed to process image: {str(e)}")
    
    async def _extract_text_from_image(self, image: np.ndarray, language: str, 
                                     page_num: int, confidence_threshold: float) -> List[TextBlock]:
        """Extract text from image using Tesseract"""
        try:
            # Preprocess image for better OCR
            processed_image = await self._preprocess_image(image)
            
            # Get detailed OCR data
            ocr_data = pytesseract.image_to_data(
                processed_image,
                lang=language,
                output_type=pytesseract.Output.DICT
            )
            
            text_blocks = []
            n_boxes = len(ocr_data['text'])
            
            for i in range(n_boxes):
                confidence = float(ocr_data['conf'][i])
                text = ocr_data['text'][i].strip()
                
                # Filter by confidence and non-empty text
                if confidence >= confidence_threshold and text:
                    bbox = [
                        int(ocr_data['left'][i]),
                        int(ocr_data['top'][i]),
                        int(ocr_data['width'][i]),
                        int(ocr_data['height'][i])
                    ]
                    
                    text_blocks.append(TextBlock(
                        text=text,
                        confidence=round(confidence, 2),
                        bbox=bbox,
                        page=page_num
                    ))
            
            return text_blocks
            
        except Exception as e:
            logger.error(f"Text extraction failed: {str(e)}")
            raise
    
    async def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR results"""
        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image
            
            # Apply denoising
            denoised = cv2.fastNlMeansDenoising(gray)
            
            # Apply adaptive thresholding
            thresh = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            return thresh
            
        except Exception as e:
            logger.warning(f"Image preprocessing failed, using original: {str(e)}")
            return image
