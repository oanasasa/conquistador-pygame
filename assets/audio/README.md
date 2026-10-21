# Game sounds

Put the sound files here. Each is optional: a missing file is simply silent.
Use `.ogg`, `.wav` or `.mp3` with these names:

| File | When it plays |
|---|---|
| `lobby` | Music, looped while players are in the menus and halls; fades out when the battle starts |
| `tick` | Each second while a riddle is open |
| `tick_urgent` | Each of a riddle's last three seconds (uses `tick` if missing) |
| `bell` | When a riddle ends and the pause card appears |
| `horn` | When it is your turn to choose land |

Keep effects short (under a second; the bell can ring a little longer) and
make sure you have the right to use each file (your own, CC0, or a license
that allows it). Press `M` in the game to mute.
