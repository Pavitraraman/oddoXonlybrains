"""
OCR background tasks for receipt processing.
"""

import logging
from celery import current_task
from app.celery_app import celery_app
from app.services.ocr_service import ocr_service
from app.database import AsyncSessionLocal
from app.models import Expense, OCRResult

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='app.tasks.ocr_tasks.process_receipt_ocr')
def process_receipt_ocr(self, expense_id: str, receipt_url: str):
    """
    Process receipt image with OCR in the background.
    
    Args:
        expense_id: ID of the expense
        receipt_url: URL of the receipt image
    """
    try:
        logger.info(f"Starting OCR processing for expense {expense_id}")
        
        # Update task progress
        self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100, 'status': 'Loading image'})
        
        # Process receipt with OCR
        ocr_result = ocr_service.process_receipt(receipt_url)
        
        self.update_state(state='PROGRESS', meta={'current': 50, 'total': 100, 'status': 'Processing OCR'})
        
        # Save OCR results to database
        async def save_ocr_result():
            async with AsyncSessionLocal() as db:
                try:
                    ocr_record = OCRResult(
                        expense_id=expense_id,
                        receipt_url=receipt_url,
                        detected_amount=ocr_result.get('detected_amount'),
                        detected_currency=ocr_result.get('detected_currency'),
                        detected_date=ocr_result.get('detected_date'),
                        confidence_score=ocr_result.get('confidence_score', 0.0),
                        raw_text=ocr_result.get('raw_text', ''),
                        is_verified=False
                    )
                    
                    db.add(ocr_record)
                    await db.commit()
                    
                    logger.info(f"OCR results saved for expense {expense_id}")
                    return True
                    
                except Exception as e:
                    logger.error(f"Error saving OCR results: {e}")
                    await db.rollback()
                    return False
        
        # Run async function
        import asyncio
        success = asyncio.run(save_ocr_result())
        
        self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100, 'status': 'Completed'})
        
        if success:
            logger.info(f"OCR processing completed for expense {expense_id}")
            return {
                'status': 'success',
                'result': ocr_result,
                'expense_id': expense_id
            }
        else:
            logger.error(f"OCR processing failed for expense {expense_id}")
            return {
                'status': 'error',
                'message': 'Failed to save OCR results',
                'expense_id': expense_id
            }
            
    except Exception as e:
        logger.error(f"OCR processing error for expense {expense_id}: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'expense_id': expense_id}
        )
        raise


@celery_app.task(name='app.tasks.ocr_tasks.batch_process_receipts')
def batch_process_receipts(receipt_urls: list):
    """
    Process multiple receipts in batch.
    
    Args:
        receipt_urls: List of receipt URLs to process
    """
    logger.info(f"Starting batch OCR processing for {len(receipt_urls)} receipts")
    
    results = []
    for i, receipt_url in enumerate(receipt_urls):
        try:
            result = process_receipt_ocr.delay(None, receipt_url)
            results.append(result.get(timeout=300))  # 5 minute timeout
            logger.info(f"Processed receipt {i+1}/{len(receipt_urls)}")
        except Exception as e:
            logger.error(f"Error processing receipt {receipt_url}: {e}")
            results.append({'status': 'error', 'message': str(e)})
    
    logger.info(f"Batch OCR processing completed. {len(results)} receipts processed.")
    return results

