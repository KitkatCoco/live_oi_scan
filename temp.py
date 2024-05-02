import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import time

# Helper function to fetch data
def fetch_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to fetch data:", response.status_code, response.text)
        return None

# Set parameters
symbol = 'FRONTUSDT'
interval = '5m'
limit = 500  # Covering 500 intervals

# Calculate start time
current_time = int(time.time() * 1000)  # current time in milliseconds
start_time = current_time - (5 * 60 * 1000 * limit)  # Go back 500 x 5 minutes

# URLs
url_price = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}&startTime={start_time}"
url_open_interest = f"https://fapi.binance.com/futures/data/openInterestHist?symbol={symbol}&period={interval}&limit={limit}&startTime={start_time}"

# Fetch data
price_data = fetch_data(url_price)
open_interest_data = fetch_data(url_open_interest)

# Prepare price data for candlestick plot
df_price = pd.DataFrame()
if price_data:
    df_price = pd.DataFrame(price_data, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close Time', 'Quote Asset Volume', 'Number of Trades', 'Taker Buy Base Asset Volume', 'Taker Buy Quote Asset Volume', 'Ignore'])
    df_price['Time'] = pd.to_datetime(df_price['Time'], unit='ms')
    df_price[['Open', 'High', 'Low', 'Close']] = df_price[['Open', 'High', 'Low', 'Close']].astype(float)

# Prepare open interest data
df_open_interest = pd.DataFrame()
if open_interest_data:
    df_open_interest = pd.DataFrame(open_interest_data)
    df_open_interest['sumOpenInterestValue'] = df_open_interest['sumOpenInterestValue'].astype(float)
    df_open_interest['timestamp'] = pd.to_datetime(df_open_interest['timestamp'], unit='ms')

# Create a 3x1 subplot
fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                    subplot_titles=("Candlestick Price Data", "Open Interest", "Funding Rate Placeholder"))

# Add Candlestick plot
fig.add_trace(
    go.Candlestick(x=df_price['Time'], open=df_price['Open'], high=df_price['High'], low=df_price['Low'], close=df_price['Close'], name='Candlestick'),
    row=1, col=1
)

# Add open interest plot
fig.add_trace(
    go.Scatter(x=df_open_interest['timestamp'], y=df_open_interest['sumOpenInterestValue'], mode='lines', name='Open Interest'),
    row=2, col=1
)

# Add a placeholder for funding rate
fig.add_trace(
    go.Scatter(x=[df_price['Time'].iloc[0], df_price['Time'].iloc[-1]], y=[0, 0], mode='lines', name='Funding Rate Placeholder'),
    row=3, col=1
)

# Update layout to make the plot wider and remove the range slider from the OHLC plot
fig.update_layout(height=900, width=1800, title_text=f"{symbol} Data Visualization Over Last {limit}x{interval} Intervals", template="plotly_dark")
fig['layout']['xaxis']['rangeslider_visible'] = False  # Disable the range slider for the Candlestick plot

fig.show()

# save the fig as html
fig.write_html('fig.html')
