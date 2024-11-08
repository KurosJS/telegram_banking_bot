import logging
import sqlite3
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env

# Initialize the bot and dispatcher
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())

# Logger configuration
logging.basicConfig(level=logging.INFO)

# Connect to SQLite database
def get_db_connection():
    return sqlite3.connect('banking_bot.db')

# Register router
router = Router()

# limit for loans
LOAN_LIMIT = 45000

# state classes
class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_email = State()
    waiting_for_phone = State()

class Transaction(StatesGroup):
    waiting_for_transaction_type = State()
    waiting_for_amount = State()

class Transfer(StatesGroup):
    waiting_for_recipient_phone = State()
    waiting_for_transfer_amount = State()

class Loan(StatesGroup):
    waiting_for_amount = State()
    waiting_for_duration = State()
    confirming_loan = State()

@router.message(F.text == '💸 Take a Loan')
async def initiate_loan(message: Message, state: FSMContext):
    await message.answer("Enter the loan amount:")
    await state.set_state(Loan.waiting_for_amount)

@router.message(Loan.waiting_for_amount)
async def process_loan_amount(message: Message, state: FSMContext):
    amount_text = message.text
    if not is_positive_amount(amount_text):
        await message.answer("❌ Invalid amount. Please enter a positive number.")
        return

    amount = float(amount_text)
    if amount > 45000:
        await message.answer("❌ Loan amount exceeds the individual limit of 45,000 units.")
        return

    # Check the user's total loan balance
    telegram_id = message.from_user.id
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute('SELECT SUM(remainingBalance) FROM loans WHERE userId = ?', (telegram_id,))
    total_outstanding = cursor.fetchone()[0] or 0

    if total_outstanding + amount > 50000:
        await message.answer("❌ Total loan balance cannot exceed 50,000 units.")
        connection.close()
        return

    await state.update_data(loan_amount=amount)
    await message.answer("Select loan duration (3, 6, or 12 months):")
    await state.set_state(Loan.waiting_for_duration)
    connection.close()

@router.message(Loan.waiting_for_duration)
async def process_loan_duration(message: Message, state: FSMContext):
    duration_text = message.text
    if duration_text not in ['3', '6', '12']:
        await message.answer("❌ Invalid duration. Please choose 3, 6, or 12 months.")
        return

    duration = int(duration_text)
    loan_data = await state.get_data()
    loan_amount = loan_data['loan_amount']
    interest_rate = 0.23  # 23% per year

    # Calculate total amount to repay and monthly payment
    total_repayment = loan_amount * (1 + interest_rate * (duration / 12))
    monthly_payment = total_repayment / duration

    await state.update_data(loan_duration=duration, monthly_payment=monthly_payment, total_repayment=total_repayment)
    await message.answer(
        f"Loan Amount: {loan_amount}\nDuration: {duration} months\n"
        f"Monthly Payment: {monthly_payment:.2f}\nTotal Repayment: {total_repayment:.2f}\n\n"
        "Confirm loan? (Yes/No)"
    )
    await state.set_state(Loan.confirming_loan)

@router.message(Loan.confirming_loan)
async def confirm_loan(message: Message, state: FSMContext):
    if message.text.lower() != 'yes':
        await message.answer("Loan request canceled.")
        await state.clear()
        return

    loan_data = await state.get_data()
    loan_amount = loan_data['loan_amount']
    monthly_payment = loan_data['monthly_payment']
    duration = loan_data['loan_duration']
    telegram_id = message.from_user.id

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Update the user's account balance
        cursor.execute('UPDATE accounts SET balance = balance + ? WHERE userId = ?', (loan_amount, telegram_id))
        
        # Record the loan details
        cursor.execute(
            'INSERT INTO transactions (accountId, amount, transactionType) VALUES (?, ?, ?)',
            (telegram_id, loan_amount, 'Loan')
        )
        
        # Record the loan repayment schedule
        cursor.execute(
            'INSERT INTO loans (userId, loanAmount, durationMonths, monthlyPayment, remainingBalance) VALUES (?, ?, ?, ?, ?)',
            (telegram_id, loan_amount, duration, monthly_payment, loan_amount)
        )

        connection.commit()
        await message.answer(f"Loan confirmed. You have received {loan_amount} units. Monthly payment: {monthly_payment:.2f} units.")
    except sqlite3.Error as e:
        await message.answer(f"❌ Loan confirmation failed: {e}")
    finally:
        connection.close()

    await state.clear()

