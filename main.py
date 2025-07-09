
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from flask import Flask, request
from telegram import Update, Bot, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = Flask(__name__)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)
sheet = client.open("BRNDY Orders").sheet1

def add_order_to_sheet(user_name, order_text):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    sheet.append_row([now, user_name, order_text])

CHOOSING, TYPING_REPLY = range(2)
ADMIN_USERNAME = "@daribayev6"

app_bot = ApplicationBuilder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [['Сделать заказ', 'Отследить заказ']]
    await update.message.reply_text(
        "Добро пожаловать в BRNDY Europe! Чем могу помочь?",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return CHOOSING

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/help - список команд\n"
        "/orders - последние 5 заказов (только для админа)\n"
        "/track @username трек - отправить трек-номер клиенту (только для админа)"
    )

async def choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['choice'] = text

    if text == 'Сделать заказ':
        await update.message.reply_text("Отправьте ссылку или фото товара, цвет, размер и количество.")
        return TYPING_REPLY

    elif text == 'Отследить заказ':
        await update.message.reply_text("Введите номер заказа.")
        return TYPING_REPLY

async def received_information(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    choice = context.user_data['choice']

    if choice == 'Сделать заказ':
        context.user_data['order'] = user_text
        try:
            add_order_to_sheet(update.message.from_user.username, user_text)
        except Exception as e:
            print("Ошибка:", e)

        await update.message.reply_text(
            f"Спасибо! Ваш заказ:\n{user_text}\n"
            "💶 Примерная цена: от 100€\n"
            "🚚 Доставка: 10–14 дней"
        )

    elif choice == 'Отследить заказ':
        await update.message.reply_text(f"Спасибо! Проверим статус по номеру: {user_text}.")

    return ConversationHandler.END

async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username != ADMIN_USERNAME[1:]:
        await update.message.reply_text("⛔ Нет доступа.")
        return
    rows = sheet.get_all_values()[-5:] if len(sheet.get_all_values()) > 1 else []
    response = "\n".join([" | ".join(row) for row in rows]) if rows else "Нет заказов."
    await update.message.reply_text(response)

async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username != ADMIN_USERNAME[1:]:
        await update.message.reply_text("⛔ Нет доступа.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Формат: /track @username трек-номер")
        return
    username = context.args[0]
    track_number = " ".join(context.args[1:])
    await context.bot.send_message(chat_id=username, text=f"📦 Ваш заказ отправлен! Трек: {track_number}")
    await update.message.reply_text(f"✅ Трек отправлен {username}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Действие отменено. Напишите /start.')

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        CHOOSING: [MessageHandler(filters.TEXT & ~filters.COMMAND, choice_handler)],
        TYPING_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_information)],
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)

app_bot.add_handler(conv_handler)
app_bot.add_handler(CommandHandler("help", help_command))
app_bot.add_handler(CommandHandler("orders", orders_command))
app_bot.add_handler(CommandHandler("track", track_command))

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        update = Update.de_json(request.get_json(force=True), app_bot.bot)
        app_bot.update_queue.put(update)
        return 'ok'

@app.route('/')
def index():
    return "BRNDY Bot is running."

if __name__ == '__main__':
    bot_instance = Bot(token=TOKEN)
    bot_instance.set_webhook(WEBHOOK_URL + '/webhook')
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
