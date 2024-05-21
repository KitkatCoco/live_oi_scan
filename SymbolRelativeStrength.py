import time
import datetime
import pandas as pd
import numpy as np
import talib
from discordwebhook import Discord
from binance import Client
from ratelimit import limits, sleep_and_retry
import traceback

from config_params_market_analysis import *
from config_constants import *
from config_binance_api import *


@sleep_and_retry
@limits(calls=1, period=2)  # 2 requests per second
def safe_api_call(client, symbol, interval, start_time):
    return client.futures_historical_klines(
        symbol=symbol,
        interval=interval,
        start_str=start_time
    )

class DataParser:
    def __init__(self, symbol,
                 interval_basic='1m',
                 mode='complete',    # mode - complete or live
                 ):
        self.symbol = symbol
        self.interval_basic = interval_basic
        self.client = Client(api_key=API_KEY, api_secret=API_SECRET)

        # default - for long term history data analysis for range distribution analysis
        if mode == 'complete':
            self.num_candle_preprocess = NUM_CANDLE_RS_PREPROCESS[interval_basic]
            self.num_candle_analysis = NUM_CANDLE_RS_ANALYSIS[interval_basic]
            self._setup_current_timestamp()
            self._get_price_data()
            self._calc_technical_indicators()
        # for live data analysis - only download recent data, use pre-saved norm factors
        elif mode == 'live':
            self.num_candle_analysis = self.num_candle_analysis + 300
            self._setup_current_timestamp()
            self._get_price_data()
            self._calc_technical_indicators_live()

    def _setup_current_timestamp(self):
        current_time = int(time.time() * 1000)
        self.interval_duration_ms = dict_interval_duration_ms[self.interval_basic]
        self.current_time_recent_close = current_time - (current_time % self.interval_duration_ms)
        self.current_time = current_time
        self.start_time_price = (self.current_time_recent_close
                                 - self.num_candle_preprocess * dict_interval_duration_ms[self.interval_basic])

    def _get_price_data(self):
        try:
            # Fetch price data
            price_data = safe_api_call(self.client, self.symbol, self.interval_basic, self.start_time_price)

            # Set the columns
            columns = ["Date", "Open", "High", "Low", "Close", "Volume",
                       "Close time", "Quote asset volume", "Number of trades",
                       "Taker buy base asset volume", "Taker buy quote asset volume", "Ignore"]
            df_price = pd.DataFrame(price_data, columns=columns)
            df_price['Time'] = pd.to_datetime(df_price['Date'], unit='ms')

            # Get rid of the last open candle
            df_price = df_price[:-1]

            # Convert the OHLC values to float
            df_price.loc[:, 'Open'] = df_price['Open'].astype(float)
            df_price.loc[:, 'High'] = df_price['High'].astype(float)
            df_price.loc[:, 'Low'] = df_price['Low'].astype(float)
            df_price.loc[:, 'Close'] = df_price['Close'].astype(float)
            df_price.loc[:, 'Volume'] = df_price['Volume'].astype(float)

            # Only keep OHLC and volume and time
            df_price = df_price[['Time', 'Open', 'High', 'Low', 'Close', 'Volume']]

            # Set the index to be the time
            df_price.set_index('Time', inplace=True)

            self.df_price = df_price

        except Exception as e:
            error_msg = f"Error getting price data for {self.symbol}: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            self.df_price = None


    def _calc_technical_indicators(self):
        df_price = self.df_price

        # Calculate the intra-candle change (percentage) in price
        df_price['Price Change'] = (df_price['Close'] - df_price['Open']) / df_price['Open'] * 100

        # Create two new arrays (not columns) to save the positive and negative price change values
        arr_price_change_positive = np.where(df_price['Price Change'] > 0, df_price['Price Change'], 0)
        arr_price_change_negative = np.where(df_price['Price Change'] < 0, df_price['Price Change'], 0)

        arr_price_change_positive = arr_price_change_positive[arr_price_change_positive > 0]
        arr_price_change_negative = -arr_price_change_negative[arr_price_change_negative < 0]

        # Calculate the 90% quantile of the positive and negative price change values
        threshold_price_change_positive = np.quantile(arr_price_change_positive, 0.95)
        threshold_price_change_negative = np.quantile(arr_price_change_negative, 0.95)

        # Get the average of abs values as the normalizing factor
        norm_factor = np.mean([threshold_price_change_positive, threshold_price_change_negative])
        self.norm_factor = norm_factor

        # Normalize the price change values
        df_price['Price Change Normalized'] = df_price['Price Change'] / norm_factor

        # Update the dataframe
        df_price.dropna(inplace=True)
        self.df_price = df_price

    def _calc_technical_indicators_live(self):

        from config_candle_range_1min_norm_factors import NORM_FACTORS

        df_price = self.df_price

        # instead of calculating a long history ranges, use pre-saved values
        norm_factor = NORM_FACTORS[self.symbol]
        self.norm_factor = norm_factor

        # Calculate the intra-candle change (percentage) in price
        df_price['Price Change'] = (df_price['Close'] - df_price['Open']) / df_price['Open'] * 100
        df_price['Price Change Normalized'] = df_price['Price Change'] / norm_factor

        # Update the dataframe
        df_price.dropna(inplace=True)
        self.df_price = df_price



