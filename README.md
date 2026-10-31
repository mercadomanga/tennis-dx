# Tennis DX

Versión a color del *Tennis* de Game Boy (Nintendo, 1989), al estilo de las ediciones "DX". El juego es el original: mismas reglas y mismos gráficos; solo cambia el color. Uso privado.

Una sola ROM vale para todo:

- **Game Boy Color:** la versión DX a color.
- **Super Game Boy y SGB2:** una paleta por nivel y el borde de Game Boy clásica.
- **Game Boy clásica:** idéntica al cartucho original.

## Qué incluye

- Una pista por nivel, de la más lenta a la más rápida: tierra batida, pista dura, moqueta y hierba. La tierra batida y la hierba llevan el suelo punteado.
- La pantalla de presentación con el suelo y la pared de la pista que se va a jugar.
- Color en los jugadores, el público, Mario árbitro, el marcador, la pelota y el cartel de FAULT / OUT.
- Partidas de 2 jugadores por cable link con los mismos colores en las dos consolas.

## Jugar

Aplica `tennis_dx.ips` a tu volcado de *Tennis (World)*, SHA1 `ec45a932fb3fc21394fef5e27e7fe9eccd0c7f70`. Funciona en emuladores (SameBoy, BGB, Emulicious, mGBA) y en consola con un flashcart: la ROM usa el chip MBC5 y ocupa 64 KiB. En BGB, para ver la versión de Super Game Boy: *Options → System → GB type: SGB*.

## Compilar

Necesitas RGBDS 0.8, Python 3 (`pip install -r requirements.txt`) y la ROM original con el nombre `baserom.gb`.

```
make          # build/tennis_dx.gbc
make ips      # build/tennis_dx.ips
make test     # pruebas
make dist     # dist/: ROM, parche y código
```

- Colores de Game Boy Color: `tools/palettes.py`.
- Paletas de Super Game Boy: `SGB_*` en `tools/palettes.py`.
- Borde de Super Game Boy: `tools/data/sgb_border.png` (256 × 224, 15 colores como máximo, magenta en la ventana del juego).

Los gráficos del juego no se guardan con el código: al compilar se leen de `baserom.gb`.
