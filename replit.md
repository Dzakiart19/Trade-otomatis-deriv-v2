# Deriv Auto Trading Bot

## Overview
This project is an automated trading bot for the Deriv Binary Options platform, utilizing a multi-indicator strategy (RSI, EMA, MACD, Stochastic) and an Adaptive Martingale system. Built with Python, it connects to the Deriv API via WebSockets for real-time data and trade execution. The bot aims to automate trading decisions, manage risk, and provide real-time monitoring and analytics for various volatility indices and forex pairs, supporting both short-term and long-term strategies. It offers a web dashboard, Telegram integration for control and notifications, and supports multiple trading strategies.

## User Preferences
I prefer detailed explanations.
Do not make changes to the folder `Z`.
Do not make changes to the file `Y`.

## System Architecture

### UI/UX Decisions
The system features real-time monitoring with instant Telegram notifications, CSV logging for trades, and detailed error logs. A web dashboard, redesigned for minimalism and responsiveness (mobile-first), uses a neutral color palette with a blue accent, Inter typography, and an 8px grid system. It incorporates rounded corners, soft shadows, and reusable components. Dynamic strategy panels provide unique UI elements for each of the seven trading strategies (Multi-Indicator, LDP, Tick Analyzer, Terminal, DigitPad, AMT, Sniper), with real-time updates via WebSocket integration.

### Technical Implementations
The bot implements multiple trading strategies, including a **Multi-Indicator Strategy** with confluence scoring and advanced filters (Multi-Timeframe Trend Confirmation, EMA Slope, ADX, Volume, Price Action, Signal Cooldown). Other strategies include **LDP Analyzer**, **Tick Picker**, **Terminal** (Smart Analysis 80%), **DigitPad**, **AMT (Accumulator)**, and **Sniper**. New strategies like **Trend Following**, **Bollinger Bands Breakout**, and **Support & Resistance** have been introduced, each with dynamic stake calculation.

An **Adaptive Martingale System** dynamically adjusts multipliers based on the rolling win rate and has a maximum of 5 levels. **Risk Management** includes max session loss (20%), max consecutive losses (5x), daily loss limit ($50 USD for real accounts), balance checks, and auto-adjusting stake. **Session Analytics** track key performance indicators.

Key features also include **Instant Data Preload** from the Deriv API, robust **Error Handling & Stability** with WebSocket reconnection and graceful shutdown, and **Multi-Account Support** (Demo/Real). **Per-User Token Authentication** encrypts and stores tokens securely, with **Telegram WebApp Dashboard Integration** providing auto-authentication and HMAC-SHA256 validation. **Martingale Recovery Priority** ensures stake preservation during recovery sequences, and **User Stake Priority** allows direct user control over stake amounts without automatic caps. The **Tick Direction Predictor** uses a multi-factor weighted analysis for predicting future tick movements. Stability and performance improvements include WebSocket memory leak fixes, thread safety, and efficient indicator calculations.

**Real-time Strategy Panel Updates**: The dashboard now receives instant SignalEvent broadcasts when strategies are switched via Telegram, even when trading is inactive. The `_broadcast_strategy_change()` method in trading.py publishes STRATEGY_CHANGE events with strategy-specific data (ldp_data, terminal_data, digitpad_data, amt_data, sniper_data, multi_indicator_data) so panels update immediately.

### Feature Specifications
The bot supports **Volatility indices** (R_100, R_75, R_50, R_25, R_10, 1HZ100V, 1HZ75V, 1HZ50V) for 5-10 tick durations and **frxXAUUSD** (Gold/USD) for daily durations. **Telegram Integration** provides interactive commands for control and status. **Session Management** includes configurable target trades and auto-stop. The **Multi-Strategy System** allows selection from:
1.  **Multi-Indicator Strategy** (Default)
2.  **Trend Following Strategy**
3.  **Bollinger Bands Breakout Strategy**
4.  **Support & Resistance Strategy**

### System Design Choices
The project utilizes a modular **file structure** for maintainability. **Logging** is comprehensive, with dedicated directories for trade journals, analytics, and error logs. **Security** is maintained through encrypted environment variables (Replit Secrets) for API and bot tokens, and WSS for WebSocket communication. The bot employs an asynchronous **startup** pattern, avoiding the need for a Flask keep-alive server.

## External Dependencies
-   `python-telegram-bot`: For Telegram API interaction.
-   `websocket-client`: For WebSocket communication with the Deriv API.
-   `python-dotenv`: For managing environment variables (though Replit Secrets are primary).
-   `cryptography`: For secure encryption of user tokens.