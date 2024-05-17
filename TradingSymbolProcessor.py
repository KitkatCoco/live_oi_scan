import time
import datetime
import pandas as pd
import numpy as np
import talib
from discordwebhook import Discord
from binance.um_futures import UMFutures

from config_constants import *
from config_study_params import *
from config_discord import *

from utils import *

class TradingSymbolProcessor:
    def __init__(self, interval):
        # init variables
        self.symbol = None  # Symbol is set by the worker function for each task
        self.interval = interval
        self.current_time = None  # Initialize to None or a suitable default value
        self.current_time_recent_close = None
        self.df_price = None
        self.df_price_oi = None

        # status variables
        self.flag_run_oi_analysis = False
        self.flag_run_pa_analysis = False

        # init the binance future connector
        self.um_futures_client = UMFutures()

        # init functions
        self._setup_current_timestamp()
        self._setup_thresholds()
        self._setup_webhooks()


    def _setup_thresholds(self):
        # Setup trading thresholds based on the interval
        self.threshold_price_change_pct_negative = dict_threshold_price_change_pct_negative[self.interval]
        self.threshold_oi_change_pct_positive = dict_threshold_oi_change_pct_positive[self.interval]

        # Pre-calculate static analysis parameters for OI analysis
        self.short_range_end = SEARCH_NUM_CANDLE_MIN + (SEARCH_NUM_CANDLE_MAX - SEARCH_NUM_CANDLE_MIN) // 3
        self.mid_range_end = SEARCH_NUM_CANDLE_MIN + 2 * (SEARCH_NUM_CANDLE_MAX - SEARCH_NUM_CANDLE_MIN) // 3
        self.threshold_price_change_pct_negative_short_term = self.threshold_price_change_pct_negative / 3
        self.threshold_price_change_pct_negative_mid_term = self.threshold_price_change_pct_negative * 2 / 3
        self.threshold_oi_change_pct_positive_short_term = self.threshold_oi_change_pct_positive / 3
        self.threshold_oi_change_pct_positive_mid_term = self.threshold_oi_change_pct_positive * 2 / 3

    def _setup_webhooks(self):
        # Setup Discord webhooks for notifications
        self.webhook_discord_oi = Discord(url=dict_dc_webhook_oi[self.interval])
        self.webhook_discord_oi_trading = Discord(url=dict_dc_webhook_oi_trading_signal[self.interval])
        self.webhook_discord_pa = Discord(url=dict_dc_webhook_pa[self.interval])

    def _setup_current_timestamp(self):
        interval_duiration_ms = dict_interval_duration_ms[self.interval]
        current_time = int(time.time() * 1000)  # current time in milliseconds
        current_time_recent_close = current_time - (current_time % interval_duiration_ms)
        start_time_price = current_time_recent_close - (interval_duiration_ms * NUM_CANDLE_HIST_PRICE)

        self.interval_duiration_ms = interval_duiration_ms
        self.current_time = current_time
        self.current_time_recent_close = current_time_recent_close
        self.start_time_price = start_time_price

    def _get_price_data(self):

        try:
            # price
            price_data = self.um_futures_client.klines(symbol=self.symbol,
                                                       interval=self.interval,
                                                       limit=NUM_CANDLE_HIST_PRICE,
                                                       startTime=self.start_time_price,
                                                       )
                                                       # endTime=self.current_time_recent_close)
            df_price = pd.DataFrame(price_data,
                                    columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close Time',
                                             'Quote Asset Volume', 'Number of Trades', 'Taker Buy Base Asset Volume',
                                             'Taker Buy Quote Asset Volume', 'Ignore'])
            df_price['Time'] = pd.to_datetime(df_price['Time'], unit='ms')

            # Get rid of the last open candle
            if df_price['Close Time'].iloc[-1] > self.current_time and df_price['Close Time'].iloc[-2] < self.current_time:
                df_price = df_price.iloc[:-1]

            # convert the OHLC values to float
            df_price.loc[:, 'Open'] = df_price['Open'].astype(float)
            df_price.loc[:, 'High'] = df_price['High'].astype(float)
            df_price.loc[:, 'Low'] = df_price['Low'].astype(float)
            df_price.loc[:, 'Close'] = df_price['Close'].astype(float)
            df_price.loc[:, 'Volume'] = df_price['Volume'].astype(float)

            # only keep OHLC and volume and time
            df_price = df_price[['Time', 'Open', 'High', 'Low', 'Close', 'Volume']]

            self.df_price = df_price

        except Exception as e:
            print(f"Error getting data for {self.symbol}: {e}")
            return None


    def _get_oi_data(self):
        if self.interval == '1d':
            num_candle_hist_oi = NUM_CANDLE_HIST_OI_1D
        else:
            num_candle_hist_oi = NUM_CANDLE_HIST_OI_OTHER

        # get the price data with matched length and period
        df_price_oi = self.df_price.iloc[-num_candle_hist_oi:]

        # calculate time period, convert to timestamp
        start_time_oi = int(df_price_oi['Time'].iloc[0].timestamp() * 1000)

        # get open interest data
        try:
            # get the raw open interest data
            oi_data = self.um_futures_client.open_interest_hist(symbol=self.symbol,
                                                                contractType='PERPETUAL',
                                                                period=self.interval,
                                                                limit=num_candle_hist_oi,
                                                                startTime=start_time_oi,
                                                                )

            # Process open interest data
            df_oi = pd.DataFrame(oi_data)
            df_oi.loc[:, 'sumOpenInterest'] = df_oi['sumOpenInterest'].astype(float)
            df_oi.loc[:, 'timestamp'] = pd.to_datetime(df_oi['timestamp'], unit='ms')

            # the OI data is provided at the candle close, so we need to shift the timestamp to the candle open
            df_oi['timestamp'] = df_oi['timestamp'] - pd.Timedelta(seconds=self.interval_duiration_ms / 1000)

            # compute the SMA of OI (price already calculated)
            df_oi['SMA'] = talib.SMA(df_oi['sumOpenInterest'], timeperiod=5)
            df_oi.dropna(inplace=True)

            # reset df_price_oi to match the length of df_oi using the same index
            df_price_oi = df_price_oi[df_price_oi['Time'].isin(df_oi['timestamp'])]

            # assert the time stamps are aligned
            assert df_price_oi['Time'].iloc[0] == df_oi['timestamp'].iloc[0]
            assert df_price_oi['Time'].iloc[-1] == df_oi['timestamp'].iloc[-1]

        except Exception as e:
            print(f"Error getting OI data for {self.symbol}: {e}")
            return None


    def _calc_technical_indicators(self):

        df_price = self.df_price

        # calculate indicators
        df_price['RSI'] = talib.RSI(df_price['Close'], timeperiod=14)
        df_price['SMA'] = talib.SMA(df_price['Close'], timeperiod=SMA_LENGTH_PRICE)
        df_price['ATR'] = talib.ATR(df_price['High'], df_price['Low'], df_price['Close'], timeperiod=100)
        df_price['Volume_MA'] = talib.SMA(df_price['Volume'], timeperiod=100)

        # Price-action analysis
        df_price['lower_pinbar_length'] = np.where(df_price['Open'] < df_price['Close'],
                                                   df_price['Open'] - df_price['Low'],
                                                   df_price['Close'] - df_price['Low'])
        df_price['upper_pinbar_length'] = np.where(df_price['Open'] < df_price['Close'],
                                                   df_price['High'] - df_price['Close'],
                                                   df_price['High'] - df_price['Open'])

        # update the dataframe
        df_price.dropna(inplace=True)
        self.df_price = df_price

    def run_oi_analysis(self):
        if not self.flag_run_oi_analysis:
            return  # Skip if OI analysis flag is not set

        try:
            valid_lengths = []

            for i in range(SEARCH_NUM_CANDLE_MIN, SEARCH_NUM_CANDLE_MAX, SEARCH_NUM_CANDLE_INC):
                price_change_pct = (self.df_price['SMA'].iloc[-1] - self.df_price['SMA'].iloc[-i]) / \
                                   self.df_price['SMA'].iloc[-i] * 100
                oi_change_pct = (self.df_oi['SMA'].iloc[-1] - self.df_oi['SMA'].iloc[-i]) / self.df_oi['SMA'].iloc[
                    -i] * 100

                # Condition check based on thresholds
                if i <= self.short_range_end:
                    if (price_change_pct < self.threshold_price_change_pct_negative_short_term
                            and oi_change_pct > self.threshold_oi_change_pct_positive_short_term):
                        valid_lengths.append(i)
                elif i <= self.mid_range_end:
                    if (price_change_pct < self.threshold_price_change_pct_negative_mid_term
                            and oi_change_pct > self.threshold_oi_change_pct_positive_mid_term):
                        valid_lengths.append(i)
                else:
                    if (price_change_pct < self.threshold_price_change_pct_negative
                            and oi_change_pct > self.threshold_oi_change_pct_positive):
                        valid_lengths.append(i)

            if len(valid_lengths) > 3:
                criteria_ranges = [
                    any(SEARCH_NUM_CANDLE_MIN <= x <= self.short_range_end - 1 for x in valid_lengths),
                    any(self.short_range_end <= x <= self.mid_range_end - 1 for x in valid_lengths),
                    any(self.mid_range_end <= x <= SEARCH_NUM_CANDLE_MAX for x in valid_lengths)
                ]
                if all(criteria_ranges):
                    # Process the criteria met condition
                    self.post_oi_alerts()

        except Exception as e:
            print(f"Error during OI analysis for {self.symbol}: {e}")



    """ This is the main function that will be called for each symbol."""
    def run(self):

        self._get_price_data()
        self._calc_technical_indicators()
        self._get_oi_data()
        self.run_oi_analysis()



