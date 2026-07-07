import os
import re
import logging
from fastapi import FastAPI, Request, Response, status
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, Router, types, BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError
from typing import Callable, Dict, Any, Awaitable

REQUIRED_CHANNEL = "@shahrisabz_t_t_uz"
CHANNEL_URL = "https://t.me/shahrisabz_t_t_uz"

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

# DIQQAT: Vercel serverless muhitida MemoryStorage server o'chib-yonishi bilan tozalanadi.
# Ishlab chiqarish (production) uchun RedisStorage yoki tashqi ma'lumotlar bazasi tavsiya etiladi.
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# Foydalanuvchi kontaktlarini saqlash uchun vaqtinchalik xotira
# DIQQAT: Serverless sharoitida bu ma'lumotlar tez-tez o'chib ketadi.
# Ishlab chiqarishda ma'lumotlar bazasiga yozish kerak.
user_contacts = {}

# Keyboardlar
def get_main_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="📤 Hujjat topshirish")],
            [types.KeyboardButton(text="📞 Bog'lanish")]
        ],
        resize_keyboard=True
    )

def get_contact_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="📞 Telefon raqamini yuborish", request_contact=True)],
            [types.KeyboardButton(text="⬅️ Orqaga")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# 1. /start buyrug'i (Faqat shaxsiy chatlarda)
@router.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    welcome_text = (
        "👋 Assalomu alaykum!\n\n"
        "🏥 \"Shahrisabz Tibbiyot Texnikumi\"ning\n"
        "rasmiy qabul botiga xush kelibsiz.\n\n"
        "📋 Ushbu bot orqali siz:\n\n"
        "✅ Onlayn shartnoma rasmiylashtirishingiz\n"
        "✅ Kerakli hujjatlarni yuborishingiz\n"
        "✅ Arizangiz holatini kuzatishingiz mumkin.\n\n"
        "Boshlash uchun quyidagi tugmani bosing."
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

# 2. Orqaga qaytish handlingi
@router.message(F.text == "⬅️ Orqaga", F.chat.type == "private")
async def cmd_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Bosh menyu:", reply_markup=get_main_keyboard())

# 3. Bog'lanish tugmasi
@router.message(F.text == "📞 Bog'lanish", F.chat.type == "private")
async def cmd_contact_info(message: types.Message):
    contact_text = (
        "🏥 <b>Shahrisabz Tibbiyot Texnikumi bilan bog'lanish:</b>\n\n"
        "📞 <b>Telefon:</b> +998 97 587 46 57\n"
        "✈️ <b>Telegram:</b> @shahrisabz_t_t_uz\n"
        "📸 <b>Instagram:</b> <a href=\"https://www.instagram.com/shahrisabz_t_t_uz/\">@shahrisabz_t_t_uz</a>\n"
        "📍 <b>Manzil:</b> Shahrisabz shahri, Ipak Yuli ko'chasi, 36A-uy\n"
        "⏰ <b>Ish vaqti:</b> Dushanba-Juma 09:00-17:00"
    )
    await message.answer(contact_text, reply_markup=get_main_keyboard())

# 4. Hujjat topshirish bosqichini boshlash
@router.message(F.text == "📤 Hujjat topshirish", F.chat.type == "private")
async def start_apply(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    # Agar telefon raqami allaqachon olingan bo'lsa
    if user_id in user_contacts:
        await state.set_state(RegistrationStates.FullName)
        step_text = (
            "📄 Ma'lumotlarni ketma-ket kiriting.\n\n"
            "❗ Pasport ma'lumotlari va telefon raqamingizni\n"
            "xatosiz kiriting.\n\n"
            "Barcha ma'lumotlar tekshirilgandan so'ng\n"
            "administrator tomonidan ko'rib chiqiladi.\n\n"
            "✍️ Ism va Familiyangizni kiriting:"
        )
        await message.answer(step_text, reply_markup=types.ReplyKeyboardRemove())
    else:
        # Avval kontakt so'raymiz
        ask_contact_text = (
            "Ro'yxatdan o'tishni boshlash uchun pastdagi tugma orqali telefon raqamingizni yuboring."
        )
        await message.answer(ask_contact_text, reply_markup=get_contact_keyboard())

# 5. Kontakt qabul qilish (Faqat shaxsiy chatlarda)
@router.message(F.contact, F.chat.type == "private")
async def contact_handler(message: types.Message, state: FSMContext):
    phone_number = message.contact.phone_number
    user_contacts[message.from_user.id] = phone_number
    
    await state.set_state(RegistrationStates.FullName)
    step_text = (
        "📄 Ma'lumotlarni ketma-ket kiriting.\n\n"
        "❗ Pasport ma'lumotlari va telefon raqamingizni\n"
        "xatosiz kiriting.\n\n"
        "Barcha ma'lumotlar tekshirilgandan so'ng\n"
        "administrator tomonidan ko'rib chiqiladi.\n\n"
        "✍️ Ism va Familiyangizni kiriting:"
    )
    await message.answer(step_text, reply_markup=types.ReplyKeyboardRemove())

# 6. FSM: Ism va Familiya qabul qilish
@router.message(RegistrationStates.FullName, F.text)
async def process_fullname(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await state.set_state(RegistrationStates.SecondPhone)
    await message.answer(
        "📞 Qo'shimcha shaxsiy telefon raqamingizni kiriting:\n"
        "(Masalan: +998901234567)"
    )

# 7. FSM: Qo'shimcha telefon raqami qabul qilish
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

# 8. FSM: Pasport nusxasi qabul qilish
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

# 9. FSM: Diplom nusxasi qabul qilish va guruhga yuborish
@router.message(RegistrationStates.DiplomaPhoto, F.photo)
async def process_diploma_photo(message: types.Message, state: FSMContext):
    diploma_photo_file_id = message.photo[-1].file_id
    user_data = await state.get_data()
    
    # Barcha ma'lumotlarni yig'amiz
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
    full_name = user_data.get('full_name', "Noma'lum")
    main_phone = user_contacts.get(user_id, "Noma'lum")
    second_phone = user_data.get('second_phone', "Noma'lum")
    passport_photo_file_id = user_data.get('passport_photo')
    
    # FSM ni tozalaymiz
    await state.clear()
    
    # Foydalanuvchiga muvaffaqiyatli yakunlangani haqida xabar beramiz
    success_text = (
        "✅ Ma'lumotlaringiz muvaffaqiyatli qabul qilindi!\n\n"
        "📌 Tez orada administrator siz bilan bog'lanadi.\n\n"
        "Shahrisabz Tibbiyot Texnikumini tanlaganingiz uchun rahmat!"
    )
    await message.answer(
        success_text,
        reply_markup=get_main_keyboard()
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
        if passport_photo_file_id:
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

# A'zolikni tekshirish helper funksiyasi
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ["member", "creator", "administrator"]:
            return True
        return False
    except Exception as e:
        logger.error(f"Subscription check error for user {user_id}: {e}")
        # API xatolik yuz bersa foydalanuvchini bloklamaslik uchun True qaytaramiz
        return True

# A'zolikni tekshirish uchun Middleware
class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        chat = data.get("event_chat")
        
        # Agar a'zolikni tekshirish callback so'rovi bo'lsa, o'tkazib yuboramiz
        if isinstance(event, types.CallbackQuery) and event.data == "check_sub":
            return await handler(event, data)
            
        if user and chat and chat.type == "private":
            is_subscribed = await check_subscription(user.id)
            if not is_subscribed:
                keyboard = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [types.InlineKeyboardButton(text="👥 Guruhga a'zo bo'lish", url=CHANNEL_URL)],
                        [types.InlineKeyboardButton(text="✅ A'zolikni tekshirish", callback_data="check_sub")]
                    ]
                )
                warning_text = (
                    "⚠️ <b>Botdan foydalanish uchun avval rasmiy guruhimizga a'zo bo'ling!</b>\n\n"
                    "A'zo bo'lgach, \"A'zolikni tekshirish\" tugmasini bosing."
                )
                if isinstance(event, types.Message):
                    await event.answer(warning_text, reply_markup=keyboard)
                elif isinstance(event, types.CallbackQuery):
                    await event.message.answer(warning_text, reply_markup=keyboard)
                    await event.answer()
                return
                
        return await handler(event, data)

# A'zolikni tekshirish callback handlingi
@router.callback_query(F.data == "check_sub")
async def callback_check_sub(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_subscribed = await check_subscription(user_id)
    if is_subscribed:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer("✅ Rahmat! A'zolik tasdiqlandi.", show_alert=True)
        welcome_text = (
            "👋 Assalomu alaykum!\n\n"
            "🏥 \"Shahrisabz Tibbiyot Texnikumi\"ning\n"
            "rasmiy qabul botiga xush kelibsiz.\n\n"
            "📋 Ushbu bot orqali siz:\n\n"
            "✅ Onlayn shartnoma rasmiylashtirishingiz\n"
            "✅ Kerakli hujjatlarni yuborishingiz\n"
            "✅ Arizangiz holatini kuzatishingiz mumkin.\n\n"
            "Boshlash uchun quyidagi tugmani bosing."
        )
        await callback.message.answer(welcome_text, reply_markup=get_main_keyboard())
    else:
        await callback.answer("❌ Siz hali guruhga a'zo bo'lmagansiz!", show_alert=True)

# Middleware-larni ro'yxatdan o'tkazamiz
router.message.outer_middleware(SubscriptionMiddleware())
router.callback_query.outer_middleware(SubscriptionMiddleware())

dp.include_router(router)

# FastAPI ilovasini yaratamiz
app = FastAPI()

@app.get("/")
async def root():
    return {
        "status": "active",
        "description": "FastAPI Webhook for Telegram Qabul Bot"
    }

@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        update_data = await request.json()
        update = types.Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return Response(status_code=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Webhook-ni o'rnatish uchun endpoint (Vercel-ga deploy qilingandan so'ng 1 marta chaqiriladi)
# Masalan: https://domain-name.vercel.app/setup-webhook
@app.get("/setup-webhook")
async def setup_webhook(request: Request):
    # Vercel domenini avtomatik aniqlash yoki query param orqali olish
    url = request.query_params.get("url")
    if not url:
        # Vercel-da xostni aniqlaymiz
        host = request.headers.get("host")
        if host:
            url = f"https://{host}"
        else:
            return {"status": "error", "message": "Domen nomini aniqlab bo'lmadi. 'url' query parametrini bering."}

    webhook_url = f"{url}/webhook"
    try:
        await bot.set_webhook(webhook_url)
        return {"status": "success", "message": f"Webhook muvaffaqiyatli o'rnatildi: {webhook_url}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
