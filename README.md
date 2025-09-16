<div align="center">
  <h1 align="center">YouTube Discord Bridge</h1>
  <p align="center">
    This is a Discord bot capable of relaying messages from a live YouTube video to a chosen channel in a Discord server.
  </p>
</div>

## Getting Started

### Prerequisites

* [Python3](https://www.python.org/downloads/)

### Installation

1. Make a new project in [Google Cloud](https://console.cloud.google.com), enable the [YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com), then get a free API key. Guides for this can be found online.
2. Make a new bot in [Discord Developers](https://discord.com/developers/applications), invite it to your server, then save the bot token. Guides for this can be found online.
3. Clone the repo
   
   ```sh
   git clone https://github.com/wyattford/YT-Discord-Bridge.git
   ```
5. Install python dependencies
   
   ```sh
   pip install -r requirements.txt
   ```
6. Enter your YouTube API key and Discord bot token in `.env`
   
   ```env
   DISCORD_TOKEN=YOUR_DISCORD_TOKEN
   YOUTUBE_API_KEY=YOUR_YOUTUBE_API_KEY
   ```
8. Start the bot
   
   ```sh
   python bridge.py 
   ``` 

## Usage
All bot commands require moderator permissions (i.e. manage messages and manage channels)

* /setchannel {Channel name}
  * Allows users to set the active relay channel for the server
* /start {Video ID}
  * Allows users to start a relay session, providing the ID of a YouTube video
* /stop
  * Allows users to end a relay session

## Contact

Wyatt Ford - wyatt@wjford.dev

Project Link: [https://github.com/wyattford/YT-Discord-Bridge](https://github.com/wyattford/YT-Discord-Bridge)
