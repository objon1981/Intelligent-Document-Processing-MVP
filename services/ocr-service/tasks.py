from ocr_processor import OCRProcessor
from config import settings

processor = OCRProcessor(settings())

def run_ocr_job(file_content, filename, language="eng", file_id=None, confidence_threshold=30.0):
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(
        processor.process_file(
            file_content=file_content,
            filename=filename,
            language=language,
            file_id=file_id,
            confidence_threshold=confidence_threshold
        )
    )
    return result.model_dump()
