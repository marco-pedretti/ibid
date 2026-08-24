"""Crea le taglie di contesto di un modello, per il selettore di U-16.

    python scripts/model_sizes.py --assicura            # tutte, e non chiede
    python scripts/model_sizes.py gemma4:e2b 8192 32768 # una a mano
    python scripts/model_sizes.py --rimuovi gemma4:e2b 8192
    python scripts/model_sizes.py --pulisci             # via tutte, elenco e conferma

**Le taglie nascono sotto `ibid/`** (A-09): `ibid/gemma4-e2b:32k`. Sono modelli
a tutti gli effetti e compaiono in `ollama list` -- Ollama non sa nasconderli --
ma almeno si vede di chi sono e si tolgono in blocco.

**Perche' uno script e non un campo della richiesta.** La finestra di contesto
non esiste sul contratto OpenAI: misurato il 2026-08-19, `num_ctx` mandato a
`/v1/chat/completions` riceve 200 e viene ignorato -- che e' peggio di un
rifiuto, perche' un controllo costruito li' sembrerebbe funzionare. Un
`PARAMETER num_ctx` nel Modelfile invece ha effetto **attraverso** quello stesso
endpoint. Quindi la finestra viaggia col nome del modello, e questo script e' il
posto dove quei nomi nascono. Il ragionamento per esteso sta in ROADMAP, A-08.

**`--assicura` e' il modo normale, e nessuno dovrebbe lanciarlo a mano**: lo
chiama `scripts/dev.py` all'avvio. Chi usa la demo non deve sapere che le taglie
sono modelli derivati -- e' un dettaglio del motore, e chiedergli di crearli
significherebbe che il selettore non esiste finche' non ha letto la
documentazione giusta.

**Il servizio non le crea da se', ed e' una decisione.** `LLM_BASE_URL` puo'
puntare a un motore **condiviso** o su un'altra macchina (in `compose.yml` sta
dietro `host.docker.internal`): un backend che scrivesse modelli nel registro di
quel motore a ogni avvio modificherebbe lo stato di qualcun altro senza che
nessuno l'abbia chiesto. La creazione sta quindi nell'avvio *dello sviluppo*, che
gira sulla macchina di chi lo lancia.

**La scala arriva fino al massimo del modello**, e la cautela di partenza era
mal riposta. Si era fermata a 32k temendo che una finestra troppo grande facesse
**fallire** la generazione; la documentazione di Ollama dice il contrario: quando
la cache delle chiavi non entra in VRAM, il motore sposta parte del modello in
RAM di sistema e continua. Diventa molto piu' lento -- ordini di grandezza -- ma
non si rompe, e `ollama ps` dice se sta girando tutto su GPU o a meta'.

Il costo quindi non e' un guasto ma un rallentamento, e un rallentamento **si
vede**: la riga dei tempi lo mostra a ogni risposta. Nascondere una scelta per un
costo visibile e' peggio che offrirla, perche' toglie a chi guarda proprio la
misura che il progetto esiste per far vedere. Le taglie oltre il massimo
dell'architettura restano escluse, perche' quelle non sono lente: non esistono.

Restringerle a quelle che la macchina regge **senza rallentare** e' X-05,
rinviato: serve una sonda di sistema, e Ollama non pubblica la VRAM totale.

**Costa quasi niente**: `ollama create` da un modello gia' scaricato riusa i
blob, quindi non scarica e non duplica i pesi. U-08 chiede che la demo si apra
in meno di due minuti senza download, e questo non lo viola.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.config as cfg  # noqa: E402
from src.service.catalog import _nativo  # noqa: E402


def nome_taglia(base: str, token: int) -> str:
    """`gemma4:e2b` + 8192 -> `ibid/gemma4-e2b:8k`.

    Il nome e' per chi legge `ollama list`, **non** per il programma: il
    raggruppamento nel menu passa da `parent_model`, che il motore dichiara. Se
    fosse il nome a decidere, rinominare un modello a mano lo scollegherebbe dal
    suo gruppo senza che nessuno se ne accorga.

    **Il prefisso e' arrivato con A-09**, e serve a chi non ha chiesto niente:
    prima queste voci si mescolavano ai modelli veri -- ventidue su trenta, su
    questa macchina -- e chi apriva `ollama list` per conto suo trovava un
    elenco che non riconosceva. Ollama non sa nascondere un modello (richiesto
    tre volte, mai implementato), quindi la sola cosa che si puo' fare e'
    renderle **riconoscibili e cancellabili in blocco**: `--pulisci`.

    Verificato il 2026-08-24 che un nome con namespace regge tutto il giro:
    `ibid/gemma4-e2b:32k` risponde su `/v1/chat/completions` a CONTEXT 32768,
    compare in `/v1/models` e conserva `parent_model: gemma4:e2b`. E riusa il
    blob del modello base: stesso ID della taglia creata col nome vecchio.
    """
    return f"{PREFISSO}{_pulito(base)}:{_tag(token)}"


#: Il namespace sotto cui nascono le taglie. Un modello locale puo' avere un
#: namespace come uno scaricato (`utente/modello:tag`), e questo e' il solo modo
#: che Ollama offre di dire «queste sono di un programma, non tue».
PREFISSO = "ibid/"


def _tag(token: int) -> str:
    k = token // 1024
    return f"{k}k" if token % 1024 == 0 else str(token)


def _pulito(base: str) -> str:
    """`smtek/Qwen3.8-27B:IQ3_XXS` -> `smtek-Qwen3.8-27B-IQ3_XXS`.

    Un nome ha **un solo** namespace e **un solo** tag: quelli del modello di
    partenza diventano parte del nome, altrimenti `ibid/` non avrebbe dove
    stare.
    """
    return base.replace("/", "-").replace(":", "-")


def nome_vecchio(base: str, token: int) -> str:
    """Il nome che questo script usava prima di A-09: `gemma4:e2b-8k`.

    Resta perche' le taglie create allora esistono ancora sulle macchine dove
    sono state create, e `--pulisci` deve saperle togliere. Non ne crea piu'.
    """
    return f"{base}-{_tag(token)}"


def massimo(base: str) -> int | None:
    """La finestra piu' grande che `base` regge, o `None` se non si sa.

    Letta **per pattern** (`*.context_length`): Ollama la pubblica sotto una
    chiave che contiene la famiglia, quindi cercarla per nome funzionerebbe su
    un modello solo.
    """
    url = f"{_nativo(cfg.LLM_BASE_URL)}/api/show"
    req = urllib.request.Request(
        url,
        data=json.dumps({"model": base}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read())
    except Exception:
        return None
    info = d.get("model_info")
    if not isinstance(info, dict):
        return None
    for chiave, valore in info.items():
        if str(chiave).endswith(".context_length") and isinstance(valore, int):
            return valore
    return None


def crea(base: str, token: int) -> str:
    nome = nome_taglia(base, token)
    with tempfile.NamedTemporaryFile("w", suffix=".Modelfile", delete=False) as f:
        f.write(f"FROM {base}\nPARAMETER num_ctx {token}\n")
        percorso = f.name
    try:
        subprocess.run(["ollama", "create", nome, "-f", percorso], check=True)
    finally:
        Path(percorso).unlink(missing_ok=True)
    return nome


#: I pioli riconoscibili: potenze di due da 8k in su. Non e' un elenco di
#: finestre valide -- quelle dipendono dal modello -- ma di **misure che chi
#: guarda riconosce**, e si fermano da sole al tetto di ciascuno.
#:
#: Arriva piu' in alto di qualunque modello installato oggi, e costa niente:
#: `scala_per` taglia, quindi un piolo che nessuno regge non produce niente. Il
#: giorno in cui arriva un modello da 1M la scala c'e' gia'.
PIOLI: tuple[int, ...] = (
    8192, 16384, 32768, 65536, 131072, 262144, 524288, 1048576,
)


def scala_per(massimo: int | None) -> tuple[int, ...]:
    """Le finestre da creare per un modello che regge fino a `massimo`.

    **Il tetto si legge dal motore, i pioli no**, e la differenza va detta: senza
    l'ultima riga di questa funzione un modello il cui massimo non cade su una
    potenza di due non vedrebbe mai la propria finestra piu' grande. Oggi non si
    noterebbe -- i quattro modelli installati hanno massimi di 128k e 256k, che
    sono pioli -- e sarebbe il tipo di difetto che si scopre con un modello nuovo
    e sembra un guasto di quel modello.

    Senza un massimo noto si prova la scala intera: `crea` fallira' da sola su
    cio' che il motore non regge, e inventare un tetto che nessuno ha dichiarato
    sarebbe peggio che provarci.
    """
    if massimo is None:
        return PIOLI
    sotto = [t for t in PIOLI if t <= massimo]
    return tuple(sotto if massimo in sotto else [*sotto, massimo])


def _esistenti() -> dict[str, str | None]:
    """Cosa c'e' gia' nel motore: nome -> genitore. Vuoto se non risponde."""
    from src.service.catalog import model_catalog

    try:
        return {m.name: (m.parent or None) for m in model_catalog()}
    except Exception:
        return {}


