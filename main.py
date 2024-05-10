import logging
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, \
    callback_query
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup


API_TOKEN = '6751870961:AAGU4Yna3sMrO8rVPOXSi2uyO40qng21Ey8'

MODERATOR_IDS = [406299011]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

conn = sqlite3.connect('suppliers.db')
cur = conn.cursor()

# Создаем таблицу в базе данных для хранения данных пользователей
cur.execute('''CREATE TABLE IF NOT EXISTS users 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       user_id INTEGER, 
                       username TEXT, 
                       first_name TEXT)''')

# Создаем таблицу в базе данных для записей о приемах
cur.execute('''CREATE TABLE IF NOT EXISTS appointments 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       user_id INTEGER, 
                       appointment_date TEXT,
                       appointment_time TEXT,
                       FOREIGN KEY(user_id) REFERENCES users(user_id))''')

conn.commit()
conn.close()

# Временные слоты для записи
TIME_SLOTS = {
    "Пн": [(f"{hour}:00", f"{hour + 1}:00") for hour in range(11, 18)],
    "Вт": [(f"{hour}:00", f"{hour + 1}:00") for hour in range(11, 18)],
    "Ср": [(f"{hour}:00", f"{hour + 1}:00") for hour in range(11, 18)],
    "Чт": [(f"{hour}:00", f"{hour + 1}:00") for hour in range(11, 18)],
}

# Определение класса состояний
class SupplierRegistration(StatesGroup):
    save_name = State()  # Состояние для сохранения имени

# Обработчик команды /start для начала регистрации
@dp.message_handler(commands=['start'])
async def start_registration(message: types.Message, state: FSMContext):
    # Проверяем, зарегистрирован ли пользователь
    conn = sqlite3.connect('suppliers.db')
    cursor = conn.cursor()
    cursor.execute("SELECT first_name FROM users WHERE user_id=?", (message.from_user.id,))
    user_name = cursor.fetchone()
    conn.close()

    if user_name:
        # Если пользователь уже зарегистрирован, предлагаем ему выбор: изменить имя или продолжить запись
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.KeyboardButton("/change_name"))
        keyboard.add(types.KeyboardButton("/continue_record"))
        await message.reply("Вы уже зарегистрированы. Хотите изменить имя или продолжить запись?",
                            reply_markup=keyboard)

    else:
        await message.reply("Привет! Пожалуйста, укажите ваше имя.")
        await SupplierRegistration.save_name.set()

# Обработчик команды /continue_record для продолжения записи без изменения имени
@dp.message_handler(commands=['continue_record'])
async def continue_record(message: types.Message, state: FSMContext):# Показываем меню

    await show_menu(message)
    # Здесь можно продолжить процесс записи

