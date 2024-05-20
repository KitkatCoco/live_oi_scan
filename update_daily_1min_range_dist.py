from SymbolRelativeStrength import DataParser
import time
import pandas as pd

def load_symbols():
    # Load symbols from a list_symbols.txt file
    with open('list_symbols.txt', 'r') as f:
        all_symbols = f.read().splitlines()
    return all_symbols


def calc_normalizer(symbol):

    try:
        # Get the current symbol data
        parser_cur = DataParser(symbol, '1m')
        norm_factor = parser_cur.norm_factor

    except Exception as e:
        error_msg = f"Error processing {symbol}: {str(e)}"
        print(error_msg)
        norm_factor = None

    return norm_factor



if __name__ == '__main__':
    all_symbols = load_symbols()

    # create a list to save the normalizer data for each symbol and its normalizer value
    norm_factors = []

    # Process all symbols
    for symbol in all_symbols:
        norm_factor = calc_normalizer(symbol)

        # Save the normalizer factor
        norm_factors.append({'symbol': symbol, 'norm_factor': norm_factor})

    # Save the normalizer factors to a CSV file
    df_norm_factors = pd.DataFrame(norm_factors)
    df_norm_factors.to_csv('candle_range_1min_norm_factors.csv', index=False)

