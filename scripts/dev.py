#!/usr/bin/env python3
"""Il giro di sviluppo in un comando solo: backend + frontend.

`make api-local` in un terminale e `make ui` nell'altro funziona, ma sono due
finestre e un ordine da ricordare -- e chi dimentica la prima vede il frontend
dire «Backend non raggiungibile» senza capire perche'.

Qui Qdrant viene acceso se e' fermo, l'API parte, si **aspetta** che risponda, e
solo allora parte Vite.
L'attesa non e' cortesia: senza, il primo `/datasets` parte contro una porta
chiusa e la pagina si apre gia' in stato di guasto, che chi guarda legge come un
bug del frontend.

In Python e non in uno script di shell perche' e' l'unica cosa che questo
progetto garantisce su entrambe le piattaforme: uno `.ps1` andrebbe riscritto
per U-12, e due copie di un comando divergono.

**Non e' il modo in cui il progetto si consegna.** Quello e'
`docker compose --profile demo up` (U-08), dove l'API serve il frontend gia'
costruito e il proxy non esiste. Questo serve a chi modifica il codice.

Usage:
    python scripts/dev.py
    python scripts/dev.py --api-port 8001 --ui-port 5174
    python scripts/dev.py --no-install     # salta `npm install`
    python scripts/dev.py --senza-qdrant   # parti anche senza indice
"""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# L'indirizzo di Qdrant si legge da dove e' gia' scritto: `QDRANT_URL` ha un
# default in `src/config.py`, e ricopiarlo qui sarebbe la sedicesima copia a
# mano di una costante -- la lezione di Q-06.
import src.config as cfg  # noqa: E402

UI = ROOT / "ui"


def libera(porta: int) -> bool:
    """Vero se nessuno e' gia' in ascolto su `porta`.

    Serve **prima** di avviare, e la ragione l'ha insegnata un guasto vero: con
    un backend rimasto vivo da un avvio precedente, uvicorn muore per porta
    occupata ma `aspetta()` trova `/health` che risponde -- e' il **vecchio** che
    risponde. Il comando prosegue, la pagina funziona, e le modifiche al codice
    non compaiono mai. Un guasto che si maschera da successo e' peggio di uno
    rumoroso, quindi si controlla prima invece di dedurlo dopo.
    """
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", porta)) != 0


def risponde(url: str, secondi: float = 2) -> bool:
    """Vero se `url` risponde subito. Una domanda sola, non un'attesa."""
    try:
        with urllib.request.urlopen(url, timeout=secondi):
            return True
    except (urllib.error.URLError, OSError):
        return False


def accendi_qdrant() -> bool:
    """Prova ad avviare il servizio `qdrant` di `compose.yml`. Vero se risponde.

    **Si avvia, non si chiede.** Il container e' dichiarato in questo repo, sta
    su una porta di questo repo e contiene i dati di questo repo: accenderlo non
    e' un'iniziativa, e' la stessa cosa che `make dev` fa gia' con altri due
    processi. Cio' che non fa e' **aprire Docker Desktop**: e' un'applicazione
    con interfaccia, ci mette un minuto, e il comando per avviarla e' diverso su
    ognuno dei tre sistemi che U-12 vuole supportare. Un avvio che dipende da
    quale sistema operativo ha chi lo lancia e' la cosa che quello script deve
    evitare, non produrre.

    `start` prima di `up`: riaccende il container esistente senza ricrearlo, e
    quindi senza scaricare un'immagine che potrebbe avere un tag diverso da
    quella con cui era stato creato.
    """
    if not shutil.which("docker"):
        print(f"Qdrant non risponde su {cfg.QDRANT_URL} e `docker` non e' nel PATH.\n"
              "  installa Docker, oppure fai puntare QDRANT_URL a un'istanza gia' viva",
              file=sys.stderr)
        return False

    print("-> Qdrant non rispondeva: lo avvio")
    for comando in (["start", "qdrant"], ["up", "-d", "qdrant"]):
        esito = subprocess.run(
            ["docker", "compose", "--profile", "full", *comando],
            cwd=ROOT, capture_output=True, text=True,
        )
        if esito.returncode == 0 and aspetta(f"{cfg.QDRANT_URL}/readyz", 30):
            return True

    print(f"non sono riuscito ad avviare Qdrant. {esito.stderr.strip()[:300]}\n"
          "  Docker Desktop e' acceso? Questo script non lo apre di proposito:\n"
          "  e' un'applicazione con interfaccia e il comando per avviarla cambia\n"
          "  su ogni sistema.\n"
          "  poi riprova, oppure: python scripts/dev.py --senza-qdrant",
          file=sys.stderr)
    return False


def aspetta(url: str, secondi: float) -> bool:
    """Vero appena `url` risponde. Interroga, non dorme e spera."""
    scadenza = time.monotonic() + secondi
    while time.monotonic() < scadenza:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.4)
    return False


def assicura_taglie() -> None:
    """Crea le finestre di contesto mancanti, in silenzio se non c'e' niente da fare.

    Non solleva mai: un motore irraggiungibile o non-Ollama non deve impedire
    l'avvio dello sviluppo. Il selettore in quel caso resta spento, e la
    pastiglia dice perche' -- vedi `MenuFinestre`.
    """
    try:
        from scripts.model_sizes import assicura
    except Exception:
        return
    try:
        n = assicura()
    except Exception:
        return
    if n:
        print(f"-> {n} finestre di contesto create")