def assicura() -> int:
    """Crea le taglie mancanti per ogni modello base, e non tocca il resto.

    **Idempotente**: si puo' chiamare a ogni avvio, e la seconda volta non fa
    niente. E' cio' che permette di agganciarla a `dev.py` senza che diventi un
    costo fisso di partenza.

    Salta cio' che il modello non regge -- `context_max` -- e cio' che qualcuno
    ha gia' creato a mano, riconoscendolo dal **genitore** e non dal nome: una
    taglia chiamata diversamente e' comunque quella taglia.
    """
    catalogo = _esistenti()
    if not catalogo:
        return 0

    from src.service.catalog import model_catalog

    voci = model_catalog()
    per_nome = {m.name: m for m in voci}
    creati = 0

    for m in voci:
        if m.parent:
            continue
        gia = {v.context for v in voci if v.parent == m.name}
        for t in scala_per(m.context_max):
            if t in gia or nome_taglia(m.name, t) in per_nome:
                continue
            try:
                crea(m.name, t)
                creati += 1
            except Exception as e:
                print(f"non ho potuto creare {nome_taglia(m.name, t)}: {e}", file=sys.stderr)
    return creati


def da_pulire() -> list[str]:
    """Le taglie che **questo script** ha creato, riconosciute dai due nomi che
    ha usato: `ibid/...` da A-09, e `<base>-32k` da prima.

    Riconosce **solo** cio' che avrebbe creato lei. Un modello derivato che
    qualcuno ha fatto a mano e chiamato a modo suo non entra nell'elenco:
    cancellare il lavoro di un altro perche' somiglia al proprio sarebbe peggio
    del disordine che questo comando esiste per togliere. Su questa macchina la
    differenza e' concreta -- `Qwen3.8-27B-IQ3-32k` e' di Marco, e resta.
    """
    from src.service.catalog import model_catalog

    try:
        voci = model_catalog()
    except Exception:
        return []

    fuori: list[str] = []
    for m in voci:
        # Senza genitore non e' una taglia: e' un modello, e nessun comando di
        # pulizia deve poter togliere dei pesi scaricati.
        if not m.parent:
            continue
        if m.name.startswith(PREFISSO):
            fuori.append(m.name)
        elif m.context is not None and m.name == nome_vecchio(m.parent, m.context):
            fuori.append(m.name)
    return sorted(fuori)


