# Tennis DX

[English](README.md) · **Español**

Colorización para Game Boy Color del *Tennis* de Game Boy (Nintendo, 1989), al estilo de las versiones "DX". El mismo juego y los mismos gráficos: solo cambia el color. En una Game Boy clásica se ve y se juega exactamente igual que el cartucho.

<p align="center">
<img width="640" height="576" alt="Pantalla de título" src="https://github.com/user-attachments/assets/dae862c3-f845-455d-a0ea-bc72641fc45f" />
</p>

<img width="1044" height="1052" alt="Las cuatro pistas" src="https://github.com/user-attachments/assets/8a987d4b-4226-418d-a14f-e73b21951ffa" />

<img width="1044" height="1052" alt="Pantallas de presentación" src="https://github.com/user-attachments/assets/6329d662-9b7d-423f-b6dc-0cbe7a5fb60d" />

<img width="1044" height="1458" alt="Original y DX" src="https://github.com/user-attachments/assets/997d298d-3116-4f1b-9626-6b157a069cbd" />

## Qué incluye

- Una pista por nivel: tierra batida, pista dura, moqueta y hierba.
- Color en los jugadores, el público, Mario árbitro, el marcador y la pelota.
- Funciona en partidas de 2 jugadores por cable link.

## Jugar

Aplica `tennis_dx.ips` (en *Releases*) a tu volcado de *Tennis (World)*, SHA1 `ec45a932fb3fc21394fef5e27e7fe9eccd0c7f70`, con Floating IPS, Lunar IPS o el parcheador web de ROMhacking.net.

Funciona en emuladores de GBC (SameBoy, BGB, Emulicious, mGBA) y en hardware real con un flashcart.

## Compilar

Necesitas RGBDS 0.8, Python 3 (`pip install -r requirements.txt`) y la ROM original con el nombre `baserom.gb`.

```
make          # build/tennis_dx.gbc
make ips      # build/tennis_dx.ips
make test     # pruebas
```

Los colores están en `tools/palettes.py`. Este repositorio no contiene nada del juego original: sus gráficos se leen de tu `baserom.gb` al compilar.

## Aviso

*Tennis* es un juego de Nintendo. Este es un proyecto de aficionados, sin relación con Nintendo. No se distribuye la ROM del juego.
