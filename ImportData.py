import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime

# Define the ticker symbol for the stock
ticker_symbol = "AAPL"

# Create a ticker object
ticker = yf.Ticker(ticker_symbol)

# Get historical closing prices for the past year to calculate volatility
hist = ticker.history(period="1y")

# Calculate daily returns
daily_returns = hist['Close'].pct_change()

# Calculate annualized volatility (standard deviation of daily returns)
annualized_volatility = np.std(daily_returns) * np.sqrt(252)
print(f"Annualized Volatility: {annualized_volatility:.2%}")

# Get current stock price from the latest available data
current_price = hist['Close'][-1]
print(f"Current Stock Price: ${current_price:.2f}")

# Fetch options data
options_dates = ticker.options  # Get available expiration dates
options_data = ticker.option_chain(options_dates[0])  # Options data for the first available expiration date

# Display options data
print("Available Expiration Dates:", options_dates)
print("Options Data for First Expiration Date:")
print(options_data.calls[['strike', 'lastPrice', 'impliedVolatility']].head())  # Display some call options data
print(options_data.puts[['strike', 'lastPrice', 'impliedVolatility']].head())  # Display some put options data

# Fetch risk-free rate (using U.S. Treasury as a proxy, here assumed fixed or fetched from an external source)
risk_free_rate = 0.02  # Example: 2% annual rate
print(f"Risk-Free Rate: {risk_free_rate:.2%}")