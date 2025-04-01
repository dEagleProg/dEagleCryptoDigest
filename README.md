# Crypto Monitoring Bot

A Telegram bot for monitoring cryptocurrency market indicators and sending daily notifications.

## Features

- Real-time cryptocurrency market data monitoring
- Top 10 cryptocurrencies by market capitalization
- Bitcoin price and 24h change tracking
- Market dominance and total market cap information
- Daily notifications at user-specified times (Madrid timezone)
- User-friendly inline keyboard interface
- Persistent notification settings

## Technical Stack

- Python 3.x
- aiogram (Telegram Bot API framework)
- aiohttp (Async HTTP client)
- pytz (Timezone handling)
- python-dotenv (Environment variables management)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/crypto-monitoring-bot.git
cd crypto-monitoring-bot
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with the following variables:
```
BOT_TOKEN=your_telegram_bot_token
COINGECKO_API_URL=https://api.coingecko.com/api/v3
```

## Usage

1. Start the bot:
```bash
python bot.py
```

2. In Telegram, start a chat with your bot and use the following commands:
- `/start` - Start the bot and show main menu
- `/check` - Get current market indicators
- `/settings` - Configure notification settings
- `/help` - Show help message

3. Set up notifications:
- Click "⚙️ Notification Settings" in the main menu
- Choose to enable/disable notifications
- Set your preferred notification time (Madrid timezone)

## Features in Detail

### Market Data
- Bitcoin price and 24-hour change
- Market dominance percentage
- Total market capitalization
- Top 10 cryptocurrencies with:
  - Current price
  - 24-hour price change
  - Market cap ranking

### Notifications
- Customizable notification time
- Madrid timezone (UTC+1) support
- Persistent settings across bot restarts
- One-time notification per minute to prevent spam

### User Interface
- Inline keyboard navigation
- Clear command structure
- Helpful error messages
- Timezone-aware time input

## Error Handling

The bot includes robust error handling for:
- API rate limits
- Network issues
- Invalid user input
- Timezone conversions
- Data fetching failures

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- CoinGecko API for providing cryptocurrency data
- aiogram team for the excellent Telegram bot framework
- All contributors who help improve this project 