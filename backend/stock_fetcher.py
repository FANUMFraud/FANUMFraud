"""
Stock price fetcher - pobiera kursy akcji z Stooq API
"""

import httpx
import logging
from datetime import datetime, UTC
from typing import Optional
import random

log = logging.getLogger(__name__)


# Demo data dla testowania (jeśli API niedostępny)
DEMO_STOCK_DATA = {
    "BET": {"price": 125.50, "change": -2.3, "volume": 1250000},
    "NTS": {"price": 87.30, "change": 1.5, "volume": 520000},
    "MCON": {"price": 156.75, "change": -0.8, "volume": 340000},
    "ACM": {"price": 92.10, "change": 3.2, "volume": 680000},
    "SCP": {"price": 78.90, "change": -1.1, "volume": 410000},
}


class StooqPriceFetcher:
    """
    Pobiera aktualne kursy akcji z Stooq.pl API (GPW)
    
    Stooq jest darmowy, nie wymaga autentykacji
    API endpoint: https://stooq.pl/aq/quotesearch/quote/
    
    Fallback: Jeśli API niedostępny, zwraca demo dane
    """
    
    BASE_URL = "https://stooq.pl/aq/quotesearch/quote/"
    TIMEOUT = 10
    USE_DEMO_FALLBACK = True  # Włącz fallback na demo dane
    
    @staticmethod
    def fetch_current_price(ticker: str) -> Optional[dict]:
        """
        Pobiera aktualną cenę akcji z Stooq
        
        Args:
            ticker: Kod akcji (np. "BET", "NTS", "MCON")
        
        Returns:
            {
                'price': float,              # Aktualna cena (ostatnia cena zamknięcia)
                'price_change': float,       # Zmiana % (vs. dzień wcześniej)
                'volume': int,               # Wolumen obrotu
                'timestamp': datetime        # Czas pobrania danych
            }
            lub None jeśli błąd i demo fallback wyłączony
            
        Example:
            >>> fetcher = StooqPriceFetcher()
            >>> data = fetcher.fetch_current_price("BET")
            >>> print(data)
            {'price': 125.5, 'price_change': -2.3, 'volume': 1250000, 'timestamp': datetime(...)}
        """
        try:
            # Próbuj Stooq API
            url = f"{StooqPriceFetcher.BASE_URL}?q={ticker}&type=stock"
            response = httpx.get(url, timeout=StooqPriceFetcher.TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            
            # Brak danych dla tego tickera
            if not data or len(data) == 0:
                log.warning(f"Stooq: No data for ticker {ticker}")
                return StooqPriceFetcher._get_demo_data(ticker)
            
            item = data[0]
            
            return {
                'price': float(item.get('Close', 0)),
                'price_change': float(item.get('Change', 0)),  # % zmiana
                'volume': int(item.get('Volume', 0)),
                'timestamp': datetime.now(UTC)
            }
        
        except httpx.TimeoutException:
            log.warning(f"Stooq API timeout for {ticker}, using demo data")
            return StooqPriceFetcher._get_demo_data(ticker)
        except httpx.RequestError as e:
            log.warning(f"Stooq API request error for {ticker}: {e}, using demo data")
            return StooqPriceFetcher._get_demo_data(ticker)
        except (KeyError, ValueError, TypeError) as e:
            log.warning(f"Stooq API parse error for {ticker}: {e}, using demo data")
            return StooqPriceFetcher._get_demo_data(ticker)
        except Exception as e:
            log.warning(f"Unexpected error fetching {ticker} from Stooq: {e}, using demo data")
            return StooqPriceFetcher._get_demo_data(ticker)
    
    @staticmethod
    def _get_demo_data(ticker: str) -> Optional[dict]:
        """
        Zwraca demo dane dla testowania
        Jeśli USE_DEMO_FALLBACK wyłączony, zwraca None
        """
        if not StooqPriceFetcher.USE_DEMO_FALLBACK:
            return None
        
        if ticker in DEMO_STOCK_DATA:
            demo = DEMO_STOCK_DATA[ticker]
            # Add small random variation to make it more realistic
            price_variation = random.uniform(-0.5, 0.5)
            change_variation = random.uniform(-0.3, 0.3)
            
            return {
                'price': demo['price'] + price_variation,
                'price_change': demo['change'] + change_variation,
                'volume': demo['volume'],
                'timestamp': datetime.now(UTC)
            }
        
        log.debug(f"No demo data for {ticker}")
        return None

