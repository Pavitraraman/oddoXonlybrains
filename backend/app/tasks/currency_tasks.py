"""
Currency and exchange rate background tasks.
"""

import logging
from datetime import date, timedelta
from app.celery_app import celery_app
from app.services.currency_service import currency_service
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name='app.tasks.currency_tasks.update_exchange_rates')
def update_exchange_rates(base_currency: str = "USD", days_back: int = 7):
    """
    Update exchange rates from external API.
    
    Args:
        base_currency: Base currency for rates
        days_back: Number of days to fetch historical rates
    """
    try:
        logger.info(f"Starting exchange rate update for {base_currency}")
        
        async def update_rates():
            async with AsyncSessionLocal() as db:
                try:
                    # Get date range
                    end_date = date.today()
                    start_date = end_date - timedelta(days=days_back)
                    
                    # Update historical rates
                    updated_count = await currency_service.update_historical_rates(
                        db=db,
                        start_date=start_date,
                        end_date=end_date,
                        base_currency=base_currency
                    )
                    
                    logger.info(f"Updated {updated_count} exchange rate records")
                    return updated_count
                    
                except Exception as e:
                    logger.error(f"Error updating exchange rates: {e}")
                    raise
        
        # Run async function
        import asyncio
        updated_count = asyncio.run(update_rates())
        
        logger.info(f"Exchange rate update completed. {updated_count} records updated.")
        return {
            'status': 'success',
            'updated_count': updated_count,
            'base_currency': base_currency,
            'date_range': f"{start_date} to {end_date}"
        }
        
    except Exception as e:
        logger.error(f"Exchange rate update failed: {e}")
        return {
            'status': 'error',
            'message': str(e),
            'base_currency': base_currency
        }


@celery_app.task(name='app.tasks.currency_tasks.validate_currency_rates')
def validate_currency_rates():
    """
    Validate and clean up currency rate data.
    """
    try:
        logger.info("Starting currency rate validation")
        
        async def validate_rates():
            async with AsyncSessionLocal() as db:
                try:
                    from sqlalchemy import select, delete
                    from app.models import CurrencyRate
                    
                    # Find and remove invalid rates
                    invalid_rates = await db.execute(
                        select(CurrencyRate).where(
                            (CurrencyRate.rate <= 0) |
                            (CurrencyRate.rate.is_(None))
                        )
                    )
                    
                    invalid_count = len(invalid_rates.scalars().all())
                    
                    if invalid_count > 0:
                        await db.execute(
                            delete(CurrencyRate).where(
                                (CurrencyRate.rate <= 0) |
                                (CurrencyRate.rate.is_(None))
                            )
                        )
                        await db.commit()
                    
                    logger.info(f"Validated currency rates. Removed {invalid_count} invalid rates.")
                    return invalid_count
                    
                except Exception as e:
                    logger.error(f"Error validating currency rates: {e}")
                    await db.rollback()
                    raise
        
        # Run async function
        import asyncio
        invalid_count = asyncio.run(validate_rates())
        
        logger.info(f"Currency rate validation completed. {invalid_count} invalid rates removed.")
        return {
            'status': 'success',
            'invalid_rates_removed': invalid_count
        }
        
    except Exception as e:
        logger.error(f"Currency rate validation failed: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }

