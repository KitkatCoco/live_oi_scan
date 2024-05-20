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
    max_y, max_x = max_limits_oi_plot.get(interval, (100, 100))  # Default max limits

    # Clip values exceeding the maximum limits
    df_oi_analysis['max_price_drop_pct'] = df_oi_analysis['max_price_drop_pct'].clip(upper=max_y)
    df_oi_analysis['max_open_interest_change_pct'] = df_oi_analysis['max_open_interest_change_pct'].clip(upper=max_x)

    # get rid of the 'USDT' in the symbol
    df_oi_analysis['symbol'] = df_oi_analysis['symbol'].str.replace('USDT', '')

    # Creating the scatter plot
    fig = px.scatter(df_oi_analysis,
                     x='max_open_interest_change_pct',
                     y='max_price_drop_pct',
                     text='symbol',
                     labels={
                         "max_open_interest_change_pct": "OI change (%)",
                         "max_price_drop_pct": "Price change (%)",
                     },
                     title="")

    # Update traces and layout for detailed display
    fig.update_traces(textposition='bottom left', marker=dict(size=8), textfont=dict(size=14))
    fig.update_layout(
        xaxis=dict(
            title='OI change (%)',
            range=[0, max_x],
            showgrid=True,
            gridcolor='LightGray',
            title_font=dict(size=18),
            tickfont=dict(size=14)
        ),
        yaxis=dict(
            title='Price change (%)',
            range=[-max_y, max_y],
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
                                       'RSI', 'pin_ratio', and 'direction'.

    Returns:
        fig (plotly.graph_objects.Figure): The Plotly figure object.
    """
    # Constants for axes limits
    max_x = MAX_PINBAR_RATIO_ATR  # Max ratio of Pinbar length to ATR
    max_y = 100  # RSI ranges from 0 to 100

    # Removing 'USDT' from the symbol names
    df_pa_analysis['symbol'] = df_pa_analysis['symbol'].str.replace('USDT', '')

    # clip the pin_ratio values at the maximum limit
    df_pa_analysis['pin_ratio'] = df_pa_analysis['pin_ratio'].clip(upper=max_x)

    # Creating the scatter plot, using a size of 8 for the markers
    fig = px.scatter(df_pa_analysis,
                     x='pin_ratio',
                     y='RSI',
                     text='symbol',
                     labels={
                         "pin_ratio": "PA strength",
                         "RSI": "RSI",
                     },
                     title="")

    # Update traces and layout for detailed display
    fig.update_traces(textposition='bottom left', marker=dict(size=8), textfont=dict(size=14))
    fig.update_layout(
        xaxis=dict(
            title='PA strength',
            range=[0, max_x],
            showgrid=True,
            gridcolor='LightGray',
            title_font=dict(size=18),
            tickfont=dict(size=14)
        ),
        yaxis=dict(
            title='RSI',
            range=[0, max_y],
            showgrid=False,  # Disable horizontal grid lines
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

    # Add background colors for different y-axis ranges
    fig.add_shape(type="rect", x0=0, y0=0, x1=max_x, y1=20,
                  fillcolor="green", opacity=0.2, layer="below", line_width=0)
    fig.add_shape(type="rect", x0=0, y0=20, x1=max_x, y1=40,
                  fillcolor="lightgreen", opacity=0.2, layer="below", line_width=0)
    fig.add_shape(type="rect", x0=0, y0=40, x1=max_x, y1=60,
                  fillcolor="gray", opacity=0.2, layer="below", line_width=0)
    fig.add_shape(type="rect", x0=0, y0=60, x1=max_x, y1=80,
                  fillcolor="pink", opacity=0.2, layer="below", line_width=0)
    fig.add_shape(type="rect", x0=0, y0=80, x1=max_x, y1=100,
                  fillcolor="red", opacity=0.2, layer="below", line_width=0)

    return fig


def plot_rs_analysis(df_rs_analysis):
    """
    Plots a scatter chart of rsp vs. rsn for trading symbols, with a diagonal line indicating equal rsp and rsn,
    and ensuring the plot has an equal aspect ratio.

    Parameters:
        df_rs_analysis (pd.DataFrame): DataFrame containing the columns 'symbol', 'rsp', and 'rsn'.

    Returns:
        fig (plotly.graph_objects.Figure): The Plotly figure object.
    """

    # Removing 'USDT' from the symbol names
    df_rs_analysis['symbol'] = df_rs_analysis['symbol'].str.replace('USDT', '')

    # Clip the rsp and rsn values at ±2
    df_rs_analysis['rsp_clipped'] = df_rs_analysis['rsp'].clip(-2, 2)
    df_rs_analysis['rsn_clipped'] = df_rs_analysis['rsn'].clip(-2, 2)

    # Creating the scatter plot
    fig = go.Figure()

    # Add scatter trace for data points
    fig.add_trace(go.Scatter(
        x=df_rs_analysis['rsn_clipped'],
        y=df_rs_analysis['rsp_clipped'],
        mode='markers+text',
        text=df_rs_analysis['symbol'],
        textposition='top center',
        marker=dict(size=6),
    ))

    # Add diagonal line
    fig.add_trace(go.Scatter(
        x=[-2, 2], y=[-2, 2],
        mode='lines',
        line=dict(color='black', width=2)
    ))

    # Update layout for detailed display
    fig.update_layout(
        xaxis=dict(
            title='Relative Strength Negative',
            range=[-2, 2],  # slightly beyond ±2 for better visibility
            showgrid=True,
            gridcolor='LightGray',
            zeroline=True,
            zerolinewidth=2,
            zerolinecolor='Black',
            title_font=dict(size=16),
            tickfont=dict(size=12)
        ),
        yaxis=dict(
            title='Relative Strength Positive',
            range=[-2, 2],  # slightly beyond ±2 for better visibility
            showgrid=True,
            gridcolor='LightGray',
            zeroline=True,
            zerolinewidth=2,
            zerolinecolor='Black',
            title_font=dict(size=16),
            tickfont=dict(size=12),
            scaleanchor="x",
            scaleratio=1,
        ),
        plot_bgcolor='white',
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False,
        width=600,  # Square figure size: width = height
        height=600
    )

    return fig