# Telegram Auto-Post Bot

This Telegram bot allows you to automatically send and schedule posts from a source channel to your own channel. The bot walks users through the setup process and handles authentication, including two-factor authentication (2FA), if enabled.

## Features

- Force join verification for users before accessing the bot
- Step-by-step setup asking for:
  - Footer text
  - Source channel
  - Destination channel
  - Phone number
  - API ID & API hash
  - Session name
  - Telegram code (sent to your account)
  - 2FA password if enabled
- Automatic login for accounts without 2FA
- Send and schedule up to 100 posts from a source channel to your own channel
- The bot must be added as an admin in your source channel

## How It Works

1. User starts the bot on Telegram
2. Bot enforces a force-join requirement
3. Bot asks sequential questions to gather all necessary credentials
4. User provides Telegram login code (and 2FA password if required)
5. Bot logs into the user account
6. Bot sends up to 100 posts from the source channel to the user's channel and schedules them automatically

## Requirements

- Telegram account
- Telegram API credentials (API ID & API hash)
- Admin access to source channel

## Usage

1. Start the bot on Telegram.
2. Follow the step-by-step prompts.
3. Add the bot as an admin to your source channel.
4. The bot will automatically schedule and send posts.

## Notes

- Maximum of 100 posts per session.
- Ensure you provide correct API credentials and 2FA password if prompted.
