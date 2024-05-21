import argparse
import multiprocessing
import os
import time

import pandas as pd
from discordwebhook import Discord
from SymbolRelativeStrength import DataParser, SymbolRelativeStrength
from utils import plot_rs_analysis
from config_discord import *
from config_constants import *
from config_study_params import *
from config_params_market_analysis import *

def process_symbol(symbol, df_price_btc):

    # Pause for 4 seconds to avoid rate limit issues
    time.sleep(4)

    t0 = time.time()
    print(f"Processing {symbol}")

    try:
        # Get the current symbol data
        parser_cur = DataParser(symbol=symbol, interval_basic='1m',
                                mode='live',
                                )
        df_price_cur = parser_cur.df_price

        if df_price_cur is None:
            print(f"No data available for {symbol}")
            return None

        # Make a copy of the BTC data
        df_price_btc_copy = df_price_btc.copy()

        # Calculate the mutual index
        mutual_index = df_price_cur.index.intersection(df_price_btc_copy.index)

        if mutual_index.empty:
            print(f"No intersecting data for {symbol} and BTCUSDT")
            return None

        # Filter both dataframes to keep only the mutual intersecting rows
        df_price_cur = df_price_cur.loc[mutual_index]
        df_price_btc_copy = df_price_btc_copy.loc[mutual_index]

        # Initialize and run the processor
        processor_mc = SymbolRelativeStrength(symbol=symbol,
                                              df_price_btc=df_price_btc_copy,
                                              df_price_cur=df_price_cur)
        results = processor_mc.run()

    except Exception as e:
        error_msg = f"Error processing {symbol}: {str(e)}"
        print(error_msg)
        results = None

    t1 = time.time()
    print(f"Processed {symbol} in {t1 - t0:.1f} seconds")

    return results

def initialize_btc_data():
    parser_btc = DataParser(symbol='BTCUSDT',
                            interval_basic='1m',
                            mode='live',
                            )
    return parser_btc.df_price

def load_symbols():
    # Load symbols from a list_symbols.txt file
    with open('list_symbols.txt', 'r') as f:
        all_symbols = f.read().splitlines()
    #
    # all_symbols = ['ETHUSDT', 'BNBUSDT', 'DOGEUSDT', 'NEARUSDT', 'UNFIUSDT', 'TRBUSDT', 'SOLUSDT']
    return all_symbols

def main(interval_rs='1h', interval_basic='1m', num_processes=None):
    # Initialize the BTC data for all symbols to share
    df_price_btc = initialize_btc_data()  # Fetch BTC data once

    # Load all symbols
    symbols = load_symbols()

    # Define the number of processes to use
    num_processes = num_processes or multiprocessing.cpu_count()

    # Process all symbols
    with multiprocessing.Pool(processes=num_processes) as pool:
        results_all = pool.starmap(process_symbol, [(symbol, df_price_btc) for symbol in symbols])

    # Post-processing
    results_rs = [result['rs_analysis'] for result in results_all if result and result['rs_analysis']]
    post_processing_rs(results_rs, interval_rs)

def post_processing_rs(results_rs, interval_rs):
    webhook_discord_rs = Discord(url=dict_dc_webhook_rs[interval_rs])

    if len(results_rs) == 0:
        webhook_discord_rs.post(
            content="No Relative strength data found."
        )
        return

    df_rs_analysis = pd.DataFrame.from_dict(results_rs)
    fig_rs_analysis = plot_rs_analysis(df_rs_analysis)
    fig_name = f'fig_rs_summary_{interval_rs}.png'
    fig_rs_analysis.write_image(fig_name)

    # Create the string to be posted
    webhook_discord_rs.post(
        content=f"币种相对强度 - {interval_rs}级别",
        file={
            "file1": open(fig_name, "rb"),
        },
    )
    os.remove(fig_name)

if __name__ == '__main__':
    # Timer
    start_time = time.time()

    # Run the main function
    main(num_processes=4, interval_rs='1h', interval_basic='5m')

    # Report the duration, rounded to 1 decimal place
    webhook_discord_mc = Discord(url=dict_dc_webhook_rs['1h'])
    webhook_discord_mc.post(
        content=f"--- {time.time() - start_time:.1f} seconds ---"
    )