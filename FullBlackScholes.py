import yfinance as yf
from scipy.stats import norm
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import requests
import pandas as pd
import xlsxwriter
import logging
from arch import arch_model

# Setup logging
logging.basicConfig(level=logging.INFO, filename='option_pricing.log', filemode='w', format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_historical_data(ticker_symbol, period='1y'):
    ticker = yf.Ticker(ticker_symbol)
    return ticker.history(period=period)

def get_garch_volatility(returns):
    """Estimate volatility using GARCH(1,1) model with scaled returns."""
    scale = 100  # Scaling factor to improve optimizer performance
    scaled_returns = returns * scale
    model = arch_model(scaled_returns, mean='Zero', vol='Garch', p=1, q=1)
    try:
        model_fit = model.fit(disp='off')
        forecast = model_fit.forecast(horizon=1)
        forecasted_variance = forecast.variance.values[-1, -1]
        annualized_volatility = np.sqrt(forecasted_variance) / scale * np.sqrt(252)  # Annualize the volatility
        logging.info(f"GARCH Estimated Annualized Volatility: {annualized_volatility}%")
        return annualized_volatility
    except Exception as e:
        logging.error("Failed to fit GARCH model: " + str(e))
        return None

def calculate_annualized_volatility(hist_data):
    daily_returns = hist_data['Close'].pct_change().dropna()
    if daily_returns.empty or daily_returns.isnull().all():
        logging.warning("Daily returns are empty or NaN.")
        return np.nan

    if len(daily_returns) > 30:  # Ensure there's enough data to fit a model
        garch_volatility = get_garch_volatility(daily_returns)
        if garch_volatility is not None:
            return garch_volatility
        else:
            logging.warning("GARCH model fitting failed, falling back to standard deviation.")
    
    fallback_volatility = np.std(daily_returns) * np.sqrt(252)  # Fallback method
    logging.info(f"Standard Deviation Based Annualized Volatility: {fallback_volatility}%")
    return fallback_volatility

def fetch_options_data(ticker, expiration_date=None):
    if expiration_date is None:
        expiration_date = ticker.options[0]
    return ticker.option_chain(expiration_date)

def get_current_stock_price(ticker):
    stock_data = ticker.history(period="1d")['Close']
    if stock_data.empty:
        return np.nan
    return stock_data.iloc[-1]

def get_implied_volatility(ticker, ticker_symbol, target_date=None):
    if target_date is None:
        target_date = ticker.options[0]
    options_data = ticker.option_chain(target_date)
    atm_calls = options_data.calls[options_data.calls['strike'] == round(ticker.info['previousClose'])]
    atm_puts = options_data.puts[options_data.puts['strike'] == round(ticker.info['previousClose'])]
    if atm_calls.empty or atm_puts.empty or np.isnan(atm_calls['impliedVolatility'].mean()):
        logging.warning("Implied volatility unavailable, defaulting to historical volatility.")
        return calculate_annualized_volatility(fetch_historical_data(ticker_symbol))
    iv = (atm_calls['impliedVolatility'].mean() + atm_puts['impliedVolatility'].mean()) / 2
    logging.info(f"Implied Volatility: {iv * 100}%")
    return iv

def safe_divide(num, denom):
    """ Helper function to safely divide two numbers """
    if denom == 0:
        return 0
    return num / denom

def black_scholes(S, K, T, r, sigma, option_type='call'):
    if np.isnan(S) or np.isnan(K) or np.isnan(T) or np.isnan(r) or np.isnan(sigma) or sigma == 0:
        return 0  # Return 0 for option price if any input is not valid or sigma is zero
    d1 = safe_divide(np.log(S / K) + (r + 0.5 * sigma**2) * T, sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == 'call':
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def calculate_greeks(S, Ks, T, r, sigma, option_type='call'):
    results = {'Delta': [], 'Gamma': [], 'Theta': [], 'Vega': [], 'Rho': []}
    for K in Ks:
        if np.isnan(S) or np.isnan(sigma) or np.isnan(T) or np.isnan(r):
            for key in results:
                results[key].append(np.nan)
            continue
        d1 = safe_divide(np.log(S / K) + (r + 0.5 * sigma**2) * T, sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        results['Delta'].append(norm.cdf(d1) if option_type == 'call' else norm.cdf(d1) - 1)
        results['Gamma'].append(safe_divide(norm.pdf(d1), S * sigma * np.sqrt(T)))
        results['Theta'].append(-safe_divide(S * norm.pdf(d1) * sigma, 2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2))
        results['Vega'].append(safe_divide(S * norm.pdf(d1) * np.sqrt(T), 100))
        results['Rho'].append(safe_divide(K * T * np.exp(-r * T) * (norm.cdf(d2) if option_type == 'call' else -norm.cdf(-d2)), 100))
    return results

def plot_option_prices(strikes, call_prices, put_prices):
    plt.figure(figsize=(10, 5))
    plt.plot(strikes, call_prices, marker='o', label='Call Prices')
    plt.plot(strikes, put_prices, marker='x', label='Put Prices')
    plt.title('Option Prices by Strike Price')
    plt.xlabel('Strike Price')
    plt.ylabel('Option Price')
    plt.legend()
    plt.grid(True)
    plt.show()

def generate_report(strikes, call_prices, put_prices, Greeks, filename="enhanced_option_report.xlsx"):
    workbook = xlsxwriter.Workbook(filename, {'nan_inf_to_errors': True})
    worksheet = workbook.add_worksheet("Options Data")
    bold = workbook.add_format({'bold': True})
    money_format = workbook.add_format({'num_format': '$#,##0.00'})
    percent_format = workbook.add_format({'num_format': '0.00%'})

    headers = ['Strike Price', 'Call Prices', 'Put Prices'] + list(Greeks.keys())
    for i, header in enumerate(headers):
        worksheet.write(0, i, header, bold)

    for i, strike in enumerate(strikes):
        worksheet.write(i + 1, 0, strike, money_format)
        worksheet.write(i + 1, 1, call_prices[i] if not np.isnan(call_prices[i]) else 0, money_format)
        worksheet.write(i + 1, 2, put_prices[i] if not np.isnan(put_prices[i]) else 0, money_format)
        for j, key in enumerate(Greeks.keys()):
            value = Greeks[key][i] if not np.isnan(Greeks[key][i]) else 0
            worksheet.write(i + 1, j + 3, value, percent_format)

    chart = workbook.add_chart({'type': 'line'})
    chart.add_series({
        'name': '=\'Options Data\'!$B$1',
        'categories': '=\'Options Data\'!$A$2:$A$6',
        'values': '=\'Options Data\'!$B$2:$B$6',
    })
    chart.add_series({
        'name': '=\'Options Data\'!$C$1',
        'categories': '=\'Options Data\'!$A$2:$A$6',
        'values': '=\'Options Data\'!$C$2:$C$6',
    })
    chart.set_title({'name': 'Call and Put Prices'})
    chart.set_x_axis({'name': 'Strike Price'})
    chart.set_y_axis({'name': 'Option Price'})
    worksheet.insert_chart('E2', chart)

    workbook.close()
    print(f"Report generated and saved as {filename}")

def fetch_risk_free_rate(api_key):
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DTB3&api_key={api_key}&file_type=json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        latest_rate = float(data['observations'][-1]['value'])
        return latest_rate / 100
    except Exception as e:
        print(f"Error fetching the rate from FRED: {e}")
        return 0.02  # Fallback to a default rate in case of error

def main():
    api_key = 'Enter your FRED API Key' # Enter your FRED API Key
    ticker_symbol = "NVDA"
    ticker = yf.Ticker(ticker_symbol)

    current_price = get_current_stock_price(ticker)
    implied_volatility = get_implied_volatility(ticker, ticker_symbol)
    annualized_volatility = calculate_annualized_volatility(fetch_historical_data(ticker_symbol))

    print(f"Annualized Volatility: {annualized_volatility:.2%}")
    print(f"Current Stock Price: ${current_price:.2f}")
    print(f"Implied Volatility: {implied_volatility * 100:.2f}%")  # Ensure correct percentage display

    risk_free_rate = fetch_risk_free_rate(api_key)
    print(f"Risk-Free Rate: {risk_free_rate:.2%}")

    T = (datetime(2024, 4, 26) - datetime.now()).days / 365.25
    r = risk_free_rate
    sigma = implied_volatility if not np.isnan(implied_volatility) else annualized_volatility  # Use GARCH or fallback if NaN

    strikes = np.linspace(current_price * 0.8, current_price * 1.2, 5)
    call_prices = [black_scholes(current_price, k, T, r, sigma, 'call') for k in strikes]
    put_prices = [black_scholes(current_price, k, T, r, sigma, 'put') for k in strikes]
    Greeks = calculate_greeks(current_price, strikes, T, r, sigma, 'call')

    print(f"Black-Scholes Call Option Prices: {call_prices}")
    print(f"Black-Scholes Put Option Prices: {put_prices}")

    plot_option_prices(strikes, call_prices, put_prices)
    generate_report(strikes, call_prices, put_prices, Greeks)

if __name__ == '__main__':
    main()
