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
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pickle

from config_plots import *
from config_formatting import *
from config_study_params import *

def generate_combined_chart(df_price, df_oi, symbol, interval, use_sma=True):

    # Create a 2x1 subplot
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=("Candlestick Price Data", "Open Interest", "Funding Rate"))

    # Add Candlestick plot
    fig.add_trace(
        go.Candlestick(x=df_price['Time'],
                       open=df_price['Open'],
                       high=df_price['High'],
                       low=df_price['Low'],
                       close=df_price['Close'],
                       name='Price'),
        row=1, col=1
    )

    # Add SMA plot, if it exists
    if use_sma:
        fig.add_trace(
            go.Scatter(x=df_price['Time'],
                       y=df_price['SMA'],
                       mode='lines',
                       name='SMA'),
            row=1, col=1
        )

    # Add open interest plot - as light green bars
    fig.add_trace(
        go.Bar(x=df_oi['timestamp'],
               y=df_oi['sumOpenInterest'],
               name='Open Interest',
               marker=dict(color='lightgreen')),
        row=2, col=1
    )

    # Add SMA plot, if it exists
    if use_sma:
        fig.add_trace(
            go.Scatter(x=df_oi['timestamp'],
                       y=df_oi['SMA'],
                       mode='lines',
                       name='SMA'),
            row=2, col=1
        )

    # set the y limit to [0, df_oi['sumOpenInterest'].max()]),
    fig.update_yaxes(range=[df_oi['sumOpenInterest'].min()*0.95, df_oi['sumOpenInterest'].max()], row=2, col=1)

    # Update layout to make the plot wider and remove the range slider from the OHLC plot
    fig.update_layout(height=600, width=1000,
                      title_text=f"{symbol} {interval}",
                      template="plotly_dark"
                      )

    # get rid of the range slider
    fig['layout']['xaxis']['rangeslider_visible'] = False  # Disable the range slider for the Candlestick plot

    # Move the legend to the top of the plot
    fig.update_layout(legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    ))

    # Increase font sizes for the title as well as the chart title
    fig.update_layout(font=dict(size=22))

    # remove legends
    fig.update_layout(showlegend=False)

    return fig

def plot_oi_analysis(df_oi_analysis, interval):
    """
    Plots a detailed scatter chart of Open Interest Change vs. Price Drop for trading symbols,
    with grid lines and enhanced font sizes for improved readability.

    Parameters:
        df_oi_analysis (pd.DataFrame): DataFrame containing the columns 'symbol',
                                       'max_open_interest_change_pct', and 'max_price_drop_pct'.

    Returns:
        fig (plotly.graph_objects.Figure): The Plotly figure object.
    """
    # Constants for axes limits
    max_limits = {
        '15m': (MAX_PRICE_DROP_PCT_15M, MAX_OI_INCREASE_PCT_15M),
        '1h': (MAX_PRICE_DROP_PCT_1H, MAX_OI_INCREASE_PCT_1H),
        '4h': (MAX_PRICE_DROP_PCT_4H, MAX_OI_INCREASE_PCT_4H),
        '12h': (MAX_PRICE_DROP_PCT_12H, MAX_OI_INCREASE_PCT_12H),
    }
    max_x, max_y = max_limits.get(interval, (100, 100))  # Default max limits

    # Clip values exceeding the maximum limits
    df_oi_analysis['max_price_drop_pct'] = df_oi_analysis['max_price_drop_pct'].clip(upper=max_x)
    df_oi_analysis['max_open_interest_change_pct'] = df_oi_analysis['max_open_interest_change_pct'].clip(upper=max_y)

    # get rid of the 'USDT' in the symbol
    df_oi_analysis['symbol'] = df_oi_analysis['symbol'].str.replace('USDT', '')

    # Creating the scatter plot
    fig = px.scatter(df_oi_analysis,
                     x='max_price_drop_pct',
                     y='max_open_interest_change_pct',
                     text='symbol',
                     labels={
                         "max_price_drop_pct": "Max Price Drop (%)",
                         "max_open_interest_change_pct": "Max Open Interest Change (%)"
                     },
                     title="")

    # Update traces and layout for detailed display
    fig.update_traces(textposition='bottom left', marker=dict(size=8), textfont=dict(size=14))
    fig.update_layout(
        xaxis=dict(
            title='Max Price Drop (%)',
            range=[0, max_x],
            showgrid=True,
            gridcolor='LightGray',
            title_font=dict(size=18),
            tickfont=dict(size=14)
        ),
        yaxis=dict(
            title='Max Open Interest Change (%)',
            range=[0, max_y],
            showgrid=True,
            gridcolor='LightGray',
            title_font=dict(size=18),
            tickfont=dict(size=14)
        ),
        margin=dict(l=10, r=10, t=20, b=20),
        showlegend=False
    )

    return fig


def plot_pa_analysis(df_pa_analysis, interval):
    """
    Plots a scatter chart of RSI vs. Pin Length Ratio for trading symbols,
    colored by trading direction (Long in green, Short or others in red),
    and includes horizontal lines for RSI oversold and overbought thresholds.

    Parameters:
        df_pa_analysis (pd.DataFrame): DataFrame containing the columns 'symbol',
                                       'RSI', 'pin_length_ratio', and 'direction'.

    Returns:
        fig (plotly.graph_objects.Figure): The Plotly figure object.
    """
    # Constants for axes limits
    max_x = MAX_PINBAR_RATIO_ATR  # Max ratio of Pinbar length to ATR
    max_y = 100  # RSI ranges from 0 to 100

    # Removing 'USDT' from the symbol names
    df_pa_analysis['symbol'] = df_pa_analysis['symbol'].str.replace('USDT', '')

    # Mapping colors based on the 'direction' column
    color_map = {'Long': 'green', 'Short': 'red'}
    df_pa_analysis['color'] = df_pa_analysis['direction'].map(color_map).fillna('red')  # Default to red if not Long or Short

    # Creating the scatter plot
    fig = px.scatter(df_pa_analysis,
                     x='pin_ratio',
                     y='RSI',
                     text='symbol',
                     color='color',
                     labels={
                         "pin_length_ratio": "Pin Length Ratio",
                         "RSI": "RSI"
                     },
                     title="")

    # Update traces and layout for detailed display
    fig.update_traces(textposition='bottom left', marker=dict(size=8), textfont=dict(size=14))
    fig.update_layout(
        xaxis=dict(
            title='Pinbar length',
            range=[PINBAR_BODY_ATR_THRES_MULTIPLIER - 0.1, max_x],
            showgrid=True,
            gridcolor='LightGray',
            title_font=dict(size=18),
            tickfont=dict(size=14)
        ),
        yaxis=dict(
            title='RSI',
            range=[0, max_y],
            showgrid=True,
            gridcolor='LightGray',
            title_font=dict(size=18),
            tickfont=dict(size=14)
        ),
        margin=dict(l=10, r=10, t=20, b=20),
        showlegend=False,
        coloraxis_showscale=False  # Hides the color scale legend
    )

    # Add horizontal lines for RSI oversold and overbought levels
    fig.add_hline(y=RSI_OVERSOLD, line_dash="dash", line_color="gray")
    fig.add_hline(y=RSI_OVERBOUGHT, line_dash="dash", line_color="gray")

    return fig