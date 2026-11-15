# Tennis DX

A colour version of Game Boy *Tennis* (Nintendo, 1989), in the style of the "DX" editions. The game is the original: same rules and same graphics; only the colour changes. For private use.

One ROM for everything:

- **Game Boy Color:** the DX version in colour.
- **Super Game Boy and SGB2:** one palette per level (and a custom border, if you provide one), with the same fixes as on the original Game Boy.
- **Original Game Boy:** like the original cartridge, with two fixes: the opponent's eyes and shoes are no longer transparent (except on the second console of a 2-player game, whose palette for them has no white), and the FAULT / OUT sign fills its right-hand strip.

On all three, switching between the scoreboard and the court no longer flashes leftovers from the previous screen (players, text, the stands), a bug in the original game: the screen stays white for a few frames until everything is in place. On Game Boy Color, the last frame of each screen is shown whole too, sprites included.

## What's included

- One court per level, from slowest to fastest: clay, hard court, carpet and grass. Clay and grass get a dotted surface.
- The title screen shows the floor and wall of the court about to be played.
- Colour on the players, the crowd, Mario the umpire, the scoreboard, the ball and the FAULT / OUT sign. The sign comes up with its colours on its very first frame.
- 2-player matches over the link cable, with the same colours on both consoles.

## Playing

Apply `tennis_dx.ips` to your dump of *Tennis (World)*, SHA1 `ec45a932fb3fc21394fef5e27e7fe9eccd0c7f70`. It works in emulators (SameBoy, BGB, Emulicious, mGBA) and on hardware with a flash cart: the ROM uses the MBC5 chip and takes 64 KiB. In BGB, to see the Super Game Boy version: *Options → System → GB type: SGB*.

## Building

You need RGBDS 0.8, Python 3 (`pip install -r requirements.txt`) and the original ROM named `baserom.gb`.

```
make          # build/tennis_dx.gbc
make ips      # build/tennis_dx.ips
make test     # tests
make dist     # dist/: ROM, patch and source
```

- Game Boy Color colours: `tools/palettes.py`.
- Super Game Boy palettes: `SGB_*` in `tools/palettes.py`.
- Super Game Boy border (optional, not included): `tools/data/sgb_border.png` (256 × 224, at most 15 colours, magenta for the game's window). Without it, the Super Game Boy shows its usual border.

The game's graphics are not stored with the source: they are read from `baserom.gb` at build time.
