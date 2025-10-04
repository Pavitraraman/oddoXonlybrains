"""
OCR (Optical Character Recognition) service for receipt processing.
Extracts text and structured data from receipt images for expense management.
"""

import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any, List
from pathlib import Path

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np

from config import settings
from app.schemas import OCRResultCreate
from app.services.currency_service import currency_service

logger = logging.getLogger(__name__)


class OCRService:
    """Service for processing receipt images and extracting structured data."""
    
    def __init__(self):
        self.tesseract_cmd = settings.tesseract_cmd
        self.ocr_language = settings.ocr_language
        self.supported_currencies = [
            "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "INR", "BRL",
            "KRW", "SGD", "NZD", "MXN", "HKD", "NOK", "SEK", "DKK", "PLN", "CZK",
            "HUF", "ILS", "CLP", "PHP", "AED", "COP", "SAR", "MYR", "RON", "BGN"
        ]
        
        # Configure Tesseract
        pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
    
    async def process_receipt(self, image_path: str) -> Dict[str, Any]:
        """
        Process a receipt image and extract structured data.
        
        Args:
            image_path: Path to the receipt image file
            
        Returns:
            Dict[str, Any]: Extracted data including amount, currency, date, etc.
        """
        try:
            # Load and preprocess image
            processed_image = await self._preprocess_image(image_path)
            
            # Extract text using OCR
            raw_text = await self._extract_text(processed_image)
            
            # Parse structured data from text
            parsed_data = await self._parse_receipt_data(raw_text)
            
            return {
                "raw_text": raw_text,
                "detected_amount": parsed_data.get("amount"),
                "detected_currency": parsed_data.get("currency"),
                "detected_date": parsed_data.get("date"),
                "confidence_score": parsed_data.get("confidence", 0.0),
                "merchant_name": parsed_data.get("merchant_name"),
                "items": parsed_data.get("items", []),
                "tax_amount": parsed_data.get("tax_amount"),
                "total_amount": parsed_data.get("total_amount")
            }
            
        except Exception as e:
            logger.error(f"Error processing receipt {image_path}: {e}")
            return {
                "raw_text": "",
                "detected_amount": None,
                "detected_currency": None,
                "detected_date": None,
                "confidence_score": 0.0,
                "error": str(e)
            }
    
    async def _preprocess_image(self, image_path: str) -> Image.Image:
        """
        Preprocess image for better OCR results.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Image.Image: Preprocessed image
        """
        # Load image
        image = Image.open(image_path)
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert to numpy array for OpenCV processing
        img_array = np.array(image)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations to clean up the image
        kernel = np.ones((1, 1), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
        
        # Convert back to PIL Image
        processed_image = Image.fromarray(cleaned)
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(processed_image)
        processed_image = enhancer.enhance(2.0)
        
        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(processed_image)
        processed_image = enhancer.enhance(2.0)
        
        return processed_image
    
    async def _extract_text(self, image: Image.Image) -> str:
        """
        Extract text from preprocessed image using Tesseract OCR.
        
        Args:
            image: Preprocessed PIL Image
            
        Returns:
            str: Extracted text
        """
        try:
            # Configure Tesseract for better results
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,:/-$€£¥₹ '
            
            # Extract text
            text = pytesseract.image_to_string(image, config=custom_config)
            
            # Clean up the text
            text = re.sub(r'\s+', ' ', text.strip())
            
            return text
            
        except Exception as e:
            logger.error(f"Error extracting text with OCR: {e}")
            return ""
    
    async def _parse_receipt_data(self, text: str) -> Dict[str, Any]:
        """
        Parse structured data from receipt text.
        
        Args:
            text: Raw text from OCR
            
        Returns:
            Dict[str, Any]: Parsed receipt data
        """
        parsed_data = {
            "amount": None,
            "currency": None,
            "date": None,
            "merchant_name": None,
            "items": [],
            "tax_amount": None,
            "total_amount": None,
            "confidence": 0.0
        }
        
        confidence_score = 0.0
        
        # Extract currency and amount
        amount_currency = await self._extract_amount_and_currency(text)
        if amount_currency:
            parsed_data["amount"] = amount_currency["amount"]
            parsed_data["currency"] = amount_currency["currency"]
            parsed_data["total_amount"] = amount_currency["amount"]
            confidence_score += 0.4
        
        # Extract date
        extracted_date = await self._extract_date(text)
        if extracted_date:
            parsed_data["date"] = extracted_date
            confidence_score += 0.2
        
        # Extract merchant name
        merchant_name = await self._extract_merchant_name(text)
        if merchant_name:
            parsed_data["merchant_name"] = merchant_name
            confidence_score += 0.1
        
        # Extract tax amount
        tax_amount = await self._extract_tax_amount(text)
        if tax_amount:
            parsed_data["tax_amount"] = tax_amount
            confidence_score += 0.1
        
        # Extract items
        items = await self._extract_items(text)
        if items:
            parsed_data["items"] = items
            confidence_score += 0.1
        
        parsed_data["confidence"] = min(confidence_score, 1.0)
        
        return parsed_data
    
    async def _extract_amount_and_currency(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract amount and currency from text.
        
        Args:
            text: Receipt text
            
        Returns:
            Optional[Dict[str, Any]]: Amount and currency or None
        """
        # Currency symbols and codes
        currency_patterns = {
            r'\$': 'USD',
            r'€': 'EUR',
            r'£': 'GBP',
            r'¥': 'JPY',
            r'₹': 'INR',
            r'R\$': 'BRL',
            r'C\$': 'CAD',
            r'A\$': 'AUD',
            r'S\$': 'SGD',
            r'NZ\$': 'NZD',
            r'MX\$': 'MXN',
            r'HK\$': 'HKD',
            r'kr': 'SEK',
            r'Kč': 'CZK',
            r'Ft': 'HUF',
            r'₪': 'ILS',
            r'₩': 'KRW',
            r'₱': 'PHP',
            r'د.إ': 'AED',
            r'₪': 'ILS',
            r'zł': 'PLN',
            r'lei': 'RON',
            r'лв': 'BGN'
        }
        
        # Amount patterns (various formats)
        amount_patterns = [
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # 1,234.56
            r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',  # 1.234,56 (European)
            r'(\d+(?:\.\d{2})?)',  # 1234.56
            r'(\d+(?:,\d{2})?)',  # 1234,56
        ]
        
        # Look for total amounts (common keywords)
        total_keywords = [
            'total', 'amount', 'sum', 'grand total', 'final total',
            'subtotal', 'net total', 'gross total', 'balance',
            'amount due', 'total amount', 'final amount'
        ]
        
        text_lower = text.lower()
        
        for keyword in total_keywords:
            # Find text around total keywords
            keyword_index = text_lower.find(keyword)
            if keyword_index != -1:
                # Extract text around the keyword
                start = max(0, keyword_index - 50)
                end = min(len(text), keyword_index + 50)
                context = text[start:end]
                
                # Look for currency symbol in context
                currency = None
                for pattern, curr_code in currency_patterns.items():
                    if re.search(pattern, context):
                        currency = curr_code
                        break
                
                # Look for amount in context
                for pattern in amount_patterns:
                    matches = re.findall(pattern, context)
                    if matches:
                        # Take the largest amount (likely the total)
                        amounts = []
                        for match in matches:
                            try:
                                # Clean amount string
                                clean_amount = match.replace(',', '')
                                amount = Decimal(clean_amount)
                                amounts.append(amount)
                            except (InvalidOperation, ValueError):
                                continue
                        
                        if amounts:
                            max_amount = max(amounts)
                            return {
                                "amount": max_amount,
                                "currency": currency or "USD"
                            }
        
        # Fallback: look for any amount with currency in the entire text
        for pattern, curr_code in currency_patterns.items():
            matches = re.finditer(f'{pattern}\\s*({amount_patterns[0]})', text, re.IGNORECASE)
            for match in matches:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount = Decimal(amount_str)
                    return {
                        "amount": amount,
                        "currency": curr_code
                    }
                except (InvalidOperation, ValueError):
                    continue
        
        return None
    
    async def _extract_date(self, text: str) -> Optional[date]:
        """
        Extract date from receipt text.
        
        Args:
            text: Receipt text
            
        Returns:
            Optional[date]: Extracted date or None
        """
        # Date patterns
        date_patterns = [
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',  # MM/DD/YYYY or DD/MM/YYYY
            r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',  # YYYY/MM/DD
            r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{2,4})',  # DD MMM YYYY
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{2,4})',  # MMM DD, YYYY
        ]
        
        month_names = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        for pattern in date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    groups = match.groups()
                    
                    if len(groups) == 3:
                        if pattern == date_patterns[0]:  # MM/DD/YYYY or DD/MM/YYYY
                            # Try both formats
                            try:
                                # MM/DD/YYYY
                                month, day, year = map(int, groups)
                                if 1 <= month <= 12 and 1 <= day <= 31:
                                    if year < 100:
                                        year += 2000
                                    return date(year, month, day)
                            except ValueError:
                                pass
                            
                            try:
                                # DD/MM/YYYY
                                day, month, year = map(int, groups)
                                if 1 <= month <= 12 and 1 <= day <= 31:
                                    if year < 100:
                                        year += 2000
                                    return date(year, month, day)
                            except ValueError:
                                pass
                        
                        elif pattern == date_patterns[1]:  # YYYY/MM/DD
                            year, month, day = map(int, groups)
                            if 1 <= month <= 12 and 1 <= day <= 31:
                                return date(year, month, day)
                        
                        elif pattern == date_patterns[2]:  # DD MMM YYYY
                            day, month_str, year = groups
                            month = month_names.get(month_str.lower())
                            if month:
                                day, year = int(day), int(year)
                                if year < 100:
                                    year += 2000
                                return date(year, month, day)
                        
                        elif pattern == date_patterns[3]:  # MMM DD, YYYY
                            month_str, day, year = groups
                            month = month_names.get(month_str.lower())
                            if month:
                                day, year = int(day), int(year)
                                if year < 100:
                                    year += 2000
                                return date(year, month, day)
                
                except (ValueError, TypeError):
                    continue
        
        return None
    
    async def _extract_merchant_name(self, text: str) -> Optional[str]:
        """
        Extract merchant name from receipt text.
        
        Args:
            text: Receipt text
            
        Returns:
            Optional[str]: Merchant name or None
        """
        lines = text.split('\n')
        
        # Look for merchant name in first few lines
        for i, line in enumerate(lines[:5]):
            line = line.strip()
            if len(line) > 3 and len(line) < 50:
                # Skip lines that look like addresses or phone numbers
                if not re.search(r'\d{3,}', line) and not re.search(r'@', line):
                    return line
        
        return None
    
    async def _extract_tax_amount(self, text: str) -> Optional[Decimal]:
        """
        Extract tax amount from receipt text.
        
        Args:
            text: Receipt text
            
        Returns:
            Optional[Decimal]: Tax amount or None
        """
        tax_keywords = ['tax', 'vat', 'gst', 'hst', 'pst', 'qst']
        
        for keyword in tax_keywords:
            pattern = f'{keyword}\\s*[:\\s]*([\\d,]+\\.[\\d]{{2}})'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    tax_str = match.group(1).replace(',', '')
                    return Decimal(tax_str)
                except (InvalidOperation, ValueError):
                    continue
        
        return None
    
    async def _extract_items(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract individual items from receipt text.
        
        Args:
            text: Receipt text
            
        Returns:
            List[Dict[str, Any]]: List of items with descriptions and amounts
        """
        items = []
        lines = text.split('\n')
        
        # Simple item extraction (can be improved with more sophisticated parsing)
        for line in lines:
            line = line.strip()
            if len(line) > 10 and len(line) < 100:
                # Look for lines that might be items (contain text and numbers)
                if re.search(r'[a-zA-Z]', line) and re.search(r'\d', line):
                    # Try to extract amount from the line
                    amount_match = re.search(r'([\d,]+\.\d{2})', line)
                    if amount_match:
                        try:
                            amount_str = amount_match.group(1).replace(',', '')
                            amount = Decimal(amount_str)
                            description = line.replace(amount_match.group(1), '').strip()
                            
                            if description:
                                items.append({
                                    "description": description,
                                    "amount": amount
                                })
                        except (InvalidOperation, ValueError):
                            continue
        
        return items
    
    async def validate_currency(self, currency: str) -> bool:
        """
        Validate if detected currency is supported.
        
        Args:
            currency: Currency code to validate
            
        Returns:
            bool: True if supported, False otherwise
        """
        return currency.upper() in self.supported_currencies


# Global OCR service instance
ocr_service = OCRService()