class SymbolRelativeStrength:
    def __init__(self,
                 symbol,
                 df_price_btc,
                 df_price_cur,
                 interval_rs='1h',
                 interval_basic='1m',
                 ):

        self.symbol = symbol
        self.interval_rs = interval_rs
        self.interval_basic = interval_basic
        self.df_price_cur = df_price_cur
        self.df_price_btc = df_price_btc
        self.num_1min_candle_analysis = NUM_CANDLE_RS_ANALYSIS[interval_basic]
        self.num_candle_analysis = NUM_CANDLE_RS_ANALYSIS[interval_basic]

    def run_symbol_relative_strength(self):
        try:
            # Get the last num_1min_candle_analysis candles of price data
            df_price_btc = self.df_price_btc[-self.num_1min_candle_analysis:].copy()
            df_price_cur = self.df_price_cur[-self.num_1min_candle_analysis:].copy()

            # Generate new DataFrames for positive and negative price change, include the volume
            df_price_cur_positive = df_price_cur[df_price_cur['Price Change'] > 0].copy()
            df_price_cur_negative = df_price_cur[df_price_cur['Price Change'] < 0].copy()

            df_price_btc_positive = df_price_btc.loc[df_price_cur_positive.index].copy()
            df_price_btc_negative = df_price_btc.loc[df_price_cur_negative.index].copy()

            # Calculate the weights for both dataframes using the squared volume
            weight_total_btc_positive = np.sum(df_price_btc_positive['Volume'] ** 2)
            weight_total_btc_negative = np.sum(df_price_btc_negative['Volume'] ** 2)
            weight_total_cur_positive = np.sum(df_price_cur_positive['Volume'] ** 2)
            weight_total_cur_negative = np.sum(df_price_cur_negative['Volume'] ** 2)

            # Calculate the relative weights
            df_price_cur_positive['Weight'] = df_price_cur_positive['Volume'] ** 2 / weight_total_cur_positive
            df_price_cur_negative['Weight'] = df_price_cur_negative['Volume'] ** 2 / weight_total_cur_negative
            df_price_btc_positive['Weight'] = df_price_btc_positive['Volume'] ** 2 / weight_total_btc_positive
            df_price_btc_negative['Weight'] = df_price_btc_negative['Volume'] ** 2 / weight_total_btc_negative

            # Calculate the averaged weights
            df_price_cur_positive['Weight Average'] = (
                    (df_price_cur_positive['Weight'] + df_price_btc_positive['Weight']) / 2)
            df_price_cur_negative['Weight Average'] = (
                    (df_price_cur_negative['Weight'] + df_price_btc_negative['Weight']) / 2)

            # Calculate the relative strength w.r.t. BTC
            df_price_cur_positive['Relative Strength'] = df_price_cur_positive['Price Change Normalized'] - \
                                                         df_price_btc_positive['Price Change Normalized']
            df_price_cur_negative['Relative Strength'] = df_price_cur_negative['Price Change Normalized'] - \
                                                         df_price_btc_negative['Price Change Normalized']

            # Apply the weights
            df_price_cur_positive['Relative Strength Weighted'] = df_price_cur_positive['Relative Strength'] * \
                                                                  df_price_cur_positive['Weight Average']
            df_price_cur_negative['Relative Strength Weighted'] = df_price_cur_negative['Relative Strength'] * \
                                                                  df_price_cur_negative['Weight Average']

            # Calculate the relative strength which is the sum of the weighted relative strength
            rsp = np.sum(df_price_cur_positive['Relative Strength Weighted'])
            rsn = -np.sum(df_price_cur_negative['Relative Strength Weighted'])

            # Save the results
            relative_strength_results = {
                'symbol': self.symbol,
                'rsp': rsp,
                'rsn': rsn,
            }

            return relative_strength_results

        except Exception as e:
            # Trace back the error and print the line number
            error_msg = f"Error calculating relative strength for {self.symbol}: {str(e)}"
            print(error_msg)
            traceback.print_exc()

        return None

    def run(self):
        """Main function to run the whole market analysis process"""

        # Initialize the dictionary to store the results
        dict_results = {}

        # Relative strength (RS) analysis
        relative_strength_results = self.run_symbol_relative_strength()
        dict_results['rs_analysis'] = relative_strength_results

        return dict_results
