import asyncio
import os
import json
from datetime import datetime
import pytz
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, BotCommandScopeDefault, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp
import schedule
import time
from threading import Thread

# Загрузка переменных окружения
load_dotenv()

# Инициализация бота и диспетчера
token = os.getenv('BOT_TOKEN')
if not token:
    raise ValueError("BOT_TOKEN не установлен в .env файле")
bot = Bot(token=token)
dp = Dispatcher()

# Установка часового пояса Мадрида
MADRID_TZ = pytz.timezone('Europe/Madrid')

# Состояния FSM
class NotificationSettings(StatesGroup):
    waiting_for_time = State()

# Путь к файлу с настройками уведомлений
NOTIFICATIONS_FILE = 'notifications.json'

# Словарь для хранения настроек уведомлений пользователей
user_notifications = {}

# Словарь для хранения времени последней отправки уведомлений
last_notification_sent: dict[int, datetime] = {}

# Тип для callback.message
CallbackMessage = Message

def load_notifications():
    """Загрузка настроек уведомлений из файла"""
    global user_notifications, last_notification_sent
    try:
        if os.path.exists(NOTIFICATIONS_FILE):
            with open(NOTIFICATIONS_FILE, 'r') as f:
                data = json.load(f)
                # Преобразуем строковые ключи в целые числа
                user_notifications = {int(k): v for k, v in data.items()}
                # Инициализируем словарь времени последней отправки
                last_notification_sent = {int(k): datetime.now(MADRID_TZ) for k in user_notifications.keys()}
    except Exception as e:
        print(f"Ошибка загрузки настроек уведомлений: {e}")
        user_notifications = {}
        last_notification_sent = {}

