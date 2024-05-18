import time
import datetime
import pandas as pd
import numpy as np
import talib
from discordwebhook import Discord
from binance.um_futures import UMFutures
import traceback

from config_constants import *
from config_study_params import *
from config_discord import *
from config_thresholds import *

from utils import *

class TradingSymbolProcessor:
    def __init__(self, interval):
        self.interval = interval
        self.um_futures_client = UMFutures()
        self._setup_webhooks()
        self._setup_static_parameters()
        self._setup_current_timestamp()


    def setup_for_new_symbol(self, symbol):
        # This method resets and initializes everything necessary for a new symbol
        self.symbol = symbol
        self.df_price = None
        self.df_price_oi = None
        self.df_oi = None


    def _setup_static_parameters(self):
        # Static parameters initialized once since they don't change per symbol
        self.threshold_price_change_pct_negative = dict_threshold_price_change_pct_negative[self.interval]
        self.threshold_oi_change_pct_positive = dict_threshold_oi_change_pct_positive[self.interval]
        self.threshold_price_change_pct_negative = dict_threshold_price_change_pct_negative[self.interval]
        self.threshold_oi_change_pct_positive = dict_threshold_oi_change_pct_positive[self.interval]
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
        current_time = int(time.time() * 1000)
        self.interval_duiration_ms = dict_interval_duration_ms[self.interval]
        self.current_time_recent_close = current_time - (current_time % self.interval_duiration_ms)
        self.current_time = current_time
        self.start_time_price = (self.current_time_recent_close
                                 - NUM_CANDLE_HIST_PRICE * dict_interval_duration_ms[self.interval])


    def _get_price_data(self):

        try:
            # price
            price_data = self.um_futures_client.klines(symbol=self.symbol,
                                                       interval=self.interval,
                                                       limit=NUM_CANDLE_HIST_PRICE,
                                                       startTime=self.start_time_price,
                                                       )

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
            error_msg = f"Error getting OI data for {self.symbol}: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            self.df_price = None


    def _get_oi_data(self):
        if self.interval == '1d':
            num_candle_hist_oi = NUM_CANDLE_HIST_OI_1D
        else:
            num_candle_hist_oi = NUM_CANDLE_HIST_OI_OTHER

        # get open interest data
        try:

            # get the price data with matched length and period
            df_price_oi = self.df_price.iloc[-num_candle_hist_oi:]

            # calculate time period, convert to timestamp
            start_time_oi = int(df_price_oi['Time'].iloc[0].timestamp() * 1000)

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

            # reset df_price_oi to match the length of df_oi using the same index
            df_price_oi = df_price_oi[df_price_oi['Time'].isin(df_oi['timestamp'])]

            # save the OI data
            df_oi.dropna(inplace=True)
            self.df_oi = df_oi

        except Exception as e:
            error_msg = f"Error getting OI data for {self.symbol}: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            self.df_oi = None


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


    def run_pa_analysis(self):

        msg_rsi = ''
        msg_pinbar = ''
        # msg_poway = ''

        try:
            # get the current parameter values
            RSI_cur = self.df_price['RSI'].iloc[-1]
            ATR_cur = self.df_price['ATR'].iloc[-1]
            Vol_cur = float(self.df_price['Volume'].iloc[-1])
            Vol_MA_cur = self.df_price['Volume_MA'].iloc[-1]
            lower_pinbar_cur = self.df_price['lower_pinbar_length'].iloc[-1]
            upper_pinbar_cur = self.df_price['upper_pinbar_length'].iloc[-1]
            cur_price_open = self.df_price['Open'].iloc[-1]
            cur_price_close = self.df_price['Close'].iloc[-1]
            cur_price_low = self.df_price['Low'].iloc[-1]
            cur_price_high = self.df_price['High'].iloc[-1]

            # RSI signal
            is_rsi_oversold = False
            if RSI_cur <= RSI_OVERSOLD:
                is_rsi_oversold = True
                msg_rsi = f'RSI超卖<{RSI_OVERSOLD}'
            if RSI_cur >= RSI_OVERBOUGHT:
                is_rsi_overbought = True
                msg_rsi = f'RSI超买>{RSI_OVERBOUGHT}'

            # Pinbar signal
            is_bullish_pinbar = False
            if lower_pinbar_cur > PINBAR_BODY_ATR_THRES_MULTIPLIER * ATR_cur and \
                    cur_price_close > cur_price_open:
                is_bullish_pinbar = True
                msg_pinbar = '看涨针线'
            if upper_pinbar_cur > PINBAR_BODY_ATR_THRES_MULTIPLIER * ATR_cur and \
                    cur_price_close < cur_price_open:
                is_bearish_pinbar = True
                msg_pinbar = '看跌针线'

            # check if the last candle's low is the lowest in all last num_candle_hist_oi candles
            is_lowest_low = False
            num_candle_hl_check = min(POWAY_NUM_CANDLE_LOOKBACK, len(self.df_price))
            if cur_price_low == self.df_price['Low'].iloc[-POWAY_NUM_CANDLE_LOOKBACK:].min():
                is_lowest_low = True
                # msg_poway = '价格新低'
            if cur_price_high == self.df_price['High'].iloc[-POWAY_NUM_CANDLE_LOOKBACK:].max():
                is_highest_high = True
                # msg_poway = '价格新高'

            # Only all conditions are met, return the results
            if is_rsi_oversold and is_bullish_pinbar and is_lowest_low:
                return {'symbol': self.symbol,
                        'direction': 'Long',
                        'RSI': RSI_cur,
                        'pin_ratio': lower_pinbar_cur / ATR_cur,
                        }
            elif is_rsi_overbought and is_bearish_pinbar and is_highest_high:
                return {'symbol': self.symbol,
                        'direction': 'Short',
                        'RSI': RSI_cur,
                        'pin_ratio': upper_pinbar_cur / ATR_cur,
                        }
            else:
                return None

        except Exception as e:
            error_msg = f"Error getting PA data for {self.symbol}: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            return None

    def run_oi_analysis(self):

        try:
            valid_lengths = []
            list_price_change_pct = []
            list_oi_change_pct = []

            for i in range(SEARCH_NUM_CANDLE_MIN, SEARCH_NUM_CANDLE_MAX, SEARCH_NUM_CANDLE_INC):
                price_change_pct = ((self.df_price['SMA'].iloc[-1] - self.df_price['SMA'].iloc[-i])
                                    / self.df_price['SMA'].iloc[-i] * 100)
                oi_change_pct = ((self.df_oi['SMA'].iloc[-1] - self.df_oi['SMA'].iloc[-i])
                                 / self.df_oi['SMA'].iloc[-i] * 100)

                # Condition check based on thresholds
                if i <= self.short_range_end:
                    if (price_change_pct < self.threshold_price_change_pct_negative_short_term
                            and oi_change_pct > self.threshold_oi_change_pct_positive_short_term):
                        valid_lengths.append(i)
                        list_price_change_pct.append(price_change_pct)
                        list_oi_change_pct.append(oi_change_pct)

                elif i <= self.mid_range_end:
                    if (price_change_pct < self.threshold_price_change_pct_negative_mid_term
                            and oi_change_pct > self.threshold_oi_change_pct_positive_mid_term):
                        valid_lengths.append(i)
                        list_price_change_pct.append(price_change_pct)
                        list_oi_change_pct.append(oi_change_pct)
                else:
                    if (price_change_pct < self.threshold_price_change_pct_negative
                            and oi_change_pct > self.threshold_oi_change_pct_positive):
                        valid_lengths.append(i)
                        list_price_change_pct.append(price_change_pct)
                        list_oi_change_pct.append(oi_change_pct)

            if len(valid_lengths) > 3:
                criteria_ranges = [
                    any(SEARCH_NUM_CANDLE_MIN <= x <= self.short_range_end - 1 for x in valid_lengths),
                    any(self.short_range_end <= x <= self.mid_range_end - 1 for x in valid_lengths),
                    any(self.mid_range_end <= x <= SEARCH_NUM_CANDLE_MAX for x in valid_lengths)
                ]
                if all(criteria_ranges):
                    # find the maximum OI change and max price drop
                    max_open_interest_change_pct = max(list_oi_change_pct)
                    max_price_drop_pct = -min(list_price_change_pct)

                    oi_analysis_results = {
                        'symbol': self.symbol,
                        'max_open_interest_change_pct': max_open_interest_change_pct,
                        'max_price_drop_pct': max_price_drop_pct
                    }

                    # Process the criteria met condition
                    # self.post_oi_alerts()

                    return oi_analysis_results

        except Exception as e:
            error_msg = f"Error getting OI data for {self.symbol}: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            return None