# Обработчик сохранения имени
@dp.message_handler(state=SupplierRegistration.save_name)
async def save_name(message: types.Message, state: FSMContext):
    name = message.text

    # Сохраняем или обновляем имя в таблице пользователей
    conn = sqlite3.connect('suppliers.db')
    cursor = conn.cursor()
    cursor.execute("SELECT first_name FROM users WHERE user_id=?", (message.from_user.id,))
    user_data = cursor.fetchone()

    if user_data:
        # Пользователь уже зарегистрирован, обновляем его имя
        cursor.execute("UPDATE users SET first_name=? WHERE user_id=?", (name, message.from_user.id))
    else:
        # Пользователь не зарегистрирован, добавляем его данные
        cursor.execute("INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                       (message.from_user.id, message.from_user.username, name))
    conn.commit()
    conn.close()

    await message.reply("Ваше имя успешно сохранено!")

    # Показываем меню
    await show_menu(message)

    # Завершаем состояние сохранения имени
    await state.finish()

# Обработчик команды /change_name для изменения имени
@dp.message_handler(commands=['change_name'])
async def change_name(message: types.Message, state: FSMContext):
    await message.reply("Пожалуйста, укажите ваше новое имя.")
    await SupplierRegistration.save_name.set()
# Обработчик команды /record для записи на прием
@dp.message_handler(commands=['record'])
async def record_supplier(message: types.Message, state: FSMContext):
    # Проверяем, зарегистрирован ли пользователь
    conn = sqlite3.connect('suppliers.db')
    cursor = conn.cursor()
    cursor.execute("SELECT first_name FROM users WHERE user_id=?", (message.from_user.id,))
    user_name = cursor.fetchone()
    conn.close()

    if user_name:
        keyboard = InlineKeyboardMarkup()
        for day, date in get_next_week_dates().items():
            button_text = f"{day} {date}"
            button_data = f"record_{day.lower()}_{date}"
            keyboard.add(InlineKeyboardButton(text=button_text, callback_data=button_data))

        await message.reply("Выберите день недели и дату:", reply_markup=keyboard)
    else:
        await message.reply("Для записи на прием необходимо сначала зарегистрироваться с помощью команды /start.")

# Функция для показа меню с кнопками
async def show_menu(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("/record"), types.KeyboardButton("/my_appointments"))
                 # types.KeyboardButton("/change_name"))
    await message.reply("Выберите действие:", reply_markup=keyboard)

# Получение дат на следующую неделю
def get_next_week_dates():
    today = datetime.now()
    weekdays = ["Пн", "Вт", "Ср", "Чт"]
    next_week_dates = {}
    for i in range(4):
        next_date = today + timedelta(days=i)
        next_week_dates[weekdays[i]] = next_date.strftime("%Y-%m-%d")
    return next_week_dates

# Обработчик инлайн-кнопок для выбора времени
@dp.callback_query_handler(lambda c: c.data.startswith('record'))
async def process_record_callback(callback_query: types.CallbackQuery):
    data_parts = callback_query.data.split('_')
    day = data_parts[1].capitalize()
    date = data_parts[2]

    keyboard = InlineKeyboardMarkup()
    for start, end in TIME_SLOTS[day]:
        availability = "занято" if not is_timeslot_available(date, start, end) else "свободно"
        button_text = f"{start}-{end} ({availability})"
        button_data = f"book_{date}_{start}_{end}"
        keyboard.add(InlineKeyboardButton(text=button_text, callback_data=button_data))

    await callback_query.message.answer(f"Доступное время на {day} {date}:", reply_markup=keyboard)

# Функция для проверки доступности временного слота
def is_timeslot_available(date, start, end):
    conn = sqlite3.connect('suppliers.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM appointments WHERE appointment_date=? AND appointment_time=?",
                   (date, f"{start}-{end}"))
    count = cursor.fetchone()[0]
    conn.close()

    return count == 0

# Обработчик выбора временного слота для записи
@dp.callback_query_handler(lambda c: c.data.startswith('book'))
async def process_booking_callback(callback_query: types.CallbackQuery):
    data_parts = callback_query.data.split('_')
    date, start, end = data_parts[1], data_parts[2], data_parts[3]

    if is_timeslot_available(date, start, end):
        # Записываем прием в таблицу записей
        conn = sqlite3.connect('suppliers.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO appointments (user_id, appointment_date, appointment_time) VALUES (?, ?, ?)",
                       (callback_query.from_user.id, date, f"{start}-{end}"))
        conn.commit()
        conn.close()

        await callback_query.answer("Вы успешно записаны.")
    else:
        await callback_query.answer("Выбранный временной слот занят.")

# Обработчик команды /my_appointments для просмотра записей
@dp.message_handler(commands=['my_appointments'])
async def my_appointments(message: types.Message):
    user_id = message.from_user.id

    conn = sqlite3.connect('suppliers.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, appointment_date, appointment_time FROM appointments WHERE user_id=?", (user_id,))
    appointments = cursor.fetchall()

    if appointments:
        await message.answer("Ваши записи:")
        for appointment_id, appointment_date, appointment_time in appointments:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("Удалить", callback_data=f"delete_appointment_{appointment_id}"))
            await message.answer(f"{appointment_date}, {appointment_time}", reply_markup=markup)
    else:
        await message.answer("У вас нет записей.")
    conn.close()

    # Показываем меню после выполнения функции my_appointments
    await show_menu(message)
# Обработчик нажатия кнопки "Удалить" для записи о приеме
@dp.callback_query_handler(lambda c: c.data.startswith('delete_appointment'))
async def delete_appointment(callback_query: types.CallbackQuery):
    appointment_id = callback_query.data.split('_')[-1]

    conn = sqlite3.connect('suppliers.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM appointments WHERE id=?", (appointment_id,))
    conn.commit()
    conn.close()

    await callback_query.message.delete()
    await callback_query.answer("Запись успешно удалена.")


# Обработчик команды /all_appointments для модератора
@dp.message_handler(commands=['all_appointments'])
async def all_appointments_for_moderator(message: types.Message):
    if message.from_user.id not in MODERATOR_IDS:
        await message.answer("У вас нет прав доступа к этой команде.")
        return

    conn = sqlite3.connect('suppliers.db')
    cursor = conn.cursor()
    cursor.execute("SELECT a.id, u.first_name, u.username, a.appointment_date, a.appointment_time FROM appointments a LEFT JOIN users u ON a.user_id = u.user_id")

    appointments = cursor.fetchall()

    if appointments:
        await message.answer("Все записи:")
        for appointment_id, name, username, appointment_date, appointment_time in appointments:
            username_display = username if username else "не указано"
            name_display = name if name else "не указано"
            appointment_display = f"{appointment_date}, {appointment_time}" if appointment_date and appointment_time else "не указано"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("Удалить", callback_data=f"delete_moderator_appointment_{appointment_id}"))
            await message.answer(f"{name_display} ({username_display}) - {appointment_display}", reply_markup=markup)
    else:
        await message.answer("Нет записей.")
    conn.close()
# Обработчик нажатия кнопки "Удалить" для записи о приеме модератором
@dp.callback_query_handler(lambda c: c.data.startswith('delete_moderator_appointment'))
async def delete_moderator_appointment(callback_query: types.CallbackQuery):
    appointment_id = callback_query.data.split('_')[-1]

    conn = sqlite3.connect('suppliers.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, appointment_date, appointment_time FROM appointments WHERE id=?", (appointment_id,))
    appointment = cursor.fetchone()

    if appointment:
        user_id, appointment_date, appointment_time = appointment
        cursor.execute("DELETE FROM appointments WHERE id=?", (appointment_id,))
        conn.commit()
        conn.close()

        await callback_query.answer("Запись успешно удалена.")

        try:
            await bot.send_message(user_id, f"Ваша запись на {appointment_date}, {appointment_time} была отменена модератором.")
        except Exception as e:
            logger.exception(f"Ошибка при отправке уведомления пользователю: {e}")
    else:
        await callback_query.answer("Запись не найдена.")


# Добавляем логгирование
dp.middleware.setup(LoggingMiddleware())

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)