def save_notifications():
    """Сохранение настроек уведомлений в файл"""
    try:
        # Преобразуем целочисленные ключи в строки для JSON
        data = {str(k): v for k, v in user_notifications.items()}
        with open(NOTIFICATIONS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения настроек уведомлений: {e}")

# Загружаем настройки при запуске
load_notifications()

# Кэш для хранения данных
cached_data = None
last_cache_time = None
CACHE_DURATION = 300  # 5 минут в секундах

async def fetch_crypto_data():
    """Получение данных о криптовалютах"""
    global cached_data, last_cache_time
    
    # Проверяем кэш
    current_time = datetime.now(MADRID_TZ)
    if cached_data and last_cache_time and (current_time - last_cache_time).total_seconds() < CACHE_DURATION:
        return cached_data

    async with aiohttp.ClientSession() as session:
        try:
            # Добавляем заголовки для имитации браузера
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Увеличенная задержка перед запросом
            await asyncio.sleep(5)
            
            # Получаем все необходимые данные одним запросом
            async with session.get(
                f"{os.getenv('COINGECKO_API_URL')}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&sparkline=false&price_change_percentage=24h",
                headers=headers
            ) as response:
                if response.status == 429:
                    print("Превышен лимит запросов к API. Ожидание 120 секунд...")
                    await asyncio.sleep(120)
                    return cached_data if cached_data else None
                if response.status != 200:
                    raise Exception(f"Ошибка API: {response.status}")
                coins_data = await response.json()

            # Задержка между запросами
            await asyncio.sleep(5)

            # Получаем глобальные данные
            async with session.get(
                f"{os.getenv('COINGECKO_API_URL')}/global",
                headers=headers
            ) as response:
                if response.status == 429:
                    print("Превышен лимит запросов к API. Ожидание 120 секунд...")
                    await asyncio.sleep(120)
                    return cached_data if cached_data else None
                if response.status != 200:
                    raise Exception(f"Ошибка API: {response.status}")
                global_data = await response.json()

            # Получаем индекс страха и жадности
            async with session.get(
                f"{os.getenv('FEAR_GREED_API_URL')}",
                headers=headers
            ) as response:
                if response.status == 200:
                    fear_greed_data = await response.json()
                    fear_greed_index = int(fear_greed_data['data'][0]['value'])
                else:
                    fear_greed_index = None

            # Формируем данные
            data = {
                'btc_price': next(coin['current_price'] for coin in coins_data if coin['id'] == 'bitcoin'),
                'btc_change_24h': next(coin['price_change_percentage_24h'] for coin in coins_data if coin['id'] == 'bitcoin'),
                'total_market_cap': global_data['data']['total_market_cap']['usd'],
                'total_market_cap_change_24h': global_data['data']['market_cap_change_percentage_24h_usd'],
                'btc_dominance': global_data['data']['market_cap_percentage']['btc'],
                'fear_greed_index': fear_greed_index,
                'top_coins': coins_data
            }

            # Обновляем кэш
            cached_data = data
            last_cache_time = current_time

            return data
        except Exception as e:
            print(f"Ошибка при получении данных: {str(e)}")
            return cached_data if cached_data else None

def create_summary_message(data):
    """Создание красивого сообщения с данными"""
    if data is None:
        return "❌ Извините, не удалось получить данные о криптовалютах. Пожалуйста, попробуйте позже."
    
    # Определяем эмодзи и статус для индекса страха и жадности
    fear_greed_text = ""
    if data['fear_greed_index'] is not None:
        if data['fear_greed_index'] >= 75:
            fear_greed_text = f"😱 Индекс страха и жадности: *{data['fear_greed_index']}* (Крайняя жадность)"
        elif data['fear_greed_index'] >= 60:
            fear_greed_text = f"😊 Индекс страха и жадности: *{data['fear_greed_index']}* (Жадность)"
        elif data['fear_greed_index'] >= 40:
            fear_greed_text = f"😐 Индекс страха и жадности: *{data['fear_greed_index']}* (Нейтрально)"
        elif data['fear_greed_index'] >= 25:
            fear_greed_text = f"😨 Индекс страха и жадности: *{data['fear_greed_index']}* (Страх)"
        else:
            fear_greed_text = f"😱 Индекс страха и жадности: *{data['fear_greed_index']}* (Крайний страх)"
    
    # Формируем список топ-10 криптовалют
    top_coins_text = "\n🏆 *Топ-10 криптовалют:*\n"
    for i, coin in enumerate(data['top_coins'], 1):
        change_24h = coin['price_change_percentage_24h']
        change_emoji = "📈" if change_24h > 0 else "📉"
        top_coins_text += f"{i}. {coin['name']} ({coin['symbol'].upper()}): ${coin['current_price']:,.2f} {change_emoji} {change_24h:.2f}%\n"
    
    return f"""
📊 dEagle-крипто дайджест на {datetime.now(MADRID_TZ).strftime('%d.%m.%Y %H:%M')} (GMT+2)

💰 Доминация BTC: *{data['btc_dominance']:.2f}*%
📈 Цена BTC: *${data['btc_price']:,.0f}* ({data['btc_change_24h']:.2f}% за 24ч)
💎 Капитализация рынка: _${data['total_market_cap']:,.0f}_ 
{fear_greed_text}
{top_coins_text}
"""

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Проверить показатели", callback_data="check")],
        [InlineKeyboardButton(text="⚙️ Настройка уведомлений", callback_data="settings")]
    ])
    await message.answer("Приветствую, деген. Я бот для мониторинга криптовалютных показателей. Поставь уведомления и будь в курсе когда уже бычка", reply_markup=keyboard)

@dp.message(Command("check"))
async def cmd_check(message: types.Message):
    """Обработчик команды /check"""
    data = await fetch_crypto_data()
    await message.answer(create_summary_message(data), parse_mode="Markdown")

