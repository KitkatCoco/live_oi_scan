""" This function performs live scan of price and Open interest (coin-native) to search price/OI divergence """


from config_constants import *
from config_study_params import *
from utils import *


if __name__ == '__main__':



    # update the num_candle_hist if the interval is 1d
    if interval == '1d':
        num_candle_hist_oi = 29
        use_SMA = False

    # set up thresholds
    threshold_price_change_pct_negative = dict_threshold_price_change_pct_negative[interval]
    threshold_oi_change_pct_positive = dict_threshold_oi_change_pct_positive[interval]




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



            # OI data
            # select the last num_candle_hist_price_oi from price_data for matching the length of oi_data


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
                if lower_pinbar_cur > pinbar_body_ATR_thres_multiplier * ATR_cur and \
                    cur_price_close > cur_price_open:
                    is_bullish_pinbar = True
                    msg_pinbar = '看涨针线'
                if upper_pinbar_cur > pinbar_body_ATR_thres_multiplier * ATR_cur and \
                    cur_price_close < cur_price_open:
                    is_bearish_pinbar = True
                    msg_pinbar = '看跌针线'

                # check if the last candle's low is the lowest in all last num_candle_hist_oi candles
                # num_candle_hl_check = min(20, len(df_price))
                # if cur_price_low == df_price['Low'].iloc[-20:].min():
                #     is_lowest_low = True
                #     msg_high_low = '价格新低'
                # if cur_price_high == df_price['High'].iloc[-20:].max():
                #     is_highest_high = True
                #     msg_high_low = '价格新高'

                # send signal to discord - PA alerts
                # if is_rsi_oversold or is_rsi_overbought or is_bullish_pinbar or is_bearish_pinbar or is_lowest_low:
                if is_rsi_oversold or is_rsi_overbought or is_bullish_pinbar or is_bearish_pinbar:
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

                short_range_end = search_num_candle_min + (search_num_candle_max - search_num_candle_min) // 3
                mid_range_end = search_num_candle_min + 2 * (search_num_candle_max - search_num_candle_min) // 3

                # for gradual condition check
                threshold_price_change_pct_negative_short_term = threshold_price_change_pct_negative / 3
                threshold_price_change_pct_negative_mid_term = threshold_price_change_pct_negative * 2 / 3
                threshold_oi_change_pct_positive_short_term = threshold_oi_change_pct_positive / 3
                threshold_oi_change_pct_positive_mid_term = threshold_oi_change_pct_positive * 2 / 3


                for i in range(search_num_candle_min, search_num_candle_max, search_num_candle_inc):

                    try:
                        arr_price_change_pct = (df_price_oi['SMA'].iloc[-1] - df_price_oi['SMA'].iloc[-i]) /df_price_oi['SMA'].iloc[-i]
                        arr_price_change_pct = arr_price_change_pct * 100
                        arr_price_change_pct = round(arr_price_change_pct, 2)

                        arr_open_interest_change_pct = (df_oi['SMA'].iloc[-1] - df_oi['SMA'].iloc[-i]) /df_oi['SMA'].iloc[-i]
                        arr_open_interest_change_pct = arr_open_interest_change_pct * 100
                        arr_open_interest_change_pct = round(arr_open_interest_change_pct, 2)

                        # compare if the change of price and OI meet the requirement
                        if i <= short_range_end:
                            if (arr_price_change_pct < threshold_price_change_pct_negative_short_term and
                                    arr_open_interest_change_pct > threshold_oi_change_pct_positive_short_term):
                                valid_lengths.append(i)
                        elif i > short_range_end and i <= mid_range_end:
                            if (arr_price_change_pct < threshold_price_change_pct_negative_mid_term and
                                    arr_open_interest_change_pct > threshold_oi_change_pct_positive_mid_term):
                                valid_lengths.append(i)
                        else:
                            if (arr_price_change_pct < threshold_price_change_pct_negative and
                                    arr_open_interest_change_pct > threshold_oi_change_pct_positive):
                                valid_lengths.append(i)

                    except:
                        continue

                if len(valid_lengths) > 3:
                    oi_criteria_short_range = False
                    oi_criteria_mid_range = False
                    oi_criteria_long_range = False

                    # check if any element in valid_lengths is within the range of 3 and 10
                    if any(search_num_candle_min <= x <= short_range_end - 1 for x in valid_lengths):
                        oi_criteria_short_range = True
                    if any(short_range_end <= x <= mid_range_end - 1 for x in valid_lengths):
                        oi_criteria_mid_range = True
                    if any(mid_range_end <= x <= search_num_candle_max for x in valid_lengths):
                        oi_criteria_long_range = True
                    oi_criteria_all = oi_criteria_short_range and oi_criteria_mid_range and oi_criteria_long_range

                    if not oi_criteria_all:
                        # print(f'OI criteria not met for {symbol} at {datetime_now_str}')
                        continue

                    # calculate the min and max value in the last N=search_num_candle_max candles of df_oi
                    oi_min = df_oi['sumOpenInterest'].iloc[-search_num_candle_max:].min()
                    oi_max = df_oi['sumOpenInterest'].iloc[-search_num_candle_max:].max()
                    oi_diff_pct = (oi_max - oi_min) / oi_min * 100

                    # check for entry signal - long case only
                    decision_entry_oi = False
                    # if RSI_cur <= RSI_oversold and \
                    #         lower_pinbar_cur > pinbar_body_ATR_thres_multiplier * ATR_cur and \
                    #         Vol_cur > Vol_MA_thres_multiplier * Vol_MA_cur:
                    if is_rsi_oversold:
                        message_entry = f'**信号 RSI超卖**\n'
                        decision_entry_oi = True
                    if is_bullish_pinbar:
                        message_entry = f'**信号 看涨针线**\n'
                        decision_entry_oi = True
                    if is_rsi_oversold and is_bullish_pinbar:
                        message_entry = f'**信号 RSI超卖 + 看涨针线**\n'
                        decision_entry_oi = True


                    # send signal to discord - OI alerts
                    message_separator = '-------------------------------------\n'
                    message_time = f'时间 {datetime_now_str}\n'
                    message_name = f'标的 {symbol}\n'
                    message_timescale = f'周期 {interval}\n'
                    if arr_open_interest_change_pct < 40:
                        message_oi_change = f'**涨幅 {arr_open_interest_change_pct}% (OI)**\n'
                    else:
                        # if greater than 40, add a green apple emoji to the front
                        message_oi_change = f'**涨幅 🍏{arr_open_interest_change_pct}% (OI)**\n'
                    message_combined = message_separator + message_time + message_name + message_timescale + message_oi_change
                    webhook_discord_oi.post(content=message_combined)

                    if decision_entry_oi:
                        message_combined_trading = message_separator + message_time + message_name + message_timescale + message_entry
                        webhook_discord_oi_trading.post(content=message_combined_trading)

                    # if generate a plot, send the plot to the channel
                    if generate_plot:

                        # check if plot already exists
                        if flag_plot_exist:                            pass
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