def _conferma() -> bool:
    """`False` anche quando nessuno puo' rispondere.

    Senza un terminale -- una pipe, un CI, un `< /dev/null` -- `input` solleva
    `EOFError`, e un comando che cancella non deve **mai** interpretare il
    silenzio come un si'. Chi vuole cancellare senza terminale ha `--si`, che e'
    una risposta data apposta.
    """
    try:
        return input("le cancello? [s/N] ").strip().lower() in {"s", "si", "y", "yes"}
    except EOFError:
        print("\nnessuno a cui chiedere: uso --si se lo vuoi senza conferma.")
        return False


def pulisci(chiedi: bool = True) -> int:
    """Toglie tutte le taglie, e dice cosa sta per togliere prima di farlo.

    **Chiede conferma di default**, perche' e' l'unico comando del progetto che
    cancella qualcosa dalla macchina di chi lo lancia. `--si` la salta, per gli
    script.
    """
    nomi = da_pulire()
    if not nomi:
        print("nessuna taglia da togliere.")
        return 0

    print(f"{len(nomi)} taglie di contesto create dal progetto:")
    for n in nomi:
        print(f"  {n}")
    print("I pesi dei modelli base non si toccano: le taglie sono manifest, "
          "e i blob restano dove sono.")

    if chiedi and _conferma() is False:
        print("non ho toccato niente.")
        return 0

    tolte = 0
    for n in nomi:
        if subprocess.run(["ollama", "rm", n]).returncode == 0:
            tolte += 1
    print(f"tolte {tolte} taglie su {len(nomi)}.")
    return tolte


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("modello", nargs="?", help="il modello base, come lo chiama il motore")
    p.add_argument("token", nargs="*", type=int, help="le finestre da creare")
    p.add_argument("--rimuovi", action="store_true", help="cancella le taglie invece di crearle")
    p.add_argument("--assicura", action="store_true",
                   help="crea le taglie mancanti per tutti i modelli, e non fa altro")
    p.add_argument("--pulisci", action="store_true",
                   help="toglie tutte le taglie create dal progetto, e non fa altro")
    p.add_argument("--si", action="store_true", help="con --pulisci: non chiede conferma")
    a = p.parse_args()

    if a.pulisci:
        pulisci(chiedi=not a.si)
        return 0

    if a.assicura:
        n = assicura()
        print(f"taglie create: {n}" if n else "taglie gia' a posto")
        return 0

    if a.modello is None:
        p.error("serve un modello, oppure --assicura")

    if a.rimuovi:
        for t in a.token or []:
            # Tutti e due i nomi: una taglia creata prima di A-09 si toglie con
            # lo stesso comando con cui la si toglierebbe oggi.
            for nome in (nome_taglia(a.modello, t), nome_vecchio(a.modello, t)):
                subprocess.run(["ollama", "rm", nome])
        if not a.token:
            print("Serve almeno una taglia da rimuovere.", file=sys.stderr)
            return 2
        return 0

    if not a.token:
        p.error("serve almeno una taglia")

    tetto = massimo(a.modello)
    if tetto is None:
        print(f"Non so quale finestra regga {a.modello}: le creo tutte.", file=sys.stderr)

    for t in sorted(set(a.token)):
        # Una taglia oltre il massimo si crea lo stesso lato Ollama, ma non
        # comparirebbe nel menu (U-16 filtra su `context_max`): meglio dirlo qui
        # che lasciarla invisibile e non spiegata.
        if tetto is not None and t > tetto:
            print(f"salto {t}: {a.modello} regge fino a {tetto}", file=sys.stderr)
            continue
        print(f"creo {crea(a.modello, t)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
