from SymbolRelativeStrength import DataParser
import time
import pandas as pd
import argparse

def load_symbols():
    # Load symbols from a list_symbols.txt file
    with open('list_symbols.txt', 'r') as f:
        all_symbols = f.read().splitlines()
    return all_symbols

def calc_normalizer(symbol, interval):
    try:
        # Get the current symbol data
        parser_cur = DataParser(symbol, interval_basic=interval)
        norm_factor = parser_cur.norm_factor
    except Exception as e:
        error_msg = f"Error processing {symbol}: {str(e)}"
        print(error_msg)
        norm_factor = None
    return norm_factor

if __name__ == '__main__':
    # Use parse arguments to receive parameters
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--interval', type=str, default='5m', help='analysis interval')
    args = parser.parse_args()
    interval = args.interval

    # Start the timer
    t0 = time.time()

    # Load all symbols
    all_symbols = load_symbols()
    all_symbols.append('BTCUSDT')
    print('Processing a total number of symbols:', len(all_symbols))

    # Create a list to save the normalizer data for each symbol and its normalizer value
    norm_factors = []

    # Process all symbols
    for symbol in all_symbols:
        print(f"Processing {symbol} ...")
        t1 = time.time()
        norm_factor = calc_normalizer(symbol, interval)
        norm_factors.append({'symbol': symbol, 'norm_factor': norm_factor})
        print(f"The normalizer factor for {symbol} is {norm_factor}")
        t2 = time.time()
        print(f"Processed {symbol} in {t2 - t1:.1f} seconds")

    # Save the normalizer factors to a CSV file
    df_norm_factors = pd.DataFrame(norm_factors)
    df_norm_factors.to_csv(f'config_candle_range_norm_factors_{interval}.csv', index=False)

    # Save the normalizer factors to a Python file as a dictionary
    norm_factors_dict = {row['symbol']: row['norm_factor'] for _, row in df_norm_factors.iterrows()}
    with open(f'config_candle_range_norm_factors_{interval}.py', 'w') as f:
        f.write('NORM_FACTORS = {\n')
        for symbol, norm_factor in norm_factors_dict.items():
            f.write(f"    '{symbol}': {norm_factor},\n")
        f.write('}\n')

    # Stop the timer
    t1 = time.time()
    print(f"Processed all symbols in {t1 - t0:.1f} seconds")
