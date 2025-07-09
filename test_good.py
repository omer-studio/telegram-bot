
async def good_example():
    await send_message(update, chat_id, "תשובה")
    
    # כל השאר ברקע
    asyncio.create_task(background_processing())
