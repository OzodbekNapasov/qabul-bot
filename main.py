import os
import re
import logging
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError

# .env faylini yuklaymiz (mavjud bo'lsa)
load_dotenv()

# Konfiguratsiyalar
BOT_TOKEN = os.getenv("BOT_TOKEN", "8808184685:AAE1Iu7sB6_Ck99m4DKfGxyi6kbkCRY1am0")
group_id_str = os.getenv("GROUP_ID", "-1002222222222")

try:
    GROUP_ID = int(group_id_str)
except ValueError:
    GROUP_ID = 0

# Loggingni sozlash
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# FSM holatlari
class RegistrationStates(StatesGroup):
    FullName = State()       # Ism va Familiya
    SecondPhone = State()    # Qo'shimcha shaxsiy telefon raqami
    PassportPhoto = State()  # Pasport nusxasi (Rasm)
    DiplomaPhoto = State()   # Diplom yoki shahodatnoma nusxasi (Rasm)

# Bot va Dispatcher obyektlarini yaratish
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# Foydalanuvchi asosiy telefon raqamlarini saqlash uchun vaqtinchalik xotira
user_contacts = {}

# Keyboardlar
def get_contact_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="📞 Telefon raqamini yuborish", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_apply_inline_keyboard():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="📝 Hujjat topshirish", callback_data="start_apply")]
        ]
    )

# 1. /start buyrug'i (Faqat shaxsiy chatlarda)
@router.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    welcome_text = (
        "👋 Assalomu alaykum! Xususiy tibbiyot texnikumi qabul botiga xush kelibsiz.\n\n"
        "Ro'yxatdan o'tishni boshlash uchun pastdagi tugma orqali telefon raqamingizni yuboring."
    )
    await message.answer(welcome_text, reply_markup=get_contact_keyboard())

