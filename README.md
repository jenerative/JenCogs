# JenCogs

JenCogs is a collection of cogs for Red-DiscordBot that provide various functionalities to enhance your Discord server.

## Cogs

### ExposureCountdown

(CURRENTLY NONFUNCTIONAL)
ExposureCountdown is a cog that lets users upload a private file/link and set a countdown. They can check in at any point to restart the countdown, but if they don't, it'll be made public.

#### Features

- Upload files/links privately with countdown
- Restart coundowns with command
- Check calendar for countdowns ending soon

### NickNamer

NickNamer is a cog that allows a configurable role to temporarily change other users' nicknames if they have another configurable role.

#### Features

- Temporarily rename a user with the `doll` command.
- Automatically revert nicknames after a specified duration.
- Revert nicknames if the user changes their nickname while under the effect of the `doll` command.
- Configure settings such as the default nickname, modlog entries, and required roles.

### ReactionLinker

Add a configurable reaction to any of a user's messages to be taken to their most recent message in a configurable channel.

#### Features

- `[p]reactionlinkerset channel` to set channel to track for users' last posts
- `[p]reactionlinkerset emoji` to set emoji to watch for as reactions
- Bot will DM users the link when reaction is added
- Bot will delete the reaction after link is sent

### RelationshipRegistry

RelationshipRegistry allows users to set a relationship with other users and have it posted in a configurable channel.

#### Features

- Add relationship with another user
- Relationships get posted in a configurable channel
- Either member of the relationship can delete it


## Installation

1. Ensure you have Red-DiscordBot installed and properly configured.
2. Add the repo with the command `[p]repo add JenCogs https://github.com/jenerative/JenCogs`
3. Install the cog you want with `[p]cog install JenCogs [cogName]`