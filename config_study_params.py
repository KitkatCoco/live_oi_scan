# Price preprocessing TA indicators
NUM_ATR_PERIODS = 50
NUM_VOL_MA_PERIODS = 200

# Simple Moving Average lengths
SMA_LENGTH_PRICE = 3
SMA_LENGTH_OI = 3

# Historical data retrieval settings
NUM_CANDLE_HIST_PRICE = 1000
NUM_CANDLE_HIST_OI_OTHER = 50
NUM_CANDLE_HIST_OI_1D = 29

# Search parameters for analysis
SEARCH_NUM_CANDLE_MIN = 2
SEARCH_NUM_CANDLE_MAX = 20
SEARCH_NUM_CANDLE_INC = 1

# Plot generation flag
GENERATE_PLOT = True

# Flags for different types of analysis
FLAG_ANALYSIS_OI = True
FLAG_ANALYSIS_PA = True

# PA parameters
RSI_OVERSOLD = 50
RSI_OVERBOUGHT = 50
PINBAR_BODY_ATR_THRES_MULTIPLIER = 0.5
# VOL_MA_THRES_MULTIPLIER = 1
POWAY_NUM_CANDLE_LOOKBACK = 20

# OI_RSI strategy parameters
list_oi_rsi_alert_intervals = ['5m', '15m', '30m', '1h', '2h', '4h', '12h']
