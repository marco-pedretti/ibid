"""Quanto della latenza e' prefill, e quanto decode.

**Perche' esiste.** La latenza di una risposta e' ~15-22 s, e la nota di
portabilita' dice che il prefill ne prende ~12: se e' vero, ogni leva che
riguarda il *decode* (banda, quantizzazione) e' quasi inutile, e ogni leva che
riguarda il *prefill* (attenzione, backend) vale il triplo.  Questa sonda misura
i due pezzi separatamente, cosi' che una modifica al motore si giudichi su un
numero invece che su un'impressione.

**Il primo uso e' `OLLAMA_FLASH_ATTENTION`**, oggi a `false`: si misura prima,
si accende, si rimisura.  Il secondo uso possibile e' Vulkan contro ROCm, che e'
lo stesso confronto su una macchina diversa -- ed e' il motivo per cui l'uscita
si scrive su file: due condizioni non si confrontano a memoria.

**Passa dall'API nativa di Ollama e non da `/v1`**, ed e' l'unico punto in cui
questo repo lo fa oltre a `catalog.py`.  Non e' una deroga alla regola
dell'endpoint OpenAI-compatibile: quel contratto **non ha** i campi che servono
qui -- `prompt_eval_duration` e `eval_duration` non esistono in `usage`, che
riporta solo dei conteggi.  Una sonda che misura il motore ha il diritto di
guardare il motore; il codice di prodotto no, e infatti non lo fa.

**Il prompt e' vero, non sintetico.**  Si ricostruisce dai dump di generazione
gia' a disco (`eval/results/generations/*.jsonl`): la domanda e i cinque
`chunk_id` che il recupero le aveva dato, riletti da Qdrant e rimontati con lo
stesso `build_user_message` della pipeline.  Un prompt inventato della stessa
lunghezza misurerebbe lo stesso prefill, ma nessuno saprebbe piu' se la
lunghezza era quella giusta.

**La prima chiamata si butta.**  Contiene il caricamento del modello (~9 GB da
disco a VRAM), che non e' latenza di risposta ed e' l'unica cosa in grado di
spostare la mediana di un fattore.

Uso:

    python scripts/probe_prefill.py                       # 5 domande di ledger
    python scripts/probe_prefill.py --n 10 --etichetta flash-on
    python scripts/probe_prefill.py --dump eval/results/generations/20260821_101208_open_ragbench.jsonl
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src import config as cfg
from src.generation.prompt import SYSTEM, build_user_message
from src.index.store import chunk_from_payload, get_by_chunk_id, get_client

#: I dump di generazione da cui si pescano domande e chunk, in ordine di eta'.
DUMP_PREDEFINITO = Path("eval/results/generations/20260821_113606_ledger.jsonl")

#: Dove finiscono le misure.  Un file per etichetta, cosi' che accendere una
#: manopola non sovrascriva la misura fatta con la manopola spenta.
USCITA = Path("eval/results/probes")


def _nativo(base_url: str) -> str:
    """Da `http://host:11434/v1` a `http://host:11434`. Vedi `catalog.py`."""
    u = base_url.rstrip("/")
    return u[: -len("/v1")] if u.endswith("/v1") else u


@dataclass
class Misura:
    """Una risposta, coi due tempi separati.  Le durate di Ollama sono in ns."""

    query_id: str
    prompt_tok: int
    prefill_s: float
    decode_tok: int
    decode_s: float
    totale_s: float

    @property
    def prefill_tok_s(self) -> float:
        return self.prompt_tok / self.prefill_s if self.prefill_s else 0.0

    @property
    def decode_tok_s(self) -> float:
        return self.decode_tok / self.decode_s if self.decode_s else 0.0

    @property
    def quota_prefill(self) -> float:
        """La frazione del tempo speso a leggere invece che a scrivere."""
        return self.prefill_s / self.totale_s if self.totale_s else 0.0


def chiedi(
    base: str,
    model: str,
    system: str,
    user: str,
    num_ctx: int,
    num_batch: int | None = None,
) -> dict:
    opzioni: dict = {
        "temperature": cfg.TEMPERATURE,
        "num_ctx": num_ctx,
        "num_predict": cfg.MAX_NEW_TOKENS,
    }
    # `num_batch` si passa solo se chiesto: il valore predefinito lo decide
    # Ollama, e scriverlo qui vorrebbe dire fissare oggi una scelta che domani
    # cambia da sola -- cioe' misurare una condizione credendo di misurarne
    # un'altra.
    if num_batch is not None:
        opzioni["num_batch"] = num_batch
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "think": False,
        "options": opzioni,
    }
    req = urllib.request.Request(
        f"{base}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"Ollama HTTP {e.code}: {body}") from e


def quota_vram(base: str, model: str) -> float | None:
    """La frazione del modello che sta davvero in VRAM, o `None` se non si sa.

    **Senza questo la sonda si lascia confondere in silenzio.**  Misurato il
    2026-08-22: tre runner orfani rimasti da altrettanti riavvii tenevano ~6 GB
    di VRAM, il modello successivo e' entrato per 31 strati su 43, e il numero
    che ne e' uscito -- 365 tok/s di prefill, 10 di decode -- sembrava una
    misura del backend mentre era una misura della memoria libera.  Un terzo del
    modello sulla CPU e' il genere di guasto che non si annuncia: la risposta
    arriva lo stesso, solo lenta.

    `size` e `size_vram` di `/api/ps` bastano a dirlo, e sono due campi
    dell'API, non righe di log da riconoscere -- quindi la verifica sopravvive
    al cambio di sistema operativo, che e' il caso per cui questa sonda esiste.
    """
    try:
        with urllib.request.urlopen(f"{base}/api/ps", timeout=10) as resp:
            caricati = json.loads(resp.read()).get("models", [])
    except (urllib.error.URLError, TimeoutError):
        return None
    for m in caricati:
        if m.get("model") == model or m.get("name") == model:
            totale = m.get("size", 0)
            return m.get("size_vram", 0) / totale if totale else None
    return None


def prompt_da_dump(client, collection: str, riga: dict) -> str | None:
    """Rimonta il messaggio utente di una riga di dump, o `None` se un chunk
    non c'e' piu' nella collection -- il dump e l'indice possono divergere."""
    chunks = []
    for cid in riga["chunk_ids"]:
        payload = get_by_chunk_id(client, collection, cid)
        if payload is None:
            return None
        chunks.append(chunk_from_payload(payload))
    return build_user_message(riga["query_text"], chunks)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dump", type=Path, default=DUMP_PREDEFINITO)
    ap.add_argument("--collection", default="", help="predefinito: dal nome del dump")
    ap.add_argument(
        "--n", type=int, default=5, help="domande misurate, oltre al riscaldamento"
    )
    ap.add_argument("--model", default=cfg.LLM_MODEL)
    ap.add_argument("--num-ctx", type=int, default=cfg.CONTEXT_WINDOW)
    ap.add_argument(
        "--num-batch",
        type=int,
        default=None,
        help="token per blocco di prefill; senza, decide Ollama",
    )
    ap.add_argument("--etichetta", default="", help="come si chiama questa condizione")
    ap.add_argument(
        "--comunque",
        action="store_true",
        help="misura anche col modello a meta' sulla CPU (serve solo a misurare quello)",
    )
    args = ap.parse_args()

    collection = args.collection or args.dump.stem.split("_", 2)[2]
    testo = args.dump.read_text(encoding="utf-8")
    righe = [json.loads(r) for r in testo.splitlines() if r.strip()]
    client = get_client(cfg.QDRANT_URL)
    base = _nativo(cfg.LLM_BASE_URL)

    print(f"dump       {args.dump}")
    print(f"collection {collection}")
    print(
        f"modello    {args.model}  num_ctx {args.num_ctx}  num_batch {args.num_batch or '(default)'}"
    )
    print()

    prompts: list[tuple[str, str]] = []
    for riga in righe:
        if len(prompts) > args.n:  # +1 per il riscaldamento
            break
        user = prompt_da_dump(client, collection, riga)
        if user is not None:
            prompts.append((riga["query_id"], user))
    if len(prompts) < 2:
        raise SystemExit(
            "meno di due prompt ricostruibili: dump e collection non combaciano"
        )

    print(
        f"riscaldamento ({prompts[0][0]}) — carica il modello, non si conta...",
        flush=True,
    )
    chiedi(base, args.model, SYSTEM, prompts[0][1], args.num_ctx, args.num_batch)

    vram = quota_vram(base, args.model)
    if vram is None:
        print(
            "  ! quota in VRAM sconosciuta: la misura non e' verificabile", flush=True
        )
    elif vram < 0.999:
        print(f"  ! solo il {vram * 100:.0f}% del modello e' in VRAM.", flush=True)
        print(
            "    Il resto gira sulla CPU e la misura non dice piu' niente sul backend.",
            flush=True,
        )
        if not args.comunque:
            raise SystemExit("  liberare la VRAM e rilanciare, oppure --comunque")
    else:
        print("  modello interamente in VRAM", flush=True)
    print(flush=True)

    misure: list[Misura] = []
    for qid, user in prompts[1:]:
        t0 = time.time()
        d = chiedi(base, args.model, SYSTEM, user, args.num_ctx, args.num_batch)
        m = Misura(
            query_id=qid,
            prompt_tok=int(d.get("prompt_eval_count", 0)),
            prefill_s=d.get("prompt_eval_duration", 0) / 1e9,
            decode_tok=int(d.get("eval_count", 0)),
            decode_s=d.get("eval_duration", 0) / 1e9,
            totale_s=round(time.time() - t0, 2),
        )
        misure.append(m)
        print(
            f"  {qid:<40} {m.prompt_tok:>6} tok  prefill {m.prefill_s:5.2f}s "
            f"({m.prefill_tok_s:6.1f} tok/s)  decode {m.decode_tok:>4} tok "
            f"{m.decode_s:5.2f}s ({m.decode_tok_s:5.1f} tok/s)  = {m.totale_s:5.2f}s",
            flush=True,
        )

    def med(f) -> float:
        return round(statistics.median(f(m) for m in misure), 2)

    riassunto = {
        "etichetta": args.etichetta,
        "model": args.model,
        "num_ctx": args.num_ctx,
        "num_batch": args.num_batch,
        "collection": collection,
        "n": len(misure),
        "quota_vram": vram,
        "prompt_tok_mediana": med(lambda m: m.prompt_tok),
        "prefill_s_mediana": med(lambda m: m.prefill_s),
        "prefill_tok_s_mediana": med(lambda m: m.prefill_tok_s),
        "decode_tok_s_mediana": med(lambda m: m.decode_tok_s),
        "totale_s_mediana": med(lambda m: m.totale_s),
        "quota_prefill_mediana": med(lambda m: m.quota_prefill),
        "misure": [asdict(m) for m in misure],
    }

    print()
    print(f"  prompt              {riassunto['prompt_tok_mediana']:.0f} tok")
    print(
        f"  prefill             {riassunto['prefill_s_mediana']:.2f} s "
        f"({riassunto['prefill_tok_s_mediana']:.1f} tok/s)"
    )
    print(f"  decode              {riassunto['decode_tok_s_mediana']:.1f} tok/s")
    print(f"  totale              {riassunto['totale_s_mediana']:.2f} s")
    print(f"  quota del prefill   {riassunto['quota_prefill_mediana'] * 100:.0f}%")

    USCITA.mkdir(parents=True, exist_ok=True)
    nome = args.etichetta or time.strftime("%Y%m%d_%H%M%S")
    percorso = USCITA / f"prefill_{nome}.json"
    percorso.write_text(json.dumps(riassunto, indent=2), encoding="utf-8")
    print(f"\nscritto {percorso}")


if __name__ == "__main__":
    main()
