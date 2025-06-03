import requests
import logging
from typing import Dict
from datetime import date

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CurrencyAPI:
    def __init__(self):
        """Initialize with Frankfurter API (no API key required)"""
        self.api_base_url = "https://api.frankfurter.app"

    def get_currency_conversion(self, amount: float, from_currency: str, to_currency: str) -> Dict:
        """
        Fetch currency conversion for a given amount from one currency to another.

        Args:
            amount (float): Amount to convert
            from_currency (str): Source currency code (e.g., 'USD')
            to_currency (str): Target currency code (e.g., 'EUR')

        Returns:
            dict: Formatted response with conversion result
        """
        logger.info(f"Converting {amount} {from_currency} to {to_currency}")
        url = f"{self.api_base_url}/latest?from={from_currency}&to={to_currency}"

        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            if to_currency not in data["rates"]:
                raise ValueError(f"Currency {to_currency} not supported")

            rate = data["rates"][to_currency]
            converted_amount = amount * rate
            return {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "amount": amount,
                "converted_amount": round(converted_amount, 2),
                "rate": round(rate, 4)
            }

        except requests.exceptions.HTTPError as e:
            logger.error(f"Currency API HTTP Error: {str(e)}")
            return self._mock_conversion(amount, from_currency, to_currency)
        except requests.exceptions.RequestException as e:
            logger.error(f"Currency API Request Error: {str(e)}")
            return self._mock_conversion(amount, from_currency, to_currency)
        except ValueError as e:
            logger.error(f"Currency API Value Error: {str(e)}")
            return {
                "error": str(e),
                "from_currency": from_currency,
                "to_currency": to_currency,
                "amount": amount,
                "converted_amount": "Unable to fetch conversion rate."
            }

    def _mock_conversion(self, amount: float, from_currency: str, to_currency: str) -> Dict:
        """Return mock conversion data for testing or fallback."""
        mock_rates = {
            "USD": {"EUR": 0.925, "GBP": 0.785, "JPY": 145.20},
            "EUR": {"USD": 1.082, "GBP": 0.849, "JPY": 157.03},
            "GBP": {"USD": 1.274, "EUR": 1.178, "JPY": 184.89},
            "JPY": {"USD": 0.0069, "EUR": 0.0064, "GBP": 0.0054}
        }
        if from_currency in mock_rates and to_currency in mock_rates[from_currency]:
            rate = mock_rates[from_currency][to_currency]
            converted_amount = amount * rate
            return {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "amount": amount,
                "converted_amount": round(converted_amount, 2),
                "rate": round(rate, 4)
            }
        return {
            "error": "Unsupported currency pair",
            "from_currency": from_currency,
            "to_currency": to_currency,
            "amount": amount,
            "converted_amount": "Unable to fetch conversion rate."
        }