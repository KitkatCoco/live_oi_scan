import argparse
import multiprocessing
from TradingSymbolProcessor import TradingSymbolProcessor
from utils import *

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
        results = pool.map(process_symbol, all_symbols)  # Collects all results into a list

    # Get rid of nones from the results
    results = [result for result in results if result is not None]

    # Aggregate the results
    aggregated_result = aggregate_results(results)

    return aggregated_result

def aggregate_results(results):
    # Assuming each result is a dictionary, we aggregate them here
    aggregated_data = {}
    for result in results:
        for key, value in result.items():
            if key in aggregated_data:
                aggregated_data[key].append(value)
            else:
                aggregated_data[key] = [value]

if __name__ == '__main__':
    # parser = argparse.ArgumentParser(description='Download and update cryptocurrency data for a specific time scale.')
    # parser.add_argument('interval', type=str, help='Time scale for the data, e.g., 1w, 1d, 12h, 1h')
    # args = parser.parse_args()
    # interval = args.interval

    interval = '12h'

    # Call main with the interval; the number of processes will default to the number of CPUs
    aggregated_result = main(interval)
