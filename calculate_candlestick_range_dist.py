from SymbolRelativeStrength import DataParser
import time
import pandas as pd
from multiprocessing import Process, Queue, cpu_count

def load_symbols():
    # Load symbols from a list_symbols.txt file
    with open('list_symbols.txt', 'r') as f:
        all_symbols = f.read().splitlines()
    return all_symbols

def worker(symbol_queue, result_queue, delay):
    while not symbol_queue.empty():
        symbol = symbol_queue.get()
        try:
            # Add a fixed sleep time to spread out the API requests
            time.sleep(delay)
            print(f"Processing {symbol}")
            t0 = time.time()
            # Get the current symbol data
            parser_cur = DataParser(symbol, '1m')
            norm_factor = parser_cur.norm_factor
            t1 = time.time()
            print(f"Processed {symbol} in {t1 - t0:.1f} seconds")

        except Exception as e:
            error_msg = f"Error processing {symbol}: {str(e)}"
            print(error_msg)
            norm_factor = None
        result_queue.put({'symbol': symbol, 'norm_factor': norm_factor})

if __name__ == '__main__':
    # Start the timer
    t0 = time.time()

    # Load all symbols
    all_symbols = load_symbols()
    all_symbols.append('BTCUSDT')
    print('Processing a total number of symbols:', len(all_symbols))

    # Create queues
    symbol_queue = Queue()
    result_queue = Queue()

    # Populate the symbol queue
    for symbol in all_symbols:
        symbol_queue.put(symbol)

    # Determine the number of processes to use
    # num_processes = min(len(all_symbols), cpu_count())
    num_processes = 6

    # Calculate a delay to avoid hitting the rate limit
    delay = 10

    # Create a list of processes
    processes = []
    for i in range(num_processes):
        p = Process(target=worker, args=(symbol_queue, result_queue, delay))
        processes.append(p)
        p.start()
        time.sleep(delay)  # Stagger the start of each process

    # Wait for all processes to finish
    for p in processes:
        p.join()

    # Collect results from the result queue
    norm_factors = []
    while not result_queue.empty():
        norm_factors.append(result_queue.get())

    # Save the normalizer factors to a CSV file
    df_norm_factors = pd.DataFrame(norm_factors)
    df_norm_factors.to_csv('config_candle_range_1min_norm_factors.csv', index=False)

    # Save the normalizer factors to a Python file as a dictionary
    norm_factors_dict = {row['symbol']: row['norm_factor'] for _, row in df_norm_factors.iterrows()}
    with open('config_candle_range_1min_norm_factors.py', 'w') as f:
        f.write('NORM_FACTORS = {\n')
        for symbol, norm_factor in norm_factors_dict.items():
            f.write(f"    '{symbol}': {norm_factor},\n")
        f.write('}\n')

    # Stop the timer
    t1 = time.time()
    print(f"Processed all symbols in {t1 - t0:.1f} seconds")
