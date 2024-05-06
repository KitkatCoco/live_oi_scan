""" This function performs live scan of price and Open interest (coin-native) to search price/OI divergence """
import pickle

from config_constants import *
from config_study_params import *
from utils import *

from binance.um_futures import UMFutures



if __name__ == '__main__':

    # Parse command line arguments for time scale
    parser = argparse.ArgumentParser(description='Download and update cryptocurrency data for a specific time scale.')
    parser.add_argument('interval', type=str, help='Time scale for the data, e.g., 1w, 1d, 12h, 1h')
    parser.add_argument('num_batch_total', type=int, help='the total number of batches')
    parser.add_argument('id_batch', type=int, help='the current batch id')
    args = parser.parse_args()
    interval = args.interval  # Get the timescale from command line arguments
    num_batch_total = args.num_batch_total
    id_batch = args.id_batch

    # interval = '1h'
    # num_batch_total = 1
    # id_batch = 1

    # start the timer
    t0 = time.time()

    # Initialize Binance UMFutures client
    um_futures_client = UMFutures()

    # read the list of symbols from a local file
    with open('list_symbols.pkl', 'rb') as f:
        list_symbols = pickle.load(f)

    # divide the list by num_batch_total divisions, and then take the current batch based on id_batch
    num_symbols = len(list_symbols)
    num_symbols_per_batch = num_symbols // num_batch_total
    list_symbols = list_symbols[(id_batch - 1) * num_symbols_per_batch: id_batch * num_symbols_per_batch]

    # Calculate the most recent close candle's timestamp, by using interval_duiration_ms
    interval_duiration_ms = dict_interval_duration_ms[interval]
    current_time = int(time.time() * 1000)  # current time in milliseconds
    current_time_recent_close = current_time - (current_time % interval_duiration_ms)
    start_time = current_time_recent_close - (interval_duiration_ms * num_candle_hist)  # Go back 500 x 5 minutes


    # loop through symbols:
    for symbol in list_symbols:

        t1 = time.time()

        try:
            # get the raw price data
            price_data = um_futures_client.klines(symbol=symbol,
                                                  interval=interval,
                                                  limit=num_candle_hist,
                                                  startTime=start_time,
                                                  endTime=current_time_recent_close)

            # get the raw open interest data
            oi_data = um_futures_client.open_interest_hist(symbol=symbol,
                                                           contractType='PERPETUAL',
                                                           period=interval,
                                                           limit=num_candle_hist,
                                                           startTime=start_time,
                                                           endTime=current_time_recent_close)

            # Process price data
            df_price = pd.DataFrame(price_data,
                                    columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close Time', 'Quote Asset Volume', 'Number of Trades', 'Taker Buy Base Asset Volume', 'Taker Buy Quote Asset Volume', 'Ignore'])
            df_price['Time'] = pd.to_datetime(df_price['Time'], unit='ms')
            df_price[['Open', 'High', 'Low', 'Close']] = df_price[['Open', 'High', 'Low', 'Close']].astype(float)

            # Process open interest data
            df_oi = pd.DataFrame(oi_data)
            df_oi['sumOpenInterest'] = df_oi['sumOpenInterest'].astype(float)
            df_oi['timestamp'] = pd.to_datetime(df_oi['timestamp'], unit='ms')

            # the OI data is provided at the candle close, so we need to shift the timestamp to the candle open
            df_oi['timestamp'] = df_oi['timestamp'] - pd.Timedelta(seconds=interval_duiration_ms / 1000)

            # assert the time stamps are aligned
            assert df_price['Time'].iloc[0] == df_oi['timestamp'].iloc[0]
            assert df_price['Time'].iloc[-1] == df_oi['timestamp'].iloc[-1]

            # plot df_oi[

            # Compute the moving averages SMA
            df_price['SMA'] = df_price['High'].rolling(window=SMA_length).mean()
            df_oi['SMA'] = df_oi['sumOpenInterest'].rolling(window=SMA_length).mean()
            df_price.dropna(inplace=True)
            df_oi.dropna(inplace=True)

            # check in the last N candles, if trading criteria is met
            valid_lengths = []
            for i in range(search_num_candle_min, search_num_candle_max, 1):

                # calculate the percentage changes
                arr_price_change_pct = (100 * (df_price['SMA'].iloc[-1] - df_price['SMA'].iloc[-i])
                                        /df_price['SMA'].iloc[-i])
                arr_open_interest_change_pct = (100 * (df_oi['SMA'].iloc[-1] - df_oi['SMA'].iloc[-i])
                                        /df_oi['SMA'].iloc[-i])
                arr_price_change_pct = round(arr_price_change_pct, 2)
                arr_open_interest_change_pct = round(arr_open_interest_change_pct, 2)

                # compare if the change of price and OI meet the requirement
                if arr_price_change_pct < threshold_price_change_pct_negative \
                    and arr_open_interest_change_pct > threshold_oi_change_pct_positive:
                    valid_lengths.append(i)

            # if signal is found
            if valid_lengths != []:

                # set up datetime
                datetime_now = datetime.datetime.utcnow()
                datetime_now_str = datetime_now.strftime(DATETIME_FORMAT)

                # send signal to discord
                # set up message
                message_separator = '-------------------------------------\n'
                message_time = f'时间 {datetime_now_str}\n'
                message_name = f'标的 {symbol}\n'
                message_timescale = f'周期 {interval}\n'

                # combine the message
                message_combined = message_separator + message_time + message_name + message_timescale

                # send message
                url_dc_webhook = dict_dc_webhook['interval']
                webhook_discord = Discord(url=url_dc_webhook)
                webhook_discord.post(content=message_combined)

                # if generate a plot
                if generate_plot:
                    fig_pattern = generate_combined_chart(df_price, df_oi, symbol, interval)
                    fig_pattern.write_image('fig_pattern.png')
                    webhook_discord.post(
                        file={
                            "file1": open("fig_pattern.png", "rb"),
                        },
                    )
                    os.remove('fig_pattern.png')

            # check total run time
            t2 = time.time()
            print(f'symbol: {symbol}, time: {t2 - t1}s')

        except Exception as e:
            print(f"Failed to process {symbol}: {e}")
            continue

        time.sleep(0.1)  # Sleep for 1 second to avoid rate limiting

    # check total run time
    t3 = time.time()
    print(f'Time to complete analysis: {t3 - t0} seconds')



