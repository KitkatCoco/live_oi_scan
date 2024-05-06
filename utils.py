import requests
import pandas as pd
import time
import os
import datetime
import argparse
from discordwebhook import Discord

import plotly.graph_objects as go
from plotly.subplots import make_subplots

def generate_combined_chart(df_price, df_oi, symbol, interval):

    # Create a 3x1 subplot
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

    # Add SMA plot
    fig.add_trace(
        go.Scatter(x=df_price['Time'],
                   y=df_price['SMA'],
                   mode='lines',
                   name='SMA'),
        row=1, col=1
    )

    # Add open interest plot - as bars
    fig.add_trace(
        go.Bar(x=df_oi['timestamp'],
               y=df_oi['sumOpenInterest'],
               name='Open Interest'),
        row=2, col=1
    )

    # Add SMA plot
    fig.add_trace(
        go.Scatter(x=df_oi['timestamp'],
                   y=df_oi['SMA'],
                   mode='lines',
                   name='SMA'),
        row=2, col=1
    )

    # set the y limit to [0, df_oi['sumOpenInterest'].max()]),
    fig.update_yaxes(range=[df_oi['sumOpenInterest'].min()*0.8, df_oi['sumOpenInterest'].max()], row=2, col=1)

    # # Add funding rate
    # fig.add_trace(
    #     go.Scatter(x=[df_price['Time'].iloc[0],
    #                   df_price['Time'].iloc[-1]],
    #                y=[0, 0],
    #                mode='lines',
    #                name='Funding Rate'),
    #     row=3, col=1
    # )

    # Update layout to make the plot wider and remove the range slider from the OHLC plot
    fig.update_layout(height=900, width=1200,
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

    # remove legends
    fig.update_layout(showlegend=False)

    return fig
