MAX_PRICE_DROP_PCT_5M = 10
MAX_PRICE_DROP_PCT_15M = 10
MAX_PRICE_DROP_PCT_30M = 10
MAX_PRICE_DROP_PCT_1H = 20
MAX_PRICE_DROP_PCT_2H = 20
MAX_PRICE_DROP_PCT_4H = 20
MAX_PRICE_DROP_PCT_12H = 30

MAX_OI_INCREASE_PCT_5M = 25
MAX_OI_INCREASE_PCT_15M = 25
MAX_OI_INCREASE_PCT_30M = 25
MAX_OI_INCREASE_PCT_1H = 50
MAX_OI_INCREASE_PCT_2H = 50
MAX_OI_INCREASE_PCT_4H = 50
MAX_OI_INCREASE_PCT_12H = 75

MAX_PINBAR_RATIO_ATR = 4
MAX_RSI = 100

max_limits_oi_plot = {
    '5m': (MAX_PRICE_DROP_PCT_5M, MAX_OI_INCREASE_PCT_5M),
    '15m': (MAX_PRICE_DROP_PCT_15M, MAX_OI_INCREASE_PCT_15M),
    '30m': (MAX_PRICE_DROP_PCT_30M, MAX_OI_INCREASE_PCT_30M),
    '1h': (MAX_PRICE_DROP_PCT_1H, MAX_OI_INCREASE_PCT_1H),
    '2h': (MAX_PRICE_DROP_PCT_2H, MAX_OI_INCREASE_PCT_2H),
    '4h': (MAX_PRICE_DROP_PCT_4H, MAX_OI_INCREASE_PCT_4H),
    '12h': (MAX_PRICE_DROP_PCT_12H, MAX_OI_INCREASE_PCT_12H),
}

# plot for the RS analysis
X_MIN_RS_PLOT = -0.5
X_MAX_RS_PLOT = 3
Y_MIN_RS_PLOT = X_MIN_RS_PLOT
Y_MAX_RS_PLOT = X_MAX_RS_PLOT