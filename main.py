""" This function performs live scan of price and Open interest (coin-native) to search price/OI divergence """
import requests
import pandas as pd
import numpy as np
import time
import os
import datetime
import argparse
from discordwebhook import Discord
import pickle
import talib
from binance.um_futures import UMFutures

from config_constants import *
from config_study_params import *
from utils import *


if __name__ == '__main__':

    # # Parse command line arguments for time scale
    # parser = argparse.ArgumentParser(description='Download and update cryptocurrency data for a specific time scale.')
    # parser.add_argument('interval', type=str, help='Time scale for the data, e.g., 1w, 1d, 12h, 1h')
    # parser.add_argument('num_batch_total', type=int, help='the total number of batches')
    # parser.add_argument('id_batch', type=int, help='the current batch id')
    # args = parser.parse_args()
    # interval = args.interval  # Get the timescale from command line arguments
    # num_batch_total = args.num_batch_total
    # id_batch = args.id_batch

    # local debug
    # interval = '15m'
    interval = '1d'
    interval = '12h'
    interval = '4h'
    interval = '1h'
    num_batch_total = 1
    id_batch = 1

    # update the num_candle_hist if the interval is 1d
    if interval == '1d':
        num_candle_hist_oi = 29
        use_SMA = False

    # set up thresholds
    threshold_price_change_pct_negative = dict_threshold_price_change_pct_negative[interval]
    threshold_oi_change_pct_positive = dict_threshold_oi_change_pct_positive[interval]

    # set up discord webhook
    url_dc_webhook_pa = dict_dc_webhook_pa[interval]
    url_dc_webhook_oi = dict_dc_webhook_oi[interval]
    url_dc_webhook_oi_trading = dict_dc_webhook_oi_trading_signal[interval]
    webhook_discord_pa = Discord(url=url_dc_webhook_pa)
    webhook_discord_oi = Discord(url=url_dc_webhook_oi)
    webhook_discord_oi_trading = Discord(url=url_dc_webhook_oi_trading)

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
    start_time_price = current_time_recent_close - (interval_duiration_ms * num_candle_hist_price)
    start_time_oi = current_time_recent_close - (interval_duiration_ms * num_candle_hist_oi)

    # loop through symbols:
    for symbol in list_symbols:

        t1 = time.time()

        # set up datetime
        datetime_now = datetime.datetime.utcnow()
        datetime_now_str = datetime_now.strftime(DATETIME_FORMAT)

        try:
            ### preprocessing
            # reset params
            flag_plot_exist = False
            is_rsi_oversold = False
            is_rsi_overbought = False
            is_bullish_pinbar = False
            is_bearish_pinbar = False
            is_lowest_low = False
            is_highest_high = False
            msg_rsi = ''
            msg_pinbar = ''
            msg_high_low = ''

            # price
            price_data = um_futures_client.klines(symbol=symbol,
                                                  interval=interval,
                                                  limit=num_candle_hist_price,
                                                  startTime=start_time_price,
                                                  endTime=current_time_recent_close)
            df_price = pd.DataFrame(price_data,
                                    columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close Time',
                                             'Quote Asset Volume', 'Number of Trades', 'Taker Buy Base Asset Volume',
                                             'Taker Buy Quote Asset Volume', 'Ignore'])
            df_price['Time'] = pd.to_datetime(df_price['Time'], unit='ms')
            df_price[['Open', 'High', 'Low', 'Close']] = df_price[['Open', 'High', 'Low', 'Close']].astype(float)

            # calculate indicators
            df_price['RSI'] = talib.RSI(df_price['Close'], timeperiod=14)
            df_price['SMA'] = talib.SMA(df_price['Close'], timeperiod=SMA_length_price)
            df_price['ATR'] = talib.ATR(df_price['High'], df_price['Low'], df_price['Close'], timeperiod=100)
            df_price['Volume_MA'] = talib.SMA(df_price['Volume'], timeperiod=100)
            df_price['lower_pinbar_length'] = np.where(df_price['Open'] > df_price['Close'],
                                                       df_price['Close'] - df_price['Low'],
                                                       df_price['Open'] - df_price['Low'])
            df_price['upper_pinbar_length'] = np.where(df_price['Open'] < df_price['Close'],
                                                       df_price['High'] - df_price['Close'],
                                                       df_price['High'] - df_price['Open'])
            df_price.dropna(inplace=True)

            # OI data
            # select the last num_candle_hist_price_oi from price_data for matching the length of oi_data
            df_price_oi = df_price.iloc[-num_candle_hist_oi:]

            # get the raw open interest data
            oi_data = um_futures_client.open_interest_hist(symbol=symbol,
                                                           contractType='PERPETUAL',
                                                           period=interval,
                                                           limit=num_candle_hist_oi,
                                                           startTime=start_time_oi,
                                                           endTime=current_time_recent_close)

            # Process open interest data
            df_oi = pd.DataFrame(oi_data)
            df_oi['sumOpenInterest'] = df_oi['sumOpenInterest'].astype(float)
            df_oi['timestamp'] = pd.to_datetime(df_oi['timestamp'], unit='ms')

            # the OI data is provided at the candle close, so we need to shift the timestamp to the candle open
            df_oi['timestamp'] = df_oi['timestamp'] - pd.Timedelta(seconds=interval_duiration_ms / 1000)

            # compute the SMA of OI (price already calculated)
            df_oi['SMA'] = talib.SMA(df_oi['sumOpenInterest'], timeperiod=5)
            df_oi.dropna(inplace=True)

            # reset df_price_oi to match the length of df_oi using the same index
            df_price_oi = df_price_oi[df_price_oi['Time'].isin(df_oi['timestamp'])]

            # assert the time stamps are aligned
            assert df_price_oi['Time'].iloc[0] == df_oi['timestamp'].iloc[0]
            assert df_price_oi['Time'].iloc[-1] == df_oi['timestamp'].iloc[-1]

            # 2 - PA analysis
            if flag_analysis_pa:
                # check if price action signal is met
                # get the current parameter values
                RSI_cur = df_price['RSI'].iloc[-1]
                ATR_cur = df_price['ATR'].iloc[-1]
                Vol_cur = float(df_price['Volume'].iloc[-1])
                Vol_MA_cur = df_price['Volume_MA'].iloc[-1]
                lower_pinbar_cur = df_price['lower_pinbar_length'].iloc[-1]
                upper_pinbar_cur = df_price['upper_pinbar_length'].iloc[-1]
                cur_price_open = df_price['Open'].iloc[-1]
                cur_price_close = df_price['Close'].iloc[-1]
                cur_price_low = df_price['Low'].iloc[-1]
                cur_price_high = df_price['High'].iloc[-1]

                # RSI signal
                if RSI_cur <= RSI_oversold:
                    is_rsi_oversold = True
                    msg_rsi = f'RSI超卖<{RSI_oversold}'
                if RSI_cur >= RSI_overbought:
                    is_rsi_overbought = True
                    msg_rsi = f'RSI超买>{RSI_overbought}'

                # Pinbar signal
                if (lower_pinbar_cur > pinbar_body_ATR_thres_multiplier * ATR_cur and
                        cur_price_close > cur_price_open and
                        Vol_cur > Vol_MA_thres_multiplier * Vol_MA_cur):
                    is_bullish_pinbar = True
                    msg_pinbar = '看涨针线'
                if (upper_pinbar_cur > pinbar_body_ATR_thres_multiplier * ATR_cur and
                        cur_price_close < cur_price_open and
                        Vol_cur > Vol_MA_thres_multiplier * Vol_MA_cur):
                    is_bearish_pinbar = True
                    msg_pinbar = '看跌针线'

                # check if the last candle's low is the lowest in all last num_candle_hist_oi candles
                num_candle_hl_check = min(20, len(df_price))
                if cur_price_low == df_price['Low'].iloc[-20:].min():
                    is_lowest_low = True
                    msg_high_low = '价格新低'
                if cur_price_high == df_price['High'].iloc[-20:].max():
                    is_highest_high = True
                    msg_high_low = '价格新高'

                # send signal to discord - PA alerts
                if is_rsi_oversold or is_rsi_overbought or is_bullish_pinbar or is_bearish_pinbar or is_lowest_low:
                    message_separator = '-------------------------------------\n'
                    message_time = f'时间 {datetime_now_str}\n'
                    message_name = f'标的 {symbol}\n'
                    message_timescale = f'周期 {interval}\n'
                    message_pa = f'信号 **{msg_rsi} {msg_pinbar}**\n'
                    message_combined = message_separator + message_time + message_name + message_timescale + message_pa
                    webhook_discord_pa.post(content=message_combined)

                    # if generate_plot and flag_plot_exist is False:
                    #     fig_pattern = generate_combined_chart(df_price_oi, df_oi, symbol, interval)
                    #     fig_name = f'fig_pattern_{symbol}_{interval}.png'
                    #     fig_pattern.write_image(fig_name)
                    #     webhook_discord_pa.post(
                    #         file={
                    #             "file1": open(fig_name, "rb"),
                    #         },
                    #     )
                    #     flag_plot_exist = True

            # 3 - OI analysis
            if flag_analysis_oi:
                # check in the last N candles, if trading criteria is met
                valid_lengths = []
                for i in range(search_num_candle_min, search_num_candle_max, search_num_candle_inc):

                    try:
                        arr_price_change_pct = (df_price_oi['SMA'].iloc[-1] - df_price_oi['SMA'].iloc[-i]) /df_price_oi['SMA'].iloc[-i]
                        arr_price_change_pct = arr_price_change_pct * 100
                        arr_price_change_pct = round(arr_price_change_pct, 2)

                        arr_open_interest_change_pct = (df_oi['SMA'].iloc[-1] - df_oi['SMA'].iloc[-i]) /df_oi['SMA'].iloc[-i]
                        arr_open_interest_change_pct = arr_open_interest_change_pct * 100
                        arr_open_interest_change_pct = round(arr_open_interest_change_pct, 2)

                        # compare if the change of price and OI meet the requirement
                        if arr_price_change_pct < threshold_price_change_pct_negative \
                            and arr_open_interest_change_pct > threshold_oi_change_pct_positive:
                            valid_lengths.append(i)

                    except:
                        continue

                # if signal is found
                if len(valid_lengths) > 3:  # at least 4 valid lengths

                    # calculate the min and max value in the last N=search_num_candle_max candles of df_oi
                    oi_min = df_oi['sumOpenInterest'].iloc[-search_num_candle_max:].min()
                    oi_max = df_oi['sumOpenInterest'].iloc[-search_num_candle_max:].max()
                    oi_diff_pct = (oi_max - oi_min) / oi_min * 100

                    # check for entry signal - long case only
                    decision_entry_oi = False
                    # if RSI_cur <= RSI_oversold and \
                    #         lower_pinbar_cur > pinbar_body_ATR_thres_multiplier * ATR_cur and \
                    #         Vol_cur > Vol_MA_thres_multiplier * Vol_MA_cur:
                    if is_rsi_oversold or is_lowest_low or is_bullish_pinbar:
                        decision_entry_oi = True

                    # send signal to discord - OI alerts
                    message_separator = '-------------------------------------\n'
                    message_time = f'时间 {datetime_now_str}\n'
                    message_name = f'标的 {symbol}\n'
                    message_timescale = f'周期 {interval}\n'
                    message_oi_change = f'**涨幅 {arr_open_interest_change_pct}% (OI)**\n'
                    message_combined = message_separator + message_time + message_name + message_timescale + message_oi_change
                    webhook_discord_oi.post(content=message_combined)

                    if decision_entry_oi:
                        message_entry = f'**OI 交易信号 Long-only (价格)**\n'
                        message_combined_trading = message_separator + message_time + message_name + message_timescale + message_entry
                        webhook_discord_oi_trading.post(content=message_combined_trading)

                    # if generate a plot, send the plot to the channel
                    if generate_plot:

                        # check if plot already exists
                        if flag_plot_exist:
                            pass
                        else:
                            fig_pattern = generate_combined_chart(df_price_oi, df_oi, symbol, interval)
                            fig_name = f'fig_pattern_{symbol}_{interval}.png'
                            fig_pattern.write_image(fig_name)

                        # now send the plot
                        webhook_discord_oi.post(
                            file={
                                "file1": open(fig_name, "rb"),
                            },
                        )

                        if decision_entry_oi:
                            webhook_discord_oi_trading.post(
                                file={
                                    "file1": open(fig_name, "rb"),
                                },
                            )

                        # reset plot status
                        os.remove(fig_name)
                        flag_plot_exist = False

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