def main() -> int:
    p = argparse.ArgumentParser(description="backend + frontend in un comando")
    p.add_argument("--api-port", type=int, default=8000)
    p.add_argument("--ui-port", type=int, default=5173)
    p.add_argument("--no-install", action="store_true",
                   help="non lanciare `npm install` anche se manca node_modules")
    p.add_argument("--senza-qdrant", action="store_true",
                   help="parti anche se l'indice non risponde")
    args = p.parse_args()

    occupate = [p for p in (args.api_port, args.ui_port) if not libera(p)]
    if occupate:
        print(
            f"gia' in ascolto su {', '.join(map(str, occupate))}: c'e' un avvio "
            "precedente ancora vivo.\n"
            "  Windows:  Get-NetTCPConnection -LocalPort "
            f"{','.join(map(str, occupate))} -State Listen | "
            "%{ Stop-Process -Id $_.OwningProcess -Force }\n"
            "  Linux:    kill $(lsof -ti :" + ",".join(map(str, occupate)) + ")\n"
            "  oppure:   python scripts/dev.py --api-port 8001 --ui-port 5174",
            file=sys.stderr,
        )
        return 1

    # Qdrant **prima** di avviare qualcosa. Senza, l'API parte lo stesso (il suo
    # `/health` non interroga l'indice, di proposito: e' cio' che permette a
    # U-09 di usarlo come sonda anche quando Qdrant parte dopo), la pagina si
    # apre, e il guasto compare tre livelli piu' in la' come un traceback dentro
    # `/datasets` — cioe' lontanissimo dalla causa, che e' «manca un servizio».
    if not args.senza_qdrant and not risponde(f"{cfg.QDRANT_URL}/readyz"):
        if not accendi_qdrant():
            return 1

    # L'LLM **non** ferma l'avvio, e la differenza non e' di gusto: senza indice
    # non funziona niente, senza modello si sfoglia il corpus, si cambia dataset
    # e il recupero risponde — cade solo la generazione. Trattarli allo stesso
    # modo impedirebbe di lavorare sull'interfaccia mentre la GPU e' occupata da
    # una run di valutazione, che e' meta' del lavoro di Fase 8.
    if not risponde(f"{cfg.LLM_BASE_URL}/models"):
        print(
            f"! l'LLM non risponde su {cfg.LLM_BASE_URL}: i dataset e il recupero "
            "funzionano, le risposte no.\n"
            "  avvialo:  ollama serve   (oppure apri Ollama)",
            file=sys.stderr,
        )

    npm = shutil.which("npm")
    if not npm:
        print("npm non e' nel PATH. Installa Node.js 20+ e riapri il terminale.\n"
              "  winget install OpenJS.NodeJS.LTS", file=sys.stderr)
        return 1

    if not (UI / "node_modules").exists() and not args.no_install:
        print("-> npm install (prima volta)")
        if subprocess.run([npm, "install"], cwd=UI).returncode != 0:
            return 1

    print(f"-> API su http://127.0.0.1:{args.api_port}")
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api.main:app",
         "--host", "127.0.0.1", "--port", str(args.api_port)],
        cwd=ROOT,
    )
    try:
        # Le taglie di contesto (U-16) sono modelli derivati, e chi usa la demo
        # non deve saperlo: senza questo passo il selettore c'e' e non ha niente
        # da offrire, cioe' la funzione non esiste finche' non si legge la
        # documentazione giusta. Idempotente, quindi dalla seconda volta non
        # costa niente; e best-effort, perche' su un motore che non e' Ollama --
        # o che sta su un'altra macchina -- semplicemente non si fa.
        assicura_taglie()

        if not aspetta(f"http://127.0.0.1:{args.api_port}/health", 60):
            print("l'API non ha risposto entro 60 s: guarda i log qui sopra", file=sys.stderr)
            return 1

        # `localhost` e non `127.0.0.1`: Vite si lega a `::1`, e sull'indirizzo
        # IPv4 la connessione viene rifiutata. Stamparlo giusto qui evita il
        # quarto d'ora speso a cercare un guasto che non c'e'.
        print(f"-> UI su http://localhost:{args.ui_port}   (Ctrl-C ferma tutto)\n")
        esito = subprocess.run(
            [npm, "run", "dev", "--", "--port", str(args.ui_port), "--strictPort"],
            cwd=UI,
        ).returncode
        # Un codice negativo significa «terminato da un segnale», cioe' qualcuno
        # ha chiuso il server di sviluppo: e' il modo normale di finire, non un
        # guasto. Lasciarlo passare farebbe stampare a `make` un `*** Error` a
        # ogni uscita, e un errore che compare sempre smette di essere letto.
        return 0 if esito < 0 else esito
    except KeyboardInterrupt:
        return 0
    finally:
        # Il backend e' figlio di questo processo: se non lo si ferma qui, resta
        # in ascolto sulla porta e il prossimo avvio fallisce con un messaggio
        # che parla di porta occupata invece che di questo.
        api.terminate()
        try:
            api.wait(timeout=10)
        except subprocess.TimeoutExpired:
            api.kill()
        print("\nfermati.")


if __name__ == "__main__":
    raise SystemExit(main())
