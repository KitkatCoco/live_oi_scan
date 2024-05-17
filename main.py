import argparse
import multiprocessing
from TradingSymbolProcessor import TradingSymbolProcessor
from utils import *

def load_symbols():
    # Load symbols from a .pkl file
    with open('list_symbols.pkl', 'rb') as f:
        symbols = pickle.load(f)
    return symbols

def worker_init(interval):
    # This will create a global processor object that can be reused within the worker process
    global processor
    processor = TradingSymbolProcessor(interval)

def process_symbol(symbol):
    processor.symbol = symbol
    return processor.run()  # Modify `run()` to return some results

def aggregate_results(results):
    # Implement your aggregation logic here
    pass

def main(interval, num_processes=None):
    all_symbols = load_symbols()
    num_processes = num_processes or multiprocessing.cpu_count()

    results = []
    with multiprocessing.Pool(num_processes, initializer=worker_init, initargs=(interval,)) as pool:
        results = pool.map(process_symbol, all_symbols)

    # Now aggregate results
    aggregated_result = aggregate_results(results)

if __name__ == '__main__':
    # parser = argparse.ArgumentParser(description='Download and update cryptocurrency data for a specific time scale.')
    # parser.add_argument('interval', type=str, help='Time scale for the data, e.g., 1w, 1d, 12h, 1h')
    # args = parser.parse_args()
    # interval = args.interval

    interval = '1h'

    # Call main with the interval; the number of processes will default to the number of CPUs
    main(interval)
