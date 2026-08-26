"""Dal video della ripresa alla GIF che sta nel README (U-10).

`ui/scripts/video.mjs` registra un `.webm`; questo lo trasforma in una GIF che
GitHub mostra sempre, senza dipendere da come un client rende un `<video>`.

    python scripts/video_gif.py docs/demo.webm

## Il solo taglio, e dove cade

Il criterio di U-10 vieta i tagli che nascondono la latenza reale. Qui ce n'e'
**uno solo, in testa**: la registrazione comincia con l'applicazione che si
carica (`/datasets` costa ~2,5 s), e quei secondi di scheletro non sono il
copione. **Dentro il copione non si taglia niente**, e la riga dei tempi che si
vede a schermo dice quanto e' costata ogni fase.

Il punto in cui tagliare **si trova guardando i fotogrammi**, non l'orologio.
Il primo tentativo usava le battute che la ripresa registra in `*.tempi.json`,
ed era sbagliato: **la traccia video non e' allineata all'orologio dello
script**, e di quanto cambia da una ripresa all'altra (misurate 0,25 s e 3,4 s
su due riprese consecutive). Tagliare sul numero dello script lasciava dentro
lo scheletro intero.

Finche' l'applicazione carica, lo schermo non cambia di un pixel: il taglio
cade sul **primo fotogramma diverso dal primo**, con un quarto di secondo di
margine prima. Si autocalibra, e non ha bisogno di sapere quanto vale il
ritardo.

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


#: Quanta parte dell'immagine deve cambiare perche' sia «un altro schermo» e non
#: lo stesso con un pelo di rumore di codifica. Misurato su questa ripresa: fra
#: un fotogramma e l'altro del caricamento cambia lo 0,0% (zero pixel), quando
#: l'interfaccia compare cambia il **5%**.
_QUOTA_DIVERSA = 0.02

#: Nessun margine prima del cambiamento, e non e' una svista. Il primo
#: fotogramma di una GIF e' la locandina, quello che si vede fermo finche'
#: l'animazione non parte: deve essere **l'applicazione**, non l'ultimo
#: fotogramma del caricamento. Provato con un quarto di secondo e con un
#: fotogramma solo: in tutt'e due i casi si apriva su «Contatto il server».
_MARGINE_S = 0.0


def _primo_movimento(files: list[Path], passo_ms: int) -> float:
    """Il secondo in cui lo schermo smette di essere quello del caricamento.

    Serve perche' **la traccia video non e' allineata all'orologio della
    ripresa**, e lo scarto cambia da una volta all'altra: fra due riprese
    consecutive e' stato 0,25 s e 3,4 s. Finche' l'applicazione carica non
    cambia un pixel, quindi il primo fotogramma diverso da quello del
    caricamento e' il punto giusto **qualunque sia lo scarto**.
    """
    from PIL import ImageChops

    # Il riferimento non e' il primissimo fotogramma: quello e' la pagina ancora
    # bianca, diversa da tutti gli altri per costruzione. Mezzo secondo dopo lo
    # schermo e' quello del caricamento, che resta identico a se stesso finche'
    # l'applicazione non compare.
    i0 = min(len(files) - 1, round(0.5 * 1000 / passo_ms))
    riferimento = Image.open(files[i0]).convert("L")
    soglia = riferimento.width * riferimento.height * _QUOTA_DIVERSA
    for i, f in enumerate(files[i0 + 1 :], start=i0 + 1):
        im = Image.open(f).convert("L")
        # L'istogramma invece di contare i pixel a uno a uno: stessa risposta,
        # e non tocca `getdata()`, che Pillow ha deprecato.
        diversi = sum(ImageChops.difference(im, riferimento).histogram()[13:])
        if diversi > soglia:
            return max(0.0, i * passo_ms / 1000 - _MARGINE_S)
    return 0.0


def _estrai(ff: str, video: Path, dove: Path, da: float, fps: int, larghezza: int) -> list[Path]:
    # `-ss` **dopo** `-i`, e non prima: prima dell'ingresso ffmpeg salta al
    # fotogramma chiave piu' vicino, e un webm di Playwright ne ha pochissimi.
    # Con `-ss 2.98` in testa il taglio cadeva a zero e la GIF si apriva sullo
    # scheletro «Contatto il server», cioe' proprio cio' che il taglio doveva
    # togliere. Dopo l'ingresso il taglio e' esatto: decodifica e scarta.
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-i", str(video)]
    if da > 0:
        cmd += ["-ss", f"{da:.2f}"]
    cmd += ["-r", str(fps), "-vf", f"scale={larghezza}:-1", "-y", str(dove / "%05d.png")]
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


def _palette(immagini: list[Image.Image], colori: int) -> Image.Image:
    """Una tavolozza sola per tutta l'animazione, presa da **tutta** l'animazione.

    Ricavarla dal primo fotogramma sembra ovvio e produce una GIF di un
    fotogramma solo: il primo e' la pagina ancora bianca, la sua tavolozza ha
    due colori, e ogni fotogramma successivo ci finisce dentro appiattito fino a
    diventare identico agli altri. Pillow allora li fonde tutti, e il file esce
    di 1,4 kB.

    Il campione e' un mosaico di sedici fotogrammi presi a intervalli regolari:
    ci sono dentro la conversazione, l'esploratore e l'astensione, cioe' tutte
    le schermate che il copione attraversa.
    """
    passo = max(1, len(immagini) // 16)
    campioni = immagini[::passo][:16]
    larg = campioni[0].width // 4
    alt = campioni[0].height // 4
    mosaico = Image.new("RGB", (larg * 4, alt * 4))
    for i, im in enumerate(campioni):
        mosaico.paste(im.resize((larg, alt), Image.LANCZOS), ((i % 4) * larg, (i // 4) * alt))
    return mosaico.quantize(colors=colori, method=Image.MEDIANCUT)


def main() -> None:
    p = argparse.ArgumentParser(description="U-10: dalla ripresa alla GIF del README")
    p.add_argument("video", type=Path, help="il .webm prodotto da `npm run video`")
    p.add_argument("-o", "--out", type=Path, help="la GIF (default: accanto al video)")
    p.add_argument("--da", type=float, help="secondo da cui partire (default: dedotto, vedi sopra)")
    p.add_argument("--fps", type=int, default=12)
    p.add_argument("--larghezza", type=int, default=1000)
    p.add_argument("--colori", type=int, default=128)
    args = p.parse_args()

    video: Path = args.video
    if not video.exists():
        sys.exit(f"{video} non c'e': registra prima con `npm run video` in ui/")
    out: Path = args.out or video.with_suffix(".gif")

    ff = _ffmpeg()
    passo = round(1000 / args.fps)

    with tempfile.TemporaryDirectory() as tmp:
        files = _estrai(ff, video, Path(tmp), 0.0, args.fps, args.larghezza)
        if not files:
            sys.exit("nessun fotogramma estratto: il video e' vuoto o ffmpeg non lo legge")
        da = args.da if args.da is not None else _primo_movimento(files, passo)
        files = files[round(da * args.fps) :]
        immagini, durate = _fondi(files, passo)

    tavolozza = [im.quantize(palette=_palette(immagini, args.colori), dither=Image.NONE)
                 for im in immagini]

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
        f"taglio a {da:.2f} s, {len(files)} fotogrammi -> {len(tavolozza)} distinti  "
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
