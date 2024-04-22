from scipy.stats import norm
import numpy as np

# Define the Black-Scholes function for call and put
def black_scholes(S, K, T, r, sigma):
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    call_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    put_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return call_price, put_price

# Set parameters
S = current_price  # Current stock price from your data
K = 150.0  # Example strike price
T = (datetime(2024, 4, 26) - datetime.now()).days / 365.25  # Time to expiration calculated
r = 0.02  # Risk-free rate
sigma = annualized_volatility  # Annualized volatility from your data

# Calculate option prices
call_price, put_price = black_scholes(S, K, T, r, sigma)
print(f"Black-Scholes Call Option Price: ${call_price:.2f}")
print(f"Black-Scholes Put Option Price: ${put_price:.2f}")
