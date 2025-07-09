
async def bad_example():
    await send_message(update, chat_id, "תשובה")
    requests.post("http://example.com")  # blocking!
    calculate_costs(result)  # blocking!
    save_to_database(data)  # blocking!
