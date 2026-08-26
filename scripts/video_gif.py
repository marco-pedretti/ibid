"""Dal video della ripresa alla GIF che sta nel README (U-10).

`ui/scripts/video.mjs` registra un `.webm`; questo lo trasforma in una GIF che
GitHub mostra sempre, senza dipendere da come un client rende un `<video>`.

    python scripts/video_gif.py docs/demo.webm

## Il solo taglio, e dove cade

Il criterio di U-10 vieta i tagli che nascondono la latenza reale. Qui ce n'e'
**uno solo, in testa**: la registrazione comincia con l'applicazione che si
carica (`/datasets` costa ~2,5 s), e quei secondi di scheletro non sono il
copione. Il punto in cui tagliare non si indovina: lo dichiara il file
`*.tempi.json` che la ripresa lascia accanto al video, alla battuta «stato
vuoto». **Dentro il copione non si taglia niente**, e la riga dei tempi che si
vede a schermo dice quanto e' costata ogni fase.

## Perche' non `palettegen`/`paletteuse`

Sarebbe la strada abituale, e non e' disponibile: l'`ffmpeg` che Playwright si
porta dietro e' compilato al minimo (dodici filtri, nessun encoder GIF). Serve
solo a decodificare in PNG; la palette e l'animazione le fa Pillow, che c'e'
gia' come dipendenza di Streamlit. Se sul PATH c'e' un `ffmpeg` completo viene
preferito.

## Le tre scelte che decidono il peso

Misurate su questa ripresa, 44 secondi a 1280x800:

    1000 px, 128 colori, senza dithering   4,5 MB   <- scelta
    1000 px, 128 colori, con dithering     8,0 MB
    1000 px,  64 colori, senza dithering   3,6 MB
    disposal=2 invece di 1                40,5 MB

Il **dithering** su un'interfaccia di colori piatti aggiunge rumore che LZW non
sa comprimere, e in cambio non migliora niente: raddoppia il file. Il
**disposal** e' la scelta grossa: con `1` (lascia il fotogramma precedente)
Pillow scrive solo il rettangolo che cambia, e su una schermata ferma quel
rettangolo e' vuoto. Con `2` riscrive tutto ogni volta, e la GIF diventa dieci
volte piu' grande.

E i **fotogrammi identici si fondono** invece di ripetersi: durante le pause di
lettura non cambia un pixel, e una pausa di sette secondi costa un fotogramma
con una durata lunga invece di ottantaquattro uguali.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent.parent

#: Il tetto oltre il quale una GIF nel README diventa un peso per chi la apre e
#: per la storia del repository. Non e' un limite di GitHub: e' una scelta.
PESO_MAX_MB = 10.0

#: Il criterio di U-10, in secondi.
DURATA_MAX_S = 90.0


def _ffmpeg() -> str:
    """Un `ffmpeg` qualunque, purche' sappia decodificare in PNG.

    Prima quello di sistema, poi quello che Playwright scarica per registrare:
    e' minimo ma per estrarre fotogrammi basta, ed evita di chiedere
    un'installazione a chi ha gia' fatto `npx playwright install`.
    """
    trovato = shutil.which("ffmpeg")
    if trovato is not None:
        return trovato
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    candidati = sorted(base.glob("ffmpeg-*/ffmpeg-win64.exe")) if base.exists() else []
    if not candidati:
        candidati = sorted(Path.home().glob(".cache/ms-playwright/ffmpeg-*/ffmpeg-linux"))
    if not candidati:
        sys.exit(
            "ffmpeg non trovato: installalo, oppure esegui `npx playwright install ffmpeg` in ui/"
        )
    return str(candidati[-1])


def _inizio(video: Path, dichiarato: float | None) -> float:
    """Da dove parte il copione: il valore passato, o la prima battuta."""
    if dichiarato is not None:
        return dichiarato
    tempi = video.with_suffix("").with_suffix(".tempi.json")
    if not tempi.exists():
        print(f"  {tempi.name} non c'e': non taglio niente in testa")
        return 0.0
    battute = json.loads(tempi.read_text(encoding="utf-8"))["battute"]
    return float(battute[0]["s"]) if battute else 0.0


def _estrai(ff: str, video: Path, dove: Path, da: float, fps: int, larghezza: int) -> list[Path]:
    cmd = [ff, "-hide_banner", "-loglevel", "error"]
    if da > 0:
        cmd += ["-ss", f"{da:.2f}"]
    cmd += ["-i", str(video), "-r", str(fps), "-vf", f"scale={larghezza}:-1", "-y",
            str(dove / "%05d.png")]
    subprocess.run(cmd, check=True)
    return sorted(dove.glob("*.png"))


def _fondi(files: list[Path], passo_ms: int) -> tuple[list[Image.Image], list[int]]:
    """Fotogrammi distinti e la loro durata: gli identici consecutivi si fondono."""
    immagini: list[Image.Image] = []
    durate: list[int] = []
    prec: bytes | None = None
    for f in files:
        im = Image.open(f).convert("RGB")
        grezzo = im.tobytes()
        if prec is not None and grezzo == prec:
            durate[-1] += passo_ms
            continue
        prec = grezzo
        immagini.append(im)
        durate.append(passo_ms)
    return immagini, durate


def main() -> None:
    p = argparse.ArgumentParser(description="U-10: dalla ripresa alla GIF del README")
    p.add_argument("video", type=Path, help="il .webm prodotto da `npm run video`")
    p.add_argument("-o", "--out", type=Path, help="la GIF (default: accanto al video)")
    p.add_argument("--da", type=float, help="secondo da cui partire (default: la prima battuta)")
    p.add_argument("--fps", type=int, default=12)
    p.add_argument("--larghezza", type=int, default=1000)
    p.add_argument("--colori", type=int, default=128)
    args = p.parse_args()

    video: Path = args.video
    if not video.exists():
        sys.exit(f"{video} non c'e': registra prima con `npm run video` in ui/")
    out: Path = args.out or video.with_suffix(".gif")

    ff = _ffmpeg()
    da = _inizio(video, args.da)
    passo = round(1000 / args.fps)

    with tempfile.TemporaryDirectory() as tmp:
        files = _estrai(ff, video, Path(tmp), da, args.fps, args.larghezza)
        if not files:
            sys.exit("nessun fotogramma estratto: il video e' vuoto o ffmpeg non lo legge")
        immagini, durate = _fondi(files, passo)

    base = immagini[0].quantize(colors=args.colori, method=Image.MEDIANCUT)
    tavolozza = [im.quantize(palette=base, dither=Image.NONE) for im in immagini]

    tavolozza[0].save(
        out,
        save_all=True,
        append_images=tavolozza[1:],
        duration=durate,
        loop=0,
        optimize=True,
        disposal=1,
    )

    peso = out.stat().st_size / 1e6
    durata = sum(durate) / 1000
    print(
        f"{out.relative_to(ROOT) if out.is_absolute() else out}  "
        f"{peso:.2f} MB  {durata:.1f} s  "
        f"{len(files)} fotogrammi -> {len(tavolozza)} distinti  "
        f"{tavolozza[0].width}x{tavolozza[0].height}, {args.colori} colori"
    )
    if durata > DURATA_MAX_S:
        print(f"  ATTENZIONE: {durata:.1f} s, il criterio di U-10 dice novanta")
    if peso > PESO_MAX_MB:
        print(
            f"  ATTENZIONE: {peso:.1f} MB. Accorcia il copione prima di abbassare la\n"
            f"  qualita': una GIF illeggibile non dimostra niente."
        )


if __name__ == "__main__":
    main()