# 2. Kontakt qabul qilish (Faqat shaxsiy chatlarda)
@router.message(F.contact, F.chat.type == "private")
async def contact_handler(message: types.Message):
    phone_number = message.contact.phone_number
    user_contacts[message.from_user.id] = phone_number
    
    await message.answer(
        f"✅ Telefon raqamingiz qabul qilindi: {phone_number}",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await message.answer(
        "Hujjat topshirishni boshlash uchun pastdagi 'Hujjat topshirish' tugmasini bosing.",
        reply_markup=get_apply_inline_keyboard()
    )

# 3. "Hujjat topshirish" tugmasi bosilganda (Inline Button Callback)
@router.callback_query(F.data == "start_apply")
async def start_registration_callback(callback: types.CallbackQuery, state: FSMContext):
    # Foydalanuvchi kontakt yuborganini tekshirish
    if callback.from_user.id not in user_contacts:
        await callback.answer(
            "⚠️ Iltimos, avval telefon raqamingizni yuboring!",
            show_alert=True
        )
        return
        
    await state.set_state(RegistrationStates.FullName)
    await callback.message.edit_reply_markup(reply_markup=None) # Bosilgan tugmani olib tashlaymiz
    await callback.message.answer(
        "✍️ Ism va Familiyangizni kiriting:"
    )
    await callback.answer()

# 4. FSM: Ism va Familiya qabul qilish
@router.message(RegistrationStates.FullName, F.text)
async def process_fullname(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await state.set_state(RegistrationStates.SecondPhone)
    await message.answer(
        "📞 Qo'shimcha shaxsiy telefon raqamingizni kiriting:\n"
        "(Masalan: +998901234567)"
    )

# 5. FSM: Qo'shimcha telefon raqami qabul qilish
@router.message(RegistrationStates.SecondPhone, F.text)
async def process_second_phone(message: types.Message, state: FSMContext):
    await state.update_data(second_phone=message.text)
    await state.set_state(RegistrationStates.PassportPhoto)
    await message.answer(
        "📸 Pasportingiz nusxasini rasm holatida yuboring (Photo):"
    )

# Agar foydalanuvchi rasm o'rniga boshqa narsa yuborsa
@router.message(RegistrationStates.PassportPhoto, ~F.photo)
async def process_passport_photo_invalid(message: types.Message):
    await message.answer("⚠️ Iltimos, pasport nusxasini faqat rasm (photo) ko'rinishida yuboring!")

# 6. FSM: Pasport nusxasi qabul qilish
@router.message(RegistrationStates.PassportPhoto, F.photo)
async def process_passport_photo(message: types.Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    await state.update_data(passport_photo=photo_file_id)
    await state.set_state(RegistrationStates.DiplomaPhoto)
    await message.answer(
        "📸 Shahodatnoma yoki diplom nusxasini rasm holatida yuboring (Photo):"
    )

# Agar diplom o'rniga boshqa narsa yuborsa
@router.message(RegistrationStates.DiplomaPhoto, ~F.photo)
async def process_diploma_photo_invalid(message: types.Message):
    await message.answer("⚠️ Iltimos, diplom/shahodatnoma nusxasini faqat rasm (photo) ko'rinishida yuboring!")

# 7. FSM: Diplom nusxasi qabul qilish va guruhga yuborish
@router.message(RegistrationStates.DiplomaPhoto, F.photo)
async def process_diploma_photo(message: types.Message, state: FSMContext):
    diploma_photo_file_id = message.photo[-1].file_id
    user_data = await state.get_data()
    
    # Barcha ma'lumotlarni yig'amiz
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
    full_name = user_data['full_name']
    main_phone = user_contacts.get(user_id, "Noma'lum")
    second_phone = user_data['second_phone']
    passport_photo_file_id = user_data['passport_photo']
    
    # FSM ni tozalaymiz
    await state.clear()
    
    # Foydalanuvchiga muvaffaqiyatli yakunlangani haqida xabar beramiz
    await message.answer(
        "🎉 Arizangiz qabul qilindi, tez orada shartnoma tayyorlanadi.",
        reply_markup=get_apply_inline_keyboard()
    )

    # Guruhga yuborish uchun chiroyli matn formati
    group_text = (
        "🔔 <b>Yangi ariza kelib tushdi!</b>\n\n"
        f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
        f"🔗 <b>Username:</b> {username}\n"
        f"👤 <b>F.I.O:</b> {full_name}\n"
        f"📞 <b>Asosiy telefon:</b> {main_phone}\n"
        f"📱 <b>Qo'shimcha telefon:</b> {second_phone}"
    )

    try:
        # Guruhga matnli ma'lumotni yuboramiz
        main_msg = await bot.send_message(
            chat_id=GROUP_ID,
            text=group_text
        )
        
        # Pasport rasmini guruhga yuboramiz (batafsil ma'lumot matniga reply qilib)
        await bot.send_photo(
            chat_id=GROUP_ID,
            photo=passport_photo_file_id,
            caption=f"📄 {full_name} - Pasport nusxasi\nTelegram ID: {user_id}",
            reply_to_message_id=main_msg.message_id
        )
        
        # Diplom rasmini guruhga yuboramiz
        await bot.send_photo(
            chat_id=GROUP_ID,
            photo=diploma_photo_file_id,
            caption=f"🎓 {full_name} - Diplom/Shahodatnoma nusxasi\nTelegram ID: {user_id}",
            reply_to_message_id=main_msg.message_id
        )
        
    except TelegramAPIError as e:
        logger.error(f"Guruhga ariza yuborishda xatolik: {e}")

# 8. Admin (Guruh) tomonidan reply qilinganda foydalanuvchiga shartnoma yuborish
@router.message(F.chat.id == GROUP_ID, F.reply_to_message)
async def handle_admin_reply(message: types.Message):
    # Reply qilingan xabar matnini tekshiramiz
    reply_to = message.reply_to_message
    target_text = reply_to.text or reply_to.caption or ""
    
    # Matndan Telegram ID ni ajratib olamiz
    match = re.search(r"Telegram ID:\s*(\d+)", target_text)
    if not match:
        return
        
    student_id = int(match.group(1))
    
    # Yuborilgan fayl yoki rasmni aniqlaymiz
    try:
        if message.document:
            await bot.send_document(
                chat_id=student_id,
                document=message.document.file_id,
                caption=message.caption or "📄 Sizning shartnomangiz tayyor bo'ldi."
            )
            await message.reply("✅ Shartnoma fayli abituriyentga muvaffaqiyatli yuborildi!")
            
        elif message.photo:
            await bot.send_photo(
                chat_id=student_id,
                photo=message.photo[-1].file_id,
                caption=message.caption or "📄 Sizning shartnomangiz tayyor bo'ldi."
            )
            await message.reply("✅ Shartnoma rasmi abituriyentga muvaffaqiyatli yuborildi!")
            
        else:
            # Agar boshqa turdagi xabar (masalan oddiy matn) yuborilgan bo'lsa
            await message.reply("⚠️ Iltimos, abituriyentga faqat fayl (PDF/hujjat) yoki rasm yuboring!")
            
    except TelegramAPIError as e:
        logger.error(f"Foydalanuvchiga shartnoma jo'natishda xatolik: {e}")
        await message.reply(f"❌ Shartnomani abituriyentga yuborib bo'lmadi. Xatolik: {e}")

# Asosiy ishga tushirish funksiyasi
async def main():
    dp.include_router(router)
    logger.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
