import os
import asyncio
import threading
import gradio as gr
from main import bot, dp, router

# Gradio interfeysi - Hugging Face faol deb bilishi va to'xtab qolmasligi uchun
def get_status():
    return "Bot muvaffaqiyatli ishlamoqda! 🚀"

with gr.Blocks(title="Telegram Bot Status") as demo:
    gr.Markdown("# 🤖 Telegram Qabul Boti")
    status_output = gr.Textbox(value=get_status(), label="Holat", interactive=False)
    gr.Markdown("Ushbu sahifa botni doimiy faol ushlab turish uchun xizmat qiladi.")

def run_bot_in_background():
    # Yangi asyncio loop yaratamiz, chunki Gradio alohida oqimda ishlaydi
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def start_bot():
        dp.include_router(router)
        print("Bot Hugging Face platformasida ishga tushmoqda...")
        await dp.start_polling(bot)
        
    loop.run_until_complete(start_bot())

# Botni fondagi oqimda (background thread) ishga tushiramiz
threading.Thread(target=run_bot_in_background, daemon=True).start()

if __name__ == "__main__":
    # Hugging Face default porti 7860
    demo.launch(server_name="0.0.0.0", server_port=7860)