@dp.callback_query(F.data == "check")
async def process_check_callback(callback: types.CallbackQuery):
    """Обработчик нажатия кнопки проверки показателей"""
    if not callback.message:
        return
    data = await fetch_crypto_data()
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=create_summary_message(data),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(Command("settings"))
async def cmd_settings(message: types.Message):
    """Обработчик команды /settings"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    current_time = user_notifications.get(user_id, "Не установлено")
    
    # Создаем клавиатуру в зависимости от статуса уведомлений
    if user_id in user_notifications:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🕐 Изменить время уведомлений", callback_data="set_time")],
            [InlineKeyboardButton(text="❌ Отключить уведомления", callback_data="disable_notifications")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🕐 Включить уведомления", callback_data="set_time")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
    
    await message.answer(
        f"⚙️ Ваши настройки уведомлений:\n\n"
        f"🕒 Текущее время уведомлений: {current_time}\n"
        f"🌍 Часовой пояс: Мадрид (UTC+1)\n\n"
        f"Выберите действие:",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "set_time")
async def process_set_time_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик установки времени уведомлений"""
    if not callback.message:
        return
    if not callback.from_user:
        return
    user_id = callback.from_user.id
    current_time = user_notifications.get(user_id, "Не установлено")
    
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=f"🕒 Текущее время уведомлений: {current_time}\n\n"
             f"Введите новое время для ежедневных уведомлений в формате ЧЧ:ММ (GMT+2) (например, 09:00):\n"
             f"⚠️ Учитывайте, что время указывается по часовому поясу GMT+2\n\n"
             f"Примеры форматов:\n"
             f"• 09:00 - уведомления в 9 утра\n"
             f"• 15:30 - уведомления в 3:30 дня\n"
             f"• 23:00 - уведомления в 11 вечера"
    )
    await state.set_state(NotificationSettings.waiting_for_time)
    await callback.answer()

@dp.message(NotificationSettings.waiting_for_time)
async def process_time_input(message: types.Message, state: FSMContext):
    """Обработчик ввода времени"""
    if not message.from_user:
        return
    if not message.text:
        return
    try:
        time_str = message.text
        hour, minute = map(int, time_str.split(':'))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            # Сохраняем время в формате ЧЧ:ММ
            user_notifications[message.from_user.id] = time_str
            save_notifications()  # Сохраняем настройки
            
            # Создаем клавиатуру для возврата в настройки
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🕐 Изменить время", callback_data="set_time")],
                [InlineKeyboardButton(text="❌ Отключить уведомления", callback_data="disable_notifications")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
            ])
            
            await message.answer(
                f"✅ Уведомления настроены на время {time_str} (GMT+2)\n"
                f"Следующее уведомление будет отправлено в {time_str} (GMT+2)",
                reply_markup=keyboard
            )
            await state.clear()
        else:
            await message.answer("❌ Неверный формат времени. Попробуйте еще раз.")
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте формат ЧЧ:ММ")

@dp.callback_query(F.data == "disable_notifications")
async def process_disable_notifications(callback: types.CallbackQuery):
    """Обработчик отключения уведомлений"""
    if not callback.message:
        return
    if not callback.from_user:
        return
    user_id = callback.from_user.id
    # Создаем клавиатуру для возврата в настройки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕐 Включить уведомления", callback_data="set_time")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    
    if user_id in user_notifications:
        del user_notifications[user_id]
        save_notifications()  # Сохраняем настройки
        
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text="✅ Уведомления отключены\n\n"
                 "Чтобы снова получать уведомления, нажмите кнопку ниже:",
            reply_markup=keyboard
        )
    else:
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text="ℹ️ Уведомления уже отключены\n\n"
                 "Чтобы включить уведомления, нажмите кнопку ниже:",
            reply_markup=keyboard
        )
    await callback.answer()

