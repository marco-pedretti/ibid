"""Dal video della ripresa alla GIF che sta nel README (U-10).

`ui/scripts/video.mjs` registra un `.webm`; questo lo trasforma in una GIF che
GitHub mostra sempre, senza dipendere da come un client rende un `<video>`.

    python scripts/video_gif.py docs/demo.webm

## Due finestre su una ripresa sola

Il README mostra **due GIF**: la chat con le citazioni, e l'apertura della
fonte. Non sono due riprese: sono due ritagli dello stesso video continuo, ed e'
la ragione per cui restano onesti. Due riprese separate obbligherebbero la
seconda a partire da una risposta gia' pronta, cioe' a mostrare la schermata
senza l'attesa che l'ha prodotta.

    python scripts/video_gif.py docs/demo.webm --a "fonte aperta-1.4" -o docs/demo.gif
    python scripts/video_gif.py docs/demo.webm --da "fonte aperta-1.4" -o docs/fonte.gif

`--da` e `--a` prendono un secondo oppure **il nome di una battuta**, con uno
scostamento facoltativo (`"fonte aperta-1.4"`). Le battute le scrive la ripresa
in `*.tempi.json`, e **sono gia' sull'orologio del video**: verificato
cercando nel filmato i cambi di schermata piu' grossi, che cadono a 7,25 s
(domanda inviata), 24,33 s (fonte aperta) e 33,42 s (conversazione nuova),
contro 7,25 / 24,34 / 33,44 registrati dalla ripresa.

## Il solo taglio, e dove cade

Il criterio di U-10 vieta i tagli che nascondono la latenza reale. Qui ce n'e'
**uno solo, in testa**: la registrazione comincia con l'applicazione che si
carica (`/datasets` costa ~2,5 s), e quei secondi di scheletro non sono il
copione. **Dentro il copione non si taglia niente**, e la riga dei tempi che si
vede a schermo dice quanto e' costata ogni fase.

Il punto lo dichiara la prima battuta della ripresa, «stato vuoto». Quando il
file dei tempi non c'e', si ripiega su una ricerca nei fotogrammi: finche'
l'applicazione carica lo schermo non cambia, quindi il primo fotogramma diverso
da quello del caricamento e' il punto giusto.

**Il ripiego era la strada principale, e sbagliava.** In tema chiaro trovava il
momento giusto; in tema scuro il cambio di schermata sposta meno pixel, la
soglia non scattava, e il taglio finiva sul primo movimento successivo: tre
secondi piu' in la'. Da li' era nata anche la convinzione, sbagliata, che il
video fosse in ritardo sull'orologio dello script. Non lo e': i due orologi
coincidono, e la verifica sta qui sopra.

## Perche' non `palettegen`/`paletteuse`

Sarebbe la strada abituale, e non e' disponibile: l'`ffmpeg` che Playwright si
porta dietro e' compilato al minimo (dodici filtri, nessun encoder GIF). Serve
solo a decodificare in PNG; la palette e l'animazione le fa Pillow, che c'e'
gia' come dipendenza di Streamlit. Se sul PATH c'e' un `ffmpeg` completo viene
preferito.

## Le scelte che decidono qualita' e peso

Misurate sui venti secondi della prima GIF:

    1280 px, 256 colori, senza dithering   3,21 MB   <- scelta
    1280 px, 128 colori                    2,77 MB
    1000 px, 256 colori                    2,03 MB
    1000 px, 128 colori                    1,77 MB   <- com'era
    disposal=2 invece di 1                    x10
    APNG senza perdita                    18,7 MB

**La larghezza conta piu' dei colori.** Ridurre 1280 a 1000 ricampiona ogni
lettera, ed e' cio' che faceva sembrare le GIF «compresse»: a dimensione nativa
il testo e' quello che il browser ha disegnato. I 256 colori sono il massimo che
il formato regge e tolgono le bande dalle superfici scure, che con 128 si
appiattivano l'una sull'altra.

Il **dithering** su un'interfaccia di colori piatti aggiunge rumore che LZW non
sa comprimere, e in cambio non migliora niente: raddoppia il file. Il
**disposal** e' la scelta grossa: con `1` (lascia il fotogramma precedente)
Pillow scrive solo il rettangolo che cambia, e su una schermata ferma quel
rettangolo e' vuoto. Con `2` riscrive tutto ogni volta.

**Perche' GIF e non WebP**, che a parita' di qualita' peserebbe meno (2,94 MB a
qualita' 90) ed e' a 24 bit: perche' una GIF la disegna qualunque cosa apra un
README, e un'immagine rotta in cima alla pagina costa piu' di quanto valga il
megabyte risparmiato. APNG sarebbe senza perdita e pesa sei volte tanto.

E i **fotogrammi identici si fondono** invece di ripetersi: durante le pause di
lettura non cambia un pixel, e una pausa di sette secondi costa un fotogramma
con una durata lunga invece di ottantaquattro uguali.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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

    E' l'unico modo di trovarlo: la prima battuta della ripresa e' registrata
    quando l'elemento e' visibile nel DOM, che su questa applicazione precede la
    prima pittura di qualche secondo. Misurato: battuta a 3,00 s, interfaccia
    dipinta a 6,50 s, e tutte le battute successive invece allineate.
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


def _istante(spec: str | None, battute: list[dict], difetto: float) -> float:
    """Un secondo del video, da un numero o dal nome di una battuta.

    `"fonte aperta"` e' il momento in cui la ripresa ha registrato quella
    battuta; `"fonte aperta-1.4"` un secondo e quattro prima, che e' come si
    taglia **poco prima** di un gesto invece che subito dopo.
    """
    if spec is None:
        return difetto
    try:
        return float(spec)
    except ValueError:
        pass
    m = re.match(r"^(.*?)\s*([+-][0-9.]+)?$", spec)
    nome = (m.group(1) or "").strip() if m else ""
    delta = float(m.group(2)) if m and m.group(2) else 0.0
    for b in battute:
        if b["nome"] == nome:
            return b["s"] + delta
    noti = ", ".join(repr(b["nome"]) for b in battute)
    sys.exit(f"battuta sconosciuta: {nome!r}. Ci sono: {noti}")


def _battute(video: Path) -> list[dict]:
    """Le battute che la ripresa ha lasciato accanto al video, se ci sono."""
    tempi = video.with_suffix("").with_suffix(".tempi.json")
    if not tempi.exists():
        return []
    return list(json.loads(tempi.read_text(encoding="utf-8"))["battute"])


def _estrai(ff: str, video: Path, dove: Path, da: float, fps: int, larghezza: int) -> list[Path]:
    # `-ss` **dopo** `-i`, e non prima: prima dell'ingresso ffmpeg salta al
    # fotogramma chiave piu' vicino, e un webm di Playwright ne ha pochissimi.
    # Con `-ss 2.98` in testa il taglio cadeva a zero e la GIF si apriva sullo
    # scheletro «Contatto il server», cioe' proprio cio' che il taglio doveva
    # togliere. Dopo l'ingresso il taglio e' esatto: decodifica e scarta.
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-i", str(video)]
    if da > 0:
        cmd += ["-ss", f"{da:.2f}"]
    cmd += ["-r", str(fps)]
    # Zero significa **niente riscalatura**: e' il difetto, ed e' la differenza
    # che si vede di piu'. Ridurre 1280 a 1000 ricampiona ogni lettera, e su un
    # testo di dodici pixel il ricampionamento e' proprio cio' che fa sembrare
    # una GIF «compressa».
    if larghezza > 0:
        cmd += ["-vf", f"scale={larghezza}:-1"]
    cmd += ["-y", str(dove / "%05d.png")]
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
    p.add_argument("--da", help="secondo o battuta da cui partire (default: dedotto, vedi sopra)")
    p.add_argument("--a", help="secondo o battuta a cui fermarsi (default: la fine)")
    p.add_argument("--fps", type=int, default=12)
    p.add_argument("--larghezza", type=int, default=0, help="0 = quella della ripresa")
    p.add_argument("--colori", type=int, default=256, help="il massimo che il formato GIF regge")
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
        battute = _battute(video)
        # Il difetto e' **sempre** la ricerca nei fotogrammi, anche quando le
        # battute ci sono: la prima battuta e' l'unica che non corrisponde a
        # quello che il video mostra, per la ragione scritta piu' su.
        apertura = _primo_movimento(files, passo)
        da = _istante(args.da, battute, apertura)
        a = _istante(args.a, battute, len(files) * passo / 1000)
        if a <= da:
            sys.exit(f"la fine ({a:.2f} s) non e' dopo l'inizio ({da:.2f} s)")
        files = files[round(da * args.fps) : round(a * args.fps)]
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
    # `relative_to` solleva quando la GIF finisce fuori dal repository, che
    # capita provando parametri diversi in una cartella temporanea.
    try:
        nome = out.relative_to(ROOT)
    except ValueError:
        nome = out
    print(
        f"{nome}  "
        f"{peso:.2f} MB  {durata:.1f} s  "
        f"da {da:.2f} a {da + durata:.2f} s, {len(files)} fotogrammi -> {len(tavolozza)} distinti  "
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
