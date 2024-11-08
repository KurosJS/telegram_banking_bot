import sqlite3
import logging

# Initialize the database and create required tables with constraints
def initialize_database():
    connection = sqlite3.connect('banking_bot.db')
    cursor = connection.cursor()

    # Create Users Table with a unique email constraint
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL
        )
    ''')

    # Create Accounts Table with a positive balance constraint
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userId INTEGER NOT NULL,
            accountNumber TEXT UNIQUE NOT NULL,
            accountType TEXT NOT NULL,
            balance REAL CHECK (balance >= 0),
            FOREIGN KEY (userId) REFERENCES users(id)
        )
    ''')

    # Create Transactions Table with the correct accountId field
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            accountId INTEGER NOT NULL,
            transactionDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            amount REAL NOT NULL,
            transactionType TEXT NOT NULL,
            FOREIGN KEY (accountId) REFERENCES accounts(id)
        )
    ''')

    # Create Loans Table to manage loan details
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userId INTEGER NOT NULL,
            loanAmount REAL NOT NULL CHECK (loanAmount > 0),
            durationMonths INTEGER NOT NULL CHECK (durationMonths IN (3, 6, 12)),
            monthlyPayment REAL NOT NULL CHECK (monthlyPayment > 0),
            remainingBalance REAL NOT NULL CHECK (remainingBalance >= 0),
            FOREIGN KEY (userId) REFERENCES users(id)
        )
    ''')

    # Create Trigger to automatically update account balance after a transaction
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS update_balance_after_transaction
        AFTER INSERT ON transactions
        BEGIN
            UPDATE accounts
            SET balance = balance + NEW.amount
            WHERE id = NEW.accountId;
        END;
    ''')

    connection.commit()
    connection.close()


# CRUD Operations with error handling
def create_user(name, email, phone):
    connection = sqlite3.connect('banking_bot.db')
    cursor = connection.cursor()
    try:
        cursor.execute('INSERT INTO users (name, email, phone) VALUES (?, ?, ?)', (name, email, phone))
        connection.commit()
        logging.info(f'User {name} created successfully.')
    except sqlite3.IntegrityError as e:
        logging.error(f'Failed to create user: Integrity error (possibly a duplicate email): {e}')
    except sqlite3.Error as e:
        logging.error(f'Failed to create user: {e}')
    finally:
        connection.close()

def get_account_balance(account_id):
    connection = sqlite3.connect('banking_bot.db')
    cursor = connection.cursor()
    try:
        cursor.execute('SELECT balance FROM accounts WHERE id = ?', (account_id,))
        balance = cursor.fetchone()
        return balance[0] if balance else None
    except sqlite3.Error as e:
        logging.error(f'Error fetching account balance: {e}')
        return None
    finally:
        connection.close()

def update_account_balance(account_id, amount):
    connection = sqlite3.connect('banking_bot.db')
    cursor = connection.cursor()
    try:
        # Check if the balance will remain non-negative after the update
        cursor.execute('SELECT balance FROM accounts WHERE id = ?', (account_id,))
        balance = cursor.fetchone()
        if balance and (balance[0] + amount) < 0:
            raise ValueError("Insufficient funds for this transaction.")

        cursor.execute('UPDATE accounts SET balance = balance + ? WHERE id = ?', (amount, account_id))
        connection.commit()
        logging.info(f'Account {account_id} balance updated successfully.')
    except ValueError as e:
        logging.error(f'Balance update failed: {e}')
    except sqlite3.Error as e:
        logging.error(f'Failed to update account balance: {e}')
    finally:
        connection.close()

# Initialize the database
initialize_database()