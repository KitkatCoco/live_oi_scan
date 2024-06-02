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
    df_oi_analysis['symbol'] = df_oi_analysis['symbol'].str.replace('USDT', '').str.replace('1000', '')

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

import plotly.express as px
import pandas as pd

def plot_pa_analysis(df_pa_analysis, interval):
    # Constants for axes limits
    max_x, max_y = max_limits_pa_plot.get(interval, (10, 30))  # Default max limits

    # Removing 'USDT' from the symbol names and other text processing
    df_pa_analysis['symbol'] = df_pa_analysis['symbol'].str.replace('USDT', '').str.replace('1000', '')

    # Define marker symbols based on is_pinbar
    df_pa_analysis['marker_symbol'] = df_pa_analysis['is_pinbar'].map({True: 'square', False: 'circle'})

    # Define colors based on RSI values
    df_pa_analysis['color'] = pd.cut(df_pa_analysis['RSI'], bins=[0, 20, 40, 60, 80, 100],
                                     labels=['green', 'lightgreen', 'gray', 'orange', 'red']).astype('object')

    # Override color and symbol for low relative volume entries
    df_pa_analysis.loc[df_pa_analysis['rel_vol'] < 2, 'color'] = 'gray'
    df_pa_analysis.loc[df_pa_analysis['rel_vol'] < 2, 'marker_symbol'] = 'circle'

    # Scale marker sizes, ensuring visibility
    df_pa_analysis['scaled_pin_ratio'] = df_pa_analysis['pin_ratio'].clip(lower=1) * 10
    df_pa_analysis['marker_size'] = df_pa_analysis['scaled_pin_ratio']
    df_pa_analysis.loc[df_pa_analysis['rel_vol'] < 0.8 * max_x, 'marker_size'] = 5  # Smaller size for low rel_vol
    df_pa_analysis.loc[df_pa_analysis['rel_vol'] < 0.6 * max_x, 'marker_size'] = 4  # Smaller size for low rel_vol
    df_pa_analysis.loc[df_pa_analysis['rel_vol'] < 0.4 * max_x, 'marker_size'] = 3  # Smaller size for low rel_vol
    df_pa_analysis.loc[df_pa_analysis['rel_vol'] < 0.2 * max_x, 'marker_size'] = 2  # Smaller size for low rel_vol

    # clip the values at the max limits
    df_pa_analysis['rel_vol'] = df_pa_analysis['rel_vol'].clip(upper=max_x)
    df_pa_analysis['price_change_pct'] = df_pa_analysis['price_change_pct'].clip(upper=max_y, lower=-max_y)

    # Creating the scatter plot with explicit color mapping
    color_map = {'green': '#00FF00', 'lightgreen': '#90EE90', 'gray': '#808080', 'orange': '#FFA500', 'red': '#FF0000'}
    fig = px.scatter(df_pa_analysis,
                     x='rel_vol',
                     y='price_change_pct',
                     text='symbol',
                     labels={
                         "rel_vol": "Relative Volume",
                         "price_change_pct": "Price Change (%)"
                     },
                     title="Price Analysis",
                     color='color',
                     symbol='marker_symbol',
                     size='marker_size',
                     size_max=12,
                     color_discrete_map=color_map)  # Explicit color mapping

    # Update traces and layout for detailed display
    fig.update_traces(textposition='top center')
    fig.update_layout(
        xaxis=dict(
            title='Relative Volume',
            range=[0, max_x],
            showgrid=True,
            gridcolor='LightGray',
            title_font=dict(size=18),
            tickfont=dict(size=14)
        ),
        yaxis=dict(
            title='Price Change (%)',
            range=[-max_y, max_y],
            showgrid=True,
            title_font=dict(size=18),
            tickfont=dict(size=14)
        ),
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=False,
        coloraxis_showscale=True  # Shows the color scale legend
    )

    # # Add background colors for different x-axis ranges
    # fig.add_shape(type="rect", x0=0, y0=-0.5*max_y, x1=0.2 * max_x, y1=0.5*max_y,
    #               fillcolor="green", opacity=0.2, layer="below", line_width=0)
    # fig.add_shape(type="rect", x0=0.2 * max_x, y0=-0.5*max_y, x1=0.4 * max_x, y1=0.5*max_y,
    #               fillcolor="lightgreen", opacity=0.2, layer="below", line_width=0)
    # fig.add_shape(type="rect", x0=0.4 * max_x, y0=-0.5*max_y, x1=0.6 * max_x, y1=0.5*max_y,
    #               fillcolor="yellow", opacity=0.2, layer="below", line_width=0)
    # fig.add_shape(type="rect", x0=0.6 * max_x, y0=-0.5*max_y, x1=0.8 * max_x, y1=0.5*max_y,
    #               fillcolor="orange", opacity=0.2, layer="below", line_width=0)
    # fig.add_shape(type="rect", x0=0.8 * max_x, y0=-0.5*max_y, x1=max_x, y1=0.5*max_y,
    #               fillcolor="red", opacity=0.2, layer="below", line_width=0)

    # fig.show()

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
    df_rs_analysis['rsp_clipped'] = df_rs_analysis['rsp'].clip(Y_MIN_RS_PLOT, Y_MAX_RS_PLOT)
    df_rs_analysis['rsn_clipped'] = df_rs_analysis['rsn'].clip(Y_MIN_RS_PLOT, Y_MAX_RS_PLOT)

    # Creating the scatter plot
    fig = go.Figure()

    # Add scatter trace for data points, add font size
    fig.add_trace(go.Scatter(
        x=df_rs_analysis['rsn_clipped'],
        y=df_rs_analysis['rsp_clipped'],
        mode='markers+text',
        text=df_rs_analysis['symbol'],
        textposition='top center',
        marker=dict(size=4),
        textfont=dict(size=12)
    ))

    # Add diagonal line
    fig.add_trace(go.Scatter(
        x=[X_MIN_RS_PLOT, X_MAX_RS_PLOT], y=[Y_MIN_RS_PLOT, Y_MAX_RS_PLOT],
        mode='lines',
        line=dict(color='black', width=1)
    ))

    # Update layout for detailed display
    fig.update_layout(
        xaxis=dict(
            title='Relative Strength Negative',
            range=[Y_MIN_RS_PLOT, Y_MAX_RS_PLOT],  # slightly beyond ±2 for better visibility
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
            range=[Y_MIN_RS_PLOT, Y_MAX_RS_PLOT],  # slightly beyond ±2 for better visibility
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
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        width=500,  # Square figure size: width = height
        height=500,
    )

    return fig