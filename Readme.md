### Folder Structure
```
telegram_banking_bot/
├── bot.py                # Main bot handler file
├── database.py           # Database initialization and CRUD operations
├── .env                  # Configuration file for sensitive information like bot token
├── utils.py              # Utility functions (optional, such as logging setup)
├── requirements.txt      # Dependencies file
├── README.md             # Project description and setup instructions
└── banking_bot.db        # SQLite database (created after running the project)
```

## `bot.py` - Main Bot Handler File

```markdown
# Telegram Banking Bot

This project is a simple banking system Telegram bot that allows users to manage their accounts and transactions.

## Features
- Create a new user
- Check info
- Deposit money to an account (way of gaining balance using the bot)
- Donate to charity (way of lowering balance using the bot)
- Take a loan
- Pay the loans (in different ways)
- Transfers by phone number
- Transfers by account number

## Features to add
- Editing user's information (number, name, account number etc.)
- Splitting bot.py to different .py files for better readability!


## Setup
1. Clone the repository:
   ```
   git clone https://github.com/yourusername/telegram_banking_bot.git
   ```
2. Navigate to the project directory:
   ```
   cd telegram_banking_bot
   ```
3. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```
4. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```
5. Set up your bot token in `.env`.

6. Run the bot:
   ```
   python bot.py
   ```

## Usage
- `/start` - Start the bot and see available commands
***
```