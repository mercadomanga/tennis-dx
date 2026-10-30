# Tennis DX

**English** · [Español](README.es.md)

A Game Boy Color colorization of *Tennis* for the Game Boy (Nintendo, 1989), in the style of the "DX" releases. Same game, same graphics: only the colour changes. On a classic Game Boy it looks and plays exactly like the cartridge.

<p align="center">
<img width="640" height="576" alt="Title screen" src="https://github.com/user-attachments/assets/dae862c3-f845-455d-a0ea-bc72641fc45f" />
</p>

<img width="1044" height="1052" alt="The four courts" src="https://github.com/user-attachments/assets/8a987d4b-4226-418d-a14f-e73b21951ffa" />

<img width="1044" height="1052" alt="Score board screens" src="https://github.com/user-attachments/assets/6329d662-9b7d-423f-b6dc-0cbe7a5fb60d" />

<img width="1044" height="1458" alt="Original and DX side by side" src="https://github.com/user-attachments/assets/997d298d-3116-4f1b-9626-6b157a069cbd" />

## Features

- One court per level: clay, hard court, carpet and grass.
- Coloured players, crowd, Mario the umpire, score box and ball.
- Works in 2-player games over the link cable.

## Play

Apply `tennis_dx.ips` (see *Releases*) to your own dump of *Tennis (World)*, SHA1 `ec45a932fb3fc21394fef5e27e7fe9eccd0c7f70`, with Floating IPS, Lunar IPS or the ROMhacking.net web patcher.

Runs on GBC emulators (SameBoy, BGB, Emulicious, mGBA) and on real hardware with a flashcart.

## Build

Needs RGBDS 0.8, Python 3 (`pip install -r requirements.txt`) and the original ROM as `baserom.gb`.

```
make          # build/tennis_dx.gbc
make ips      # build/tennis_dx.ips
make test     # regression tests
```

Colours are in `tools/palettes.py`. This repository contains nothing from the original game; its graphics are read from your `baserom.gb` at build time.

## Disclaimer

*Tennis* is a Nintendo game. This is a fan project, not affiliated with Nintendo. The game's ROM is not distributed.
