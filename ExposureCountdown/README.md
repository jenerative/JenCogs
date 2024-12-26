# Exposure Countdown Cog for Red Discord Bot

This project implements an Exposure Countdown cog for the Red Discord Bot, allowing users to upload files that remain private until a specified date. Users can extend the privacy duration or let the file be posted to a channel if the time expires.

## Features

- Upload files and keep them private until a configurable date.
- Extend the privacy duration of uploaded files.
- Automatically post files to a channel if the privacy duration expires.

## Setup Instructions

1. Add the repo:
   ```
   [p]repo add JenCogs https://github.com/jenerative/JenCogs
   ```

2. Install the cog:
   ```
   [p]cog install JenCogs ExposureCountdown
   ```

3. Load the cog into your Red Discord Bot:
   ```
   [p]load ExposureCountdown
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

## Contributing

Feel free to submit issues or pull requests to improve the functionality of this cog.