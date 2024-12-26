# File Uploader Cog for Red Discord Bot

This project implements a file uploader cog for the Red Discord Bot, allowing users to upload files that remain private until a specified date. Users can extend the privacy duration or let the file be posted to a channel if the time expires.

## Features

- Upload files and keep them private until a configurable date.
- Extend the privacy duration of uploaded files.
- Automatically post files to a channel if the privacy duration expires.

## Setup Instructions

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/redbot-cog.git
   cd redbot-cog
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Load the cog into your Red Discord Bot:
   ```
   [p]load file_uploader
   ```

## Usage

### Commands

- **Upload File**
  - Command: `[p]upload_file <file>`
  - Description: Uploads a file and sets its privacy duration.

- **Set Privacy Duration**
  - Command: `[p]set_privacy_duration <duration>`
  - Description: Sets the duration for which the file remains private.

- **Extend Privacy Duration**
  - Command: `[p]extend_privacy_duration <duration>`
  - Description: Extends the privacy duration of the uploaded file.

- **Check Expiry**
  - Command: Automatically checks if the file's privacy duration has expired and posts it to the designated channel.

## File Structure

```
redbot-cog
├── cogs
│   └── file_uploader
│       ├── __init__.py
│       ├── file_uploader.py
│       └── data
│           └── files.json
├── requirements.txt
└── README.md
```

## Contributing

Feel free to submit issues or pull requests to improve the functionality of this cog.