# def post_oi_alerts(self):
    #
    #     symbol = self.symbol
    #     interval = self.interval
    #     df_price_oi = self.df_price_oi
    #     df_oi = self.df_oi
    #
    #
    #     datetime_now = datetime.datetime.utcnow()
    #     datetime_now_str = datetime_now.strftime(DATETIME_FORMAT)
    #
    #
    #     # send signal to discord - OI alerts
    #     message_separator = '-------------------------------------\n'
    #     message_time = f'时间 {datetime_now_str}\n'
    #     message_name = f'标的 {symbol}\n'
    #     message_timescale = f'周期 {interval}\n'
    #     if arr_open_interest_change_pct < 40:
    #         message_oi_change = f'**涨幅 {arr_open_interest_change_pct}% (OI)**\n'
    #     else:
    #         # if greater than 40, add a green apple emoji to the front
    #         message_oi_change = f'**涨幅 🍏{arr_open_interest_change_pct}% (OI)**\n'
    #     message_combined = message_separator + message_time + message_name + message_timescale + message_oi_change
    #     webhook_discord_oi.post(content=message_combined)
    #
    #     if decision_entry_oi:
    #         message_combined_trading = message_separator + message_time + message_name + message_timescale + message_entry
    #         webhook_discord_oi_trading.post(content=message_combined_trading)
    #
    #     # if generate a plot, send the plot to the channel
    #     if generate_plot:
    #
    #         # check if plot already exists
    #         if flag_plot_exist:
    #             pass
    #         else:
    #             fig_pattern = generate_combined_chart(df_price_oi, df_oi, symbol, interval)
    #             fig_name = f'fig_pattern_{symbol}_{interval}.png'
    #             fig_pattern.write_image(fig_name)
    #
    #         # now send the plot
    #         webhook_discord_oi.post(
    #             file={
    #                 "file1": open(fig_name, "rb"),
    #             },
    #         )
    #
    #         if decision_entry_oi:
    #             webhook_discord_oi_trading.post(
    #                 file={
    #                     "file1": open(fig_name, "rb"),
    #                 },
    #             )
    #
    #         # reset plot status
    #         os.remove(fig_name)
    #         flag_plot_exist = False
    #


    """ This is the main function that will be called for each symbol."""
    def run(self):
        dict_results = {}
        self._get_price_data()
        self._calc_technical_indicators()

        # OI analysis
        self._get_oi_data()
        results_oi_analysis = self.run_oi_analysis()
        dict_results['oi_analysis'] = results_oi_analysis

        # PA analysis
        results_pa_analysis = self.run_pa_analysis()
        dict_results['pa_analysis'] = results_pa_analysis

        return dict_results



