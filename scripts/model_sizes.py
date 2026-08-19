"""Crea le taglie di contesto di un modello, per il selettore di U-16.

    python scripts/model_sizes.py --assicura            # tutte, e non chiede
    python scripts/model_sizes.py gemma4:e2b 8192 32768 # una a mano
    python scripts/model_sizes.py --rimuovi gemma4:e2b 8192

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

**La scala automatica e' prudente di proposito.** 8k, 16k, 32k: la piu' grande e'
la finestra con cui il progetto misura (§0), e nessuna delle tre mette in
difficolta' una scheda che gia' regge il modello. Le taglie grandi -- 128k, 256k
-- restano raggiungibili a mano, perche' offrirle da sole su una macchina che non
le regge farebbe fallire la generazione dopo l'attesa. Sceglierle in base
all'hardware e' X-05, rinviato: serve una sonda di sistema, e Ollama non pubblica
la VRAM totale.

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
    """`gemma4:e2b` + 8192 -> `gemma4:e2b-8k`.

    Il suffisso e' per chi legge `ollama list`, **non** per il programma: il
    raggruppamento nel menu passa da `parent_model`, che il motore dichiara. Se
    fosse il nome a decidere, rinominare un modello a mano lo scollegherebbe dal
    suo gruppo senza che nessuno se ne accorga.
    """
    k = token // 1024
    return f"{base}-{k}k" if token % 1024 == 0 else f"{base}-{token}"


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


#: La scala che `--assicura` crea. Vedi la nota in testa al file: prudente
#: perche' nessuno l'ha scelta guardando l'hardware, e la piu' grande e' la
#: finestra con cui il progetto misura.
SCALA: tuple[int, ...] = (8192, 16384, 32768)


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
        for t in SCALA:
            if m.context_max is not None and t > m.context_max:
                continue
            if t in gia or nome_taglia(m.name, t) in per_nome:
                continue
            try:
                crea(m.name, t)
                creati += 1
            except Exception as e:
                print(f"non ho potuto creare {nome_taglia(m.name, t)}: {e}", file=sys.stderr)
    return creati


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("modello", nargs="?", help="il modello base, come lo chiama il motore")
    p.add_argument("token", nargs="*", type=int, help="le finestre da creare")
    p.add_argument("--rimuovi", action="store_true", help="cancella le taglie invece di crearle")
    p.add_argument("--assicura", action="store_true",
                   help="crea le taglie mancanti per tutti i modelli, e non fa altro")
    a = p.parse_args()

    if a.assicura:
        n = assicura()
        print(f"taglie create: {n}" if n else "taglie gia' a posto")
        return 0

    if a.modello is None:
        p.error("serve un modello, oppure --assicura")

    if a.rimuovi:
        for t in a.token or []:
            subprocess.run(["ollama", "rm", nome_taglia(a.modello, t)])
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
