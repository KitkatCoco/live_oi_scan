import argparse
import multiprocessing
from discordwebhook import Discord

from TradingSymbolProcessor import TradingSymbolProcessor
from utils import *

from config_discord import *
from config_constants import *
from config_study_params import *


def load_symbols():
    # Load symbols from a list_symbols.txt file
    with open('list_symbols.txt', 'r') as f:
        all_symbols = f.read().splitlines()
    return all_symbols

def worker_init(interval):
    # This will create a global processor object that can be reused within the worker process
    global processor
    processor = TradingSymbolProcessor(interval)

def process_symbol(symbol):
    # print(f"Processing {symbol}")
    processor.setup_for_new_symbol(symbol)
    results = processor.run()

    # pause for 0.1 second
    time.sleep(0.8)

    return results

def main(interval, num_processes=None):
    all_symbols = load_symbols()
    num_processes = num_processes or multiprocessing.cpu_count()

    with multiprocessing.Pool(num_processes, initializer=worker_init, initargs=(interval,)) as pool:
        results_all = pool.map(process_symbol, all_symbols)  # Collects all results into a list

    # process the OI data
    results_oi = [result['oi_analysis'] for result in results_all if result['oi_analysis'] is not None]
    post_processing_oi(results_oi, interval)

    # process the price action data
    results_pa = [result['pa_analysis'] for result in results_all if result['pa_analysis'] is not None]
    post_processing_pa(results_pa, interval)


def post_processing_oi(results_oi, interval):
    webhook_discord_oi = Discord(url=dict_dc_webhook_oi[interval])

    if len(results_oi) == 0:
        webhook_discord_oi.post(
            content="No Open Interest data found."
        )
        return

    else:
        df_oi_analysis = pd.DataFrame.from_dict(results_oi)
        fig_oi_analysis = plot_oi_analysis(df_oi_analysis, interval)
        fig_name = f'fig_oi_summary_{interval}.png'
        fig_oi_analysis.write_image(fig_name)
        df_oi_analysis_sorted = df_oi_analysis.sort_values(by="max_open_interest_change_pct", ascending=False)
        symbols = df_oi_analysis_sorted['symbol'].tolist()
        symbols_str = '初选名单: ' + ' '.join(symbols)
        webhook_discord_oi.post(
            content=f"{interval}级别{symbols_str}",
            file={
                "file1": open(fig_name, "rb"),
            },
        )
        os.remove(fig_name)


def post_processing_pa(results_pa, interval):
    webhook_discord_pa = Discord(url=dict_dc_webhook_pa[interval])

    if len(results_pa) == 0:
        webhook_discord_pa.post(
            content="No Price Action data found."
        )
        return

    else:
        df_pa_analysis = pd.DataFrame.from_dict(results_pa)


        fig_pa_analysis = plot_pa_analysis(df_pa_analysis, interval)
        fig_name = f'fig_pa_summary_{interval}.png'
        fig_pa_analysis.write_image(fig_name)

        # write all the symbol names to two separate lists, one for oversold and one for overbought
        df_pa_analysis_long = df_pa_analysis[df_pa_analysis['RSI'] < RSI_OVERSOLD]
        df_pa_analysis_short = df_pa_analysis[df_pa_analysis['RSI'] > RSI_OVERBOUGHT]

        # sort the symbols by RSI
        df_pa_analysis_long = df_pa_analysis_long.sort_values(by="pin_ratio", ascending=False)
        df_pa_analysis_short = df_pa_analysis_short.sort_values(by="pin_ratio", ascending=False)

        # get the symbol names
        symbols_long = df_pa_analysis_long['symbol'].tolist()
        symbols_short = df_pa_analysis_short['symbol'].tolist()

        # create the string to be posted
        symbols_str = '做多关注: ' + ' '.join(symbols_long) + '\n' + '做空关注: ' + ' '.join(symbols_short)

        webhook_discord_pa.post(
            content=f"{interval}级别\n{symbols_str}",
            file={
                "file1": open(fig_name, "rb"),
            },
        )
        os.remove(fig_name)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download and update cryptocurrency data for a specific time scale.')
    parser.add_argument('interval', type=str, help='Time scale for the data, e.g., 1h, 4h, 12h')
    args = parser.parse_args()
    interval = args.interval

    # debug
    # interval = '15m'
    # interval = '1h'
    # interval = '4h'
    # interval = '12h'
    # interval = '1h'


    # timer
    start_time = time.time()

    # run the main function
    main(interval)

    # report the duration, round to 1 decimal places
    webhook_discord_oi = Discord(url=dict_dc_webhook_oi[interval])
    webhook_discord_oi.post(
        content=f"--- {time.time() - start_time:.1f} seconds ---"
    )

    # timer
    print("--- %s seconds ---" % (time.time() - start_time))