# Input validation functions
def is_valid_name(name):
    return len(name.strip()) > 0

def is_valid_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email) is not None

def is_valid_phone(phone):
    return phone.isdigit() and 10 <= len(phone) <= 15

def is_positive_amount(amount):
    try:
        return float(amount) > 0
    except ValueError:
        return False

# Check if a user is already registered
def is_user_registered(telegram_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (telegram_id,))
    user = cursor.fetchone()
    connection.close()
    return user

# /start command handler
@router.message(Command(commands=['start']))
async def start_bot(message: Message):
    greeting_text = "👋 Hello! Welcome to the Banking Bot. Use the buttons below to proceed."
    telegram_id = message.from_user.id
    if is_user_registered(telegram_id):
        reply_keyboard = [
            [KeyboardButton(text='ℹ️ My Info')],
            [KeyboardButton(text='💸 Take a Loan'), KeyboardButton(text='🎁 Donate to Charity')],
            [KeyboardButton(text='💵 Deposit'), KeyboardButton(text='📤 Transfer')],
            [KeyboardButton(text='📅 Pay Monthly Loan')]
        ]
        markup = ReplyKeyboardMarkup(keyboard=reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
        await message.answer(greeting_text + "\nYou are already registered.", reply_markup=markup)
    else:
        reply_keyboard = [[KeyboardButton(text='📝 Register')]]
        markup = ReplyKeyboardMarkup(keyboard=reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
        await message.answer(greeting_text + "\nYou are not registered yet.", reply_markup=markup)

# /register command handler
@router.message(Command(commands=['register']))
async def register_user(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    if is_user_registered(telegram_id):
        reply_keyboard = [
            [KeyboardButton(text='💳 Check Balance'), KeyboardButton(text='ℹ️ My Info')],
            [KeyboardButton(text='💸 Take a Loan'), KeyboardButton(text='🎁 Donate to Charity')]
        ]
        markup = ReplyKeyboardMarkup(keyboard=reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
        await message.answer("You are already registered. What would you like to do?", reply_markup=markup)
        return
    await message.answer("Please provide your name.")
    await state.update_data(telegram_id=telegram_id)
    await state.set_state(Registration.waiting_for_name)

# Handler for the "Register" button
@router.message(F.text == '📝 Register')
async def handle_register_button(message: Message, state: FSMContext):
    await register_user(message, state)

# Handle name input
@router.message(Registration.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text
    if not is_valid_name(name):
        await message.answer("❌ Invalid name. Please enter a valid name.")
        return
    await state.update_data(name=name)
    await message.answer("Thank you! Now, please provide your email.")
    await state.set_state(Registration.waiting_for_email)

# Handle email input
@router.message(Registration.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    email = message.text
    if not is_valid_email(email):
        await message.answer("❌ Invalid email. Please enter a valid email.")
        return
    await state.update_data(email=email)
    await message.answer("Now, please provide your phone number.")
    await state.set_state(Registration.waiting_for_phone)

# Handle phone input and finalize registration
@router.message(Registration.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text
    if not is_valid_phone(phone):
        await message.answer("❌ Invalid phone number. Please enter a valid phone number.")
        return
    user_data = await state.get_data()
    name = user_data['name']
    email = user_data['email']
    telegram_id = user_data['telegram_id']
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute('INSERT INTO users (id, name, email, phone) VALUES (?, ?, ?, ?)', (telegram_id, name, email, phone))
        account_number = f"ACC{telegram_id}"
        initial_balance = 0.0
        cursor.execute('INSERT INTO accounts (userId, accountNumber, accountType, balance) VALUES (?, ?, ?, ?)', (telegram_id, account_number, 'savings', initial_balance))
        connection.commit()
        connection.close()
        await message.answer(f"✅ Registration completed for {name}! Your account number is {account_number}.")
    except sqlite3.IntegrityError as e:
        await message.answer(f"❌ Registration failed: {e}")
    except sqlite3.Error as e:
        await message.answer(f"❌ Database error: {e}")
    finally:
        connection.close()
    await state.clear()
    reply_keyboard = [
        [KeyboardButton(text='💳 Check Balance'), KeyboardButton(text='ℹ️ My Info')],
        [KeyboardButton(text='💸 Take a Loan'), KeyboardButton(text='🎁 Donate to Charity')]
    ]
    markup = ReplyKeyboardMarkup(keyboard=reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
    await message.answer("What would you like to do next?", reply_markup=markup)

@router.message(F.text == '💸 Take a Loan')
async def initiate_loan(message: Message, state: FSMContext):
    await message.answer("Enter the loan amount:")
    await state.set_state(Loan.waiting_for_amount)

@router.message(Loan.waiting_for_amount)
async def process_loan_amount(message: Message, state: FSMContext):
    amount_text = message.text
    if not is_positive_amount(amount_text):
        await message.answer("❌ Invalid amount. Please enter a positive number.")
        return

    amount = float(amount_text)
    if amount > 45000:
        await message.answer("❌ Loan amount exceeds the individual limit of 45,000 units.")
        return

    # Check the user's total loan balance
    telegram_id = message.from_user.id
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute('SELECT SUM(remainingBalance) FROM loans WHERE userId = ?', (telegram_id,))
    total_outstanding = cursor.fetchone()[0] or 0

    if total_outstanding + amount > 50000:
        await message.answer("❌ Total loan balance cannot exceed 50,000 units.")
        connection.close()
        return

    await state.update_data(loan_amount=amount)
    await message.answer("Select loan duration (3, 6, or 12 months):")
    await state.set_state(Loan.waiting_for_duration)
    connection.close()

# Check user info handler
@router.message(F.text == 'ℹ️ My Info')
async def get_user_info(message: Message):
    try:
        telegram_id = message.from_user.id
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute('SELECT name, email FROM users WHERE id = ?', (telegram_id,))
        user_info = cursor.fetchone()
        cursor.execute('SELECT accountNumber, balance FROM accounts WHERE userId = ?', (telegram_id,))
        account_info = cursor.fetchone()
        if user_info and account_info:
            name, email = user_info
            account_number, balance = account_info
            await message.answer(f"ℹ️ Your Info:\nName: {name}\nEmail: {email}\nAccount Number: {account_number}\nBalance: {balance} units.")
        else:
            await message.answer("No information found. Please register first.")
        connection.close()
    except sqlite3.Error as e:
        await message.answer(f"Failed to retrieve your info: {e}")

# Handler for "Take a Loan" and "Donate to Charity"
@router.message(F.text.in_(['💸 Take a Loan', '🎁 Donate to Charity']))
async def initiate_transaction(message: Message, state: FSMContext):
    transaction_type = "loan" if message.text == '💸 Take a Loan' else "donation"
    await state.update_data(transaction_type=transaction_type)
    await message.answer("Enter the amount:")
    await state.set_state(Transaction.waiting_for_amount)

# Handle transaction amount with loan limit check
@router.message(Transaction.waiting_for_amount)
async def process_transaction_amount(message: Message, state: FSMContext):
    amount_text = message.text
    if not is_positive_amount(amount_text):
        await message.answer("❌ Invalid amount. Please enter a positive number.")
        return

    amount = float(amount_text)
    user_data = await state.get_data()
    transaction_type = user_data['transaction_type']
    telegram_id = message.from_user.id

    if transaction_type == "loan" and amount > LOAN_LIMIT:
        await message.answer(f"❌ Loan amount exceeds limit of {LOAN_LIMIT} units.")
        return

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute('SELECT id FROM accounts WHERE userId = ?', (telegram_id,))
        account_id = cursor.fetchone()[0]
        
        if transaction_type == "loan":
            cursor.execute('INSERT INTO transactions (accountId, amount, transactionType) VALUES (?, ?, ?)', (account_id, amount, 'Loan'))
            await message.answer(f"💸 Loan of {amount} units added to your balance.")
        elif transaction_type == "donation":
            cursor.execute('SELECT balance FROM accounts WHERE id = ?', (account_id,))
            balance = cursor.fetchone()[0]
            if balance < amount:
                await message.answer("❌ Insufficient balance for this donation.")
                return
            cursor.execute('INSERT INTO transactions (accountId, amount, transactionType) VALUES (?, ?, ?)', (account_id, -amount, 'Donation'))
            await message.answer(f"🎁 {amount} units donated to charity. Thank you!")
        elif transaction_type == "deposit":
            cursor.execute('INSERT INTO transactions (accountId, amount, transactionType) VALUES (?, ?, ?)', (account_id, amount, 'Deposit'))
            await message.answer(f"💵 Deposit of {amount} units successful.")

        connection.commit()
    except sqlite3.Error as e:
        await message.answer(f"❌ Transaction failed: {e}")
    finally:
        connection.close()

    await state.clear()

# Handler for "Deposit" option
@router.message(F.text == '💵 Deposit')
async def initiate_deposit(message: Message, state: FSMContext):
    await state.update_data(transaction_type="deposit")
    await message.answer("Enter the deposit amount:")
    await state.set_state(Transaction.waiting_for_amount)

# Handler for "Transfer" option
@router.message(F.text == '📤 Transfer')
async def initiate_transfer(message: Message, state: FSMContext):
    await message.answer("Enter the phone number of the recipient:")
    await state.set_state(Transfer.waiting_for_recipient_phone)

@router.message(Transfer.waiting_for_recipient_phone)
async def get_transfer_recipient(message: Message, state: FSMContext):
    recipient_phone = message.text
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute('SELECT id, name FROM users WHERE phone = ?', (recipient_phone,))
    recipient = cursor.fetchone()
    connection.close()
    
    if recipient:
        recipient_id, recipient_name = recipient
        await state.update_data(recipient_id=recipient_id, recipient_name=recipient_name)  # Store recipient details
        await message.answer(f"Recipient: {recipient_name}\nEnter the transfer amount:")
        await state.set_state(Transfer.waiting_for_transfer_amount)
    else:
        await message.answer("❌ No user found with that phone number.")
        await state.clear()

@router.message(Transfer.waiting_for_transfer_amount)
async def process_transfer_amount(message: Message, state: FSMContext):
    amount_text = message.text
    if not is_positive_amount(amount_text):
        await message.answer("❌ Invalid amount. Please enter a positive number.")
        return

    amount = float(amount_text)
    user_data = await state.get_data()
    telegram_id = message.from_user.id
    recipient_id = user_data['recipient_id']
    recipient_name = user_data['recipient_name']  # Access recipient name from state data

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Fetch sender's balance
        cursor.execute('SELECT balance FROM accounts WHERE userId = ?', (telegram_id,))
        sender_balance = cursor.fetchone()[0]
        
        if sender_balance < amount:
            await message.answer("❌ Insufficient balance for this transfer.")
            return

        # Deduct from sender's balance
        cursor.execute('UPDATE accounts SET balance = balance - ? WHERE userId = ?', (amount, telegram_id))
        
        # Add to recipient's balance
        cursor.execute('UPDATE accounts SET balance = balance + ? WHERE userId = ?', (amount, recipient_id))

        # Record transactions for both parties
        cursor.execute('INSERT INTO transactions (accountId, amount, transactionType) VALUES (?, ?, ?)', (telegram_id, -amount, 'Transfer Out'))
        cursor.execute('INSERT INTO transactions (accountId, amount, transactionType) VALUES (?, ?, ?)', (recipient_id, amount, 'Transfer In'))
        
        connection.commit()
        
        await message.answer(f"📤 Transfer of {amount} units sent to {recipient_name} successfully.")

        # Send a notification to the recipient
        recipient_telegram_id = recipient_id  # Assuming recipient_id is also their Telegram ID
        await bot.send_message(recipient_telegram_id, f"💰 You have received a transfer of {amount} units from {message.from_user.full_name}.")

    except sqlite3.Error as e:
        await message.answer(f"❌ Transfer failed: {e}")
    finally:
        connection.close()

    await state.clear()


# Main entry point
async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.info("Starting bot...")
    asyncio.run(main())