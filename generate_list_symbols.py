"""
Read the list of perpetual futures from Binance and save it to a file
"""

import requests
import pickle

# Correct URL for Binance futures API
url = 'https://fapi.binance.com/fapi/v1/exchangeInfo'

try:
    response = requests.get(url)
    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()
        # Extract symbols that end with 'USDT'
        list_symbols = [symbol['symbol'] for symbol in data['symbols'] if symbol['symbol'].endswith('USDT')]
        # Write symbols to a file
        with open('list_symbols.txt', 'w') as f:
            for symbol in list_symbols:
                f.write(symbol + '\n')
    else:
        print("Failed to retrieve data: Status code", response.status_code)
except requests.exceptions.RequestException as e:
    # Handle exceptions that may occur during the request
    print("An error occurred: ", e)

# get rid of some symbols from the exclusion list
list_exclusion = ['BTCUSDT', 'ETHUSDT']
for symbol in list_exclusion:
    list_symbols.remove(symbol)

# sort the list alphabetically
list_symbols = sorted(list_symbols)

# save the list locally to a pickle file
with open('list_symbols.pkl', 'wb') as f:
    pickle.dump(list_symbols, f)

