# 🚀 Bit24 USDT Telegram Bot

A simple Telegram Bot that automatically fetches **real-time Tether (USDT) price** from the Iranian crypto exchange **Bit24** and posts updates directly to your Telegram channel.

> 🟢 **Live Example:**  
> Check the real bot running here: [Gheymatlahzeee Telegram Channel](https://t.me/Gheymatlahzeee)

---

## 📖 What This Bot Does
- 💵 Gets **real-time USDT price** (buy & sell) from **Bit24** exchange.  
- 📢 Sends the price automatically to your **Telegram channel**.  
- 🔄 Keeps updating at your chosen time interval.  

---

## 🛠 Requirements
- **Python 3** installed on your computer  
  [Download Python](https://www.python.org/downloads/)  
- A **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)  
- A **Telegram Channel ID** (like `@mychannel`)

---

## ⚙️ How to Install & Run (Step by Step)

### 1️⃣ Download This Project  
Click the green **Code** button on top of this page → **Download ZIP** → Extract it.  
Or use Git:
```bash
git clone https://github.com/YourUsername/bit24-usdt-telegram-bot.git
cd bit24-usdt-telegram-bot
```

### 2️⃣ Install the Required Libraries  

Open your terminal or command prompt inside the folder and run:  

```bash
pip install -r requirements.txt
```
(This will install python-telegram-bot and requests automatically.)

3️⃣ Set Your Bot Credentials

In the project folder, create a new file named .env and put this inside:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHANNEL_ID=@your_channel_username_here
```
4️⃣ Run the Bot
In your terminal:
```
python bot.py
```
5️⃣ Done! 🎉

Your bot will now fetch the USDT price from Bit24 and post it to your channel.

📝 Configuration (Optional)

Edit the update interval in bot.py (default: every few minutes).

Add more coins (BTC, ETH, etc.) by copying the function that fetches USDT and changing the endpoint.

🧰 Technologies Used

Python 3
```
Telegram Bot API (python-telegram-bot library)

Requests (HTTP requests to Bit24 API)
```
🔮 Future Ideas

Add more currencies (BTC, ETH, DOGE, etc.)

Send alerts when price crosses a certain limit.

Show charts in the channel.

🤝 Contributing

Pull requests are welcome! Please open an issue first to discuss what you would like to change.

📄 License

This project is licensed under the MIT License.

🆘 Need Help?

If you get stuck:

Make sure Python 3 is installed correctly.

Make sure your bot is added as Admin to your channel.

Check your ```.env``` file for correct token and channel ID.

Enjoy your new bot! 🚀
