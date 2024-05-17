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
from plotly.subplots import make_subplots
import pickle

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