@dp.callback_query(F.data == "back")
async def process_back_callback(callback: types.CallbackQuery):
    """Обработчик возврата в главное меню"""
    if not callback.message:
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Проверить показатели", callback_data="check")],
        [InlineKeyboardButton(text="⚙️ Настройка уведомлений", callback_data="settings")]
    ])
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text="Главное меню:",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data == "settings")
async def process_settings_callback(callback: types.CallbackQuery):
    """Обработчик нажатия кнопки настроек"""
    if not callback.message:
        return
    if not callback.from_user:
        return
    user_id = callback.from_user.id
    current_time = user_notifications.get(user_id, "Не установлено")
    
    # Создаем клавиатуру в зависимости от статуса уведомлений
    if user_id in user_notifications:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🕐 Изменить время уведомлений", callback_data="set_time")],
            [InlineKeyboardButton(text="❌ Отключить уведомления", callback_data="disable_notifications")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🕐 Включить уведомления", callback_data="set_time")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
    
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=f"⚙️ Ваши настройки уведомлений:\n\n"
             f"🕒 Текущее время уведомлений: {current_time}\n"
             f"🌍 Часовой пояс: GMT+2\n\n"
             f"Выберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()

async def send_notifications():
    """Функция отправки уведомлений"""
    print("Запущен планировщик уведомлений")
    while True:
        try:
            # Получаем текущее время в часовом поясе Мадрида
            current_time = datetime.now(MADRID_TZ)
            current_time_str = current_time.strftime("%H:%M")
            print(f"Текущее время (Мадрид): {current_time_str}")
            print(f"Активные уведомления: {user_notifications}")
            
            data = await fetch_crypto_data()
            
            if data:
                for user_id, notification_time in user_notifications.items():
                    if current_time_str == notification_time:
                        # Проверяем, не было ли уже отправлено уведомление в эту минуту
                        last_sent = last_notification_sent.get(user_id)
                        if last_sent is None or (current_time - last_sent).total_seconds() >= 60:
                            try:
                                print(f"Отправка уведомления пользователю {user_id} в {notification_time}")
                                await bot.send_message(user_id, create_summary_message(data), parse_mode="Markdown")
                                # Обновляем время последней отправки
                                last_notification_sent[user_id] = current_time
                            except Exception as e:
                                print(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
            else:
                print("Не удалось получить данные о криптовалютах")
                
            await asyncio.sleep(30)  # Проверка каждые 30 секунд
        except Exception as e:
            print(f"Общая ошибка в send_notifications: {e}")
            await asyncio.sleep(30)  # Ждем 30 секунд перед следующей попыткой

async def run_notification_scheduler():
    """Запуск планировщика уведомлений"""
    await send_notifications()

async def set_bot_commands():
    """Установка команд бота в меню"""
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="check", description="Проверить текущие показатели"),
        BotCommand(command="settings", description="Настройка уведомлений"),
        BotCommand(command="help", description="Помощь по использованию бота")
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = """
🤖 Я бот для мониторинга криптовалютных показателей.

📝 Доступные команды:
/start - Запустить бота
/check - Проверить текущие показатели
/settings - Настройка уведомлений
/help - Показать это сообщение

⚙️ Как использовать:
1. Нажмите /start для начала работы
2. Используйте кнопку "Проверить показатели" для получения актуальных данных
3. В настройках можно установить время ежедневных уведомлений
4. Уведомления отправляются по времени GMT+2

📊 В уведомлениях вы получите:
• Текущую цену Bitcoin
• Изменение цены за 24 часа
• Доминацию BTC
• Общую капитализацию рынка
• Топ-10 криптовалют по капитализации
• Индекс страха и жадности

✏️ Форматирование текста:
• *Жирный текст* - заключите текст в звездочки
• _Курсив_ - заключите текст в нижние подчеркивания
• __Подчеркнутый__ - используйте двойное нижнее подчеркивание
• `Моноширинный шрифт` - используйте обратные кавычки
• ~Зачеркнутый~ - используйте тильды

Примеры:
*Жирный* _курсив_ __подчеркнутый__
`код` ~зачеркнутый~
"""
    await message.answer(help_text, parse_mode="Markdown")

async def main():
    """Основная функция запуска бота"""
    # Установка команд бота
    await set_bot_commands()
    
    # Запуск планировщика уведомлений как отдельной задачи
    asyncio.create_task(run_notification_scheduler())
    
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 