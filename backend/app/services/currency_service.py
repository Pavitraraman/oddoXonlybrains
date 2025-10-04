"""
Currency conversion and exchange rate management service.
Handles fetching, caching, and converting currencies for the Expense Management System.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, List

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc

from config import settings
from app.models import CurrencyRate
from app.schemas import CurrencyRateCreate

logger = logging.getLogger(__name__)


class CurrencyService:
    """Service for managing currency conversion and exchange rates."""
    
    def __init__(self):
        self.api_key = settings.exchange_rate_api_key
        self.base_url = settings.exchange_rate_base_url
        self.cache_duration = timedelta(hours=6)  # Cache rates for 6 hours
    
    async def get_exchange_rate(
        self, 
        from_currency: str, 
        to_currency: str, 
        rate_date: Optional[date] = None,
        db: AsyncSession = None
    ) -> Optional[Decimal]:
        """
        Get exchange rate between two currencies for a specific date.
        
        Args:
            from_currency: Source currency code (e.g., 'USD')
            to_currency: Target currency code (e.g., 'EUR')
            rate_date: Date for the exchange rate (defaults to today)
            db: Database session
            
        Returns:
            Optional[Decimal]: Exchange rate or None if not found
        """
        if rate_date is None:
            rate_date = date.today()
        
        if from_currency == to_currency:
            return Decimal('1.0')
        
        # Try to get rate from database first
        if db:
            rate = await self._get_rate_from_db(db, from_currency, to_currency, rate_date)
            if rate:
                return rate
        
        # If not found in DB, try to fetch from API
        if db:
            await self._fetch_and_store_rates(db, rate_date)
            # Try again after fetching
            rate = await self._get_rate_from_db(db, from_currency, to_currency, rate_date)
            if rate:
                return rate
        
        # Fallback: try reverse rate
        if db:
            reverse_rate = await self._get_rate_from_db(db, to_currency, from_currency, rate_date)
            if reverse_rate:
                return Decimal('1.0') / reverse_rate
        
        logger.warning(f"No exchange rate found for {from_currency} to {to_currency} on {rate_date}")
        return None
    
    async def convert_currency(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        rate_date: Optional[date] = None,
        db: AsyncSession = None
    ) -> Optional[Decimal]:
        """
        Convert amount from one currency to another.
        
        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code
            rate_date: Date for conversion (defaults to today)
            db: Database session
            
        Returns:
            Optional[Decimal]: Converted amount or None if conversion failed
        """
        if from_currency == to_currency:
            return amount
        
        rate = await self.get_exchange_rate(from_currency, to_currency, rate_date, db)
        if rate is None:
            return None
        
        converted_amount = amount * rate
        return converted_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    async def get_latest_rates(
        self,
        base_currency: str = "USD",
        db: AsyncSession = None
    ) -> Dict[str, Decimal]:
        """
        Get latest exchange rates for all supported currencies.
        
        Args:
            base_currency: Base currency for rates
            db: Database session
            
        Returns:
            Dict[str, Decimal]: Dictionary of currency codes to rates
        """
        if db is None:
            return {}
        
        # Get rates from database
        result = await db.execute(
            select(CurrencyRate)
            .where(
                and_(
                    CurrencyRate.from_currency == base_currency,
                    CurrencyRate.rate_date == date.today()
                )
            )
        )
        rates = result.scalars().all()
        
        rate_dict = {}
        for rate in rates:
            rate_dict[rate.to_currency] = rate.rate
        
        # If we don't have today's rates, try to fetch them
        if not rate_dict:
            await self._fetch_and_store_rates(db, date.today(), base_currency)
            
            # Try again after fetching
            result = await db.execute(
                select(CurrencyRate)
                .where(
                    and_(
                        CurrencyRate.from_currency == base_currency,
                        CurrencyRate.rate_date == date.today()
                    )
                )
            )
            rates = result.scalars().all()
            
            for rate in rates:
                rate_dict[rate.to_currency] = rate.rate
        
        return rate_dict
    
    async def _get_rate_from_db(
        self,
        db: AsyncSession,
        from_currency: str,
        to_currency: str,
        rate_date: date
    ) -> Optional[Decimal]:
        """Get exchange rate from database."""
        # Try exact date first
        result = await db.execute(
            select(CurrencyRate.rate)
            .where(
                and_(
                    CurrencyRate.from_currency == from_currency,
                    CurrencyRate.to_currency == to_currency,
                    CurrencyRate.rate_date == rate_date
                )
            )
        )
        rate = result.scalar_one_or_none()
        
        if rate:
            return rate
        
        # Try most recent date before the requested date
        result = await db.execute(
            select(CurrencyRate.rate)
            .where(
                and_(
                    CurrencyRate.from_currency == from_currency,
                    CurrencyRate.to_currency == to_currency,
                    CurrencyRate.rate_date <= rate_date
                )
            )
            .order_by(desc(CurrencyRate.rate_date))
            .limit(1)
        )
        rate = result.scalar_one_or_none()
        
        return rate
    
    async def _fetch_and_store_rates(
        self,
        db: AsyncSession,
        rate_date: date,
        base_currency: str = "USD"
    ) -> bool:
        """
        Fetch exchange rates from external API and store in database.
        
        Args:
            db: Database session
            rate_date: Date for the rates
            base_currency: Base currency for rates
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if we already have rates for this date
            result = await db.execute(
                select(CurrencyRate)
                .where(
                    and_(
                        CurrencyRate.from_currency == base_currency,
                        CurrencyRate.rate_date == rate_date
                    )
                )
                .limit(1)
            )
            existing_rate = result.scalar_one_or_none()
            
            if existing_rate:
                logger.info(f"Exchange rates for {rate_date} already exist")
                return True
            
            # Fetch rates from API
            rates_data = await self._fetch_rates_from_api(base_currency)
            if not rates_data:
                return False
            
            # Store rates in database
            stored_count = 0
            for currency, rate in rates_data.items():
                if currency == base_currency:
                    continue
                
                currency_rate = CurrencyRate(
                    from_currency=base_currency,
                    to_currency=currency,
                    rate=Decimal(str(rate)),
                    rate_date=rate_date
                )
                db.add(currency_rate)
                stored_count += 1
            
            # Also store reverse rates
            for currency, rate in rates_data.items():
                if currency == base_currency:
                    continue
                
                currency_rate = CurrencyRate(
                    from_currency=currency,
                    to_currency=base_currency,
                    rate=Decimal('1.0') / Decimal(str(rate)),
                    rate_date=rate_date
                )
                db.add(currency_rate)
                stored_count += 1
            
            await db.commit()
            logger.info(f"Stored {stored_count} exchange rates for {rate_date}")
            return True
            
        except Exception as e:
            logger.error(f"Error fetching and storing exchange rates: {e}")
            await db.rollback()
            return False
    
    async def _fetch_rates_from_api(self, base_currency: str = "USD") -> Optional[Dict[str, float]]:
        """
        Fetch exchange rates from external API.
        
        Args:
            base_currency: Base currency for rates
            
        Returns:
            Optional[Dict[str, float]]: Dictionary of currency rates or None if failed
        """
        try:
            url = f"{self.base_url}/{base_currency}"
            headers = {}
            
            if self.api_key:
                headers["apikey"] = self.api_key
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                return data.get("rates", {})
                
        except httpx.RequestError as e:
            logger.error(f"Request error fetching exchange rates: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching exchange rates: {e}")
            return None
    
    async def update_historical_rates(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
        base_currency: str = "USD"
    ) -> int:
        """
        Update historical exchange rates for a date range.
        
        Args:
            db: Database session
            start_date: Start date for historical rates
            end_date: End date for historical rates
            base_currency: Base currency for rates
            
        Returns:
            int: Number of rates updated
        """
        updated_count = 0
        current_date = start_date
        
        while current_date <= end_date:
            success = await self._fetch_and_store_rates(db, current_date, base_currency)
            if success:
                updated_count += 1
            
            current_date += timedelta(days=1)
            
            # Add small delay to avoid rate limiting
            await asyncio.sleep(0.1)
        
        logger.info(f"Updated historical rates for {updated_count} days")
        return updated_count
    
    async def get_supported_currencies(self) -> List[str]:
        """
        Get list of supported currencies.
        
        Returns:
            List[str]: List of supported currency codes
        """
        return [
            "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "INR", "BRL",
            "KRW", "SGD", "NZD", "MXN", "HKD", "NOK", "SEK", "DKK", "PLN", "CZK",
            "HUF", "ILS", "CLP", "PHP", "AED", "COP", "SAR", "MYR", "RON", "BGN"
        ]
    
    async def validate_currency(self, currency_code: str) -> bool:
        """
        Validate if a currency code is supported.
        
        Args:
            currency_code: Currency code to validate
            
        Returns:
            bool: True if supported, False otherwise
        """
        supported_currencies = await self.get_supported_currencies()
        return currency_code.upper() in supported_currencies


# Global currency service instance
currency_service = CurrencyService()

