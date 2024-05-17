import argparse
import multiprocessing
from TradingSymbolProcessor import TradingSymbolProcessor
from utils import *

from config_discord import *
from discordwebhook import Discord


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
    print(f"Processing {symbol}")
    processor.setup_for_new_symbol(symbol)
    results = processor.run()

    # pause for 0.1 second
    time.sleep(0.5)

    if results is not None:
        print(f"Processed {symbol}")
    return results

def main(interval, num_processes=None):
    all_symbols = load_symbols()
    num_processes = num_processes or multiprocessing.cpu_count()
    # num_processes = 1
    with multiprocessing.Pool(num_processes, initializer=worker_init, initargs=(interval,)) as pool:
        results_all = pool.map(process_symbol, all_symbols)  # Collects all results into a list

    # process the OI data
    results_oi = [result['oi_analysis'] for result in results_all if result['oi_analysis'] is not None]

    # Aggregate the results
    post_processing_oi(results_oi, interval)

    # convert dict to dataframe

def post_processing_oi(results_oi, interval):

    df_oi_analysis = pd.DataFrame.from_dict(results_oi)
    fig_oi_analysis = plot_oi_analysis(df_oi_analysis, interval)
    fig_name = f'fig_oi_summary_{interval}.png'
    fig_oi_analysis.write_image(fig_name)

    # send the plot to the channel
    webhook_discord_oi = Discord(url=dict_dc_webhook_oi[interval])
    webhook_discord_oi.post(
        file={
            "file1": open(fig_name, "rb"),
        },
    )

    # remove the plot
    os.remove(fig_name)





if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download and update cryptocurrency data for a specific time scale.')
    parser.add_argument('interval', type=str, help='Time scale for the data, e.g., 1h, 4h, 12h')
    args = parser.parse_args()
    interval = args.interval

    # timer
    start_time = time.time()

    # run the main function
    aggregated_result = main(interval)

    # timer
    print("--- %s seconds ---" % (time.time() - start_time))
