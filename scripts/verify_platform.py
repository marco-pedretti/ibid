#!/usr/bin/env python3
"""U-12 / D-10: su quale piattaforma stiamo girando, e su cosa gira davvero ONNX.

    python scripts/verify_platform.py             # tutto
    python scripts/verify_platform.py --veloce    # solo l'ambiente, nessun modello

**Stampa, non giudica** (quasi): il verdetto finale e' una riga sola, tutto il
resto e' cio' che la macchina ha risposto. Serve a chiudere D-10, che chiede di
**provare** i provider invece di elencarli, e a farlo in un modo che qualcuno
possa rieseguire fra sei mesi ottenendo un confronto invece di un aneddoto.

## Le tre domande, che non sono la stessa domanda

Un guasto di portabilita' si nasconde nella differenza fra queste tre, e un
controllo che ne facesse una sola passerebbe mentendo:

1. **cosa la macchina offre** -- `onnxruntime.get_available_providers()`. Dice
   quali provider la libreria conosce, non quali funzionano;
2. **cosa il progetto sceglie** -- `src.providers.onnx_providers()`, cioe' il
   nostro ordine di preferenza applicato a cio' che c'e';
3. **su cosa la sessione e' finita** -- `InferenceSession.get_providers()`.
   Questa e' l'unica delle tre che non si puo' ottenere leggendo: onnxruntime
   **scarta in silenzio** un provider che non riesce a inizializzare, e in quel
   caso le prime due dicono ROCm e la terza dice CPU.

La terza riga e' quella che chiude D-10. Le altre due servono a capire *perche'*
quando non torna.

## Le condizioni abilitanti si stampano

`HSA_OVERRIDE_GFX_VERSION` e i suoi vicini non sono rumore: su una RX 6750 XT
(gfx1031, fuori dalla lista di supporto ufficiale di ROCm) sono **la ragione per
cui il risultato e' quello che e'**. Una misura di cui non si registra la
condizione abilitante non e' ripetibile, ed e' la stessa disciplina delle quattro
trappole di `docs/video.md`.

## Il throughput usa i chunk veri

I due numeri che il progetto conosce (~10 embed/s su DirectML, ~2,4 su CPU,
I-07) sono stati misurati su testi di corpus, non su stringhe inventate: un
terzo numero preso su testi corti non sarebbe confrontabile con loro. Quindi i
testi arrivano da `data/demo/`, che sta nel repository e non chiede ne' Qdrant
ne' rete.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg

#: Le quattro distribuzioni che forniscono il modulo `onnxruntime`. **Si
#: escludono a vicenda**: installandone due l'import prende quella che capita, e
#: il sintomo e' un acceleratore che sparisce senza che nessuno abbia cambiato
#: niente. Vale la pena scoprirlo qui invece che a meta' di un'ingestione.
DISTRIBUZIONI = (
    "onnxruntime",
    "onnxruntime-gpu",
    "onnxruntime-rocm",
    "onnxruntime-directml",
)

#: Le variabili che decidono se un acceleratore si vede. Non sono configurazione
#: del progetto: sono lo stato della macchina, e vanno accanto al risultato.
ABILITANTI = (
    "HSA_OVERRIDE_GFX_VERSION",
    "ROCR_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "CUDA_VISIBLE_DEVICES",
    "ONNX_PROVIDERS",
)

#: Quanti chunk embeddare per il throughput. Abbastanza da superare il costo
#: fisso del primo batch, pochi da non far aspettare chi esegue il controllo.
TESTI = 32


def riga(etichetta: str, valore: object, nota: str = "") -> None:
    print(f"  {etichetta:<26} {valore}{'   ' + nota if nota else ''}")


def la_macchina() -> None:
    print("\n== la macchina ==")
    riga("sistema", platform.platform())
    riga("architettura", platform.machine())
    libreria, versione = platform.libc_ver()
    riga(
        "libc",
        f"{libreria} {versione}" if libreria else "(non glibc: non e' Linux)",
        "le ruote ROCm chiedono glibc >= 2.34" if libreria == "glibc" else "",
    )
    riga("python", platform.python_version())


def le_variabili() -> None:
    print("\n== le variabili che abilitano ==")
    for nome in ABILITANTI:
        valore = os.environ.get(nome)
        riga(nome, valore if valore else "(non impostata)")


def onnx() -> tuple[list[str], list[str]]:
    """Quali distribuzioni forniscono `onnxruntime`, e cosa dichiarano di offrire.

    **Al plurale di proposito.** `fastembed` richiede `onnxruntime` (quello CPU)
    per ogni versione di Python, quindi `pip install -e ".[gpu-rocm]"` ne
    installa **due**: verificato col risolutore di pip in un container Linux, e
    ne escono `onnxruntime-rocm 1.22.2` e `onnxruntime 1.29.0` insieme. Le due
    scrivono lo stesso modulo, vince chi arriva ultimo, e il sintomo e' una GPU
    che sparisce senza che nessuno abbia cambiato niente.
    """
    from importlib.metadata import PackageNotFoundError, version

    print("\n== onnxruntime ==")
    trovate = []
    for nome in DISTRIBUZIONI:
        try:
            trovate.append(f"{nome} {version(nome)}")
        except PackageNotFoundError:
            continue
    if not trovate:
        riga("distribuzione", "NESSUNA: onnxruntime non e' installato")
        return [], []
    riga("distribuzione", trovate[0])
    if len(trovate) > 1:
        riga("ATTENZIONE", f"{len(trovate)} distribuzioni insieme: {trovate}")

    import onnxruntime

    # **Un modulo che si importa non e' un modulo che funziona.** Dopo un
    # `pip uninstall onnxruntime` fatto quando erano installate due
    # distribuzioni, resta una cartella vuota: `import` riesce, `__file__` e'
    # `None` e non c'e' nessuna funzione. Se questo controllo non ci fosse,
    # l'unica cosa che si vedrebbe e' un `AttributeError` a meta' pagina, cioe'
    # un traceback al posto della diagnosi -- ed e' successo davvero.
    if not hasattr(onnxruntime, "get_available_providers"):
        riga("modulo", "ROTTO: si importa ma e' vuoto")
        print()
        print(f"  La distribuzione {trovate[0]} risulta installata, ma i suoi file non ci sono.")
        print("  Succede dopo `pip uninstall -y onnxruntime` quando erano installate in due:")
        print("  la seconda arrivata possedeva i file condivisi, e toglierla li ha portati via.")
        print("  Si rimette in piedi cosi', senza rifare l'ambiente:")
        print(f"\n      pip install --force-reinstall --no-deps {trovate[0].split()[0]}\n")
        sys.exit(1)

    offerti = list(onnxruntime.get_available_providers())
    riga("versione del modulo", onnxruntime.__version__)
    riga("offre", offerti)
    return trovate, offerti


def la_scelta() -> list[str]:
    print("\n== la scelta del progetto ==")
    import warnings

    from src import providers

    with warnings.catch_warnings():
        # L'avviso "nessun acceleratore" e' un'informazione, non un guasto: qui
        # la stessa cosa la dice il verdetto, e due volte sarebbe rumore.
        warnings.simplefilter("ignore", providers.NoAcceleratorWarning)
        scelti = providers.onnx_providers()
    riga("ordine di preferenza", list(providers.PREFERRED_ACCELERATORS))
    riga("onnx_providers()", scelti)
    return scelti


def _sessione_dell_embedder(modello):
    """La `InferenceSession` dentro il `TextEmbedding` di fastembed.

    Fruga in una libreria di terzi, quindi **puo' smettere di funzionare senza
    preavviso**: se la catena cambia si torna `None` e il chiamante ripiega sul
    verificatore NLI, che e' codice nostro e la sessione la restituisce.
    """
    oggetto = modello
    for attributo in ("model", "model"):
        oggetto = getattr(oggetto, attributo, None)
        if oggetto is None:
            return None
    return oggetto if hasattr(oggetto, "get_providers") else None


def la_sessione_vera() -> list[str]:
    """Su cosa e' finita davvero una sessione ONNX. La riga che chiude D-10."""
    print("\n== la sessione vera ==")
    from src.index import embed

    modello = embed._dense_model(cfg.EMBEDDING_MODEL)
    sessione = _sessione_dell_embedder(modello)
    origine = f"embedder ({cfg.EMBEDDING_MODEL})"
    if sessione is None:
        # Ripiego su codice nostro: `_load` restituisce la sessione, quindi non
        # dipende da come fastembed e' fatto dentro. Costa il download del
        # verificatore, ~2 GB la prima volta.
        from src.generation import entailment

        _, sessione = entailment._load(cfg.ENTAILMENT_MODEL)
        origine = f"verificatore ({cfg.ENTAILMENT_MODEL})"
        riga("nota", "la sessione dell'embedder non e' raggiungibile: uso il verificatore")

    effettivi = list(sessione.get_providers())
    riga("da", origine)
    riga("sessione su", effettivi)
    return effettivi


def il_throughput() -> str | None:
    """Embed/s su chunk veri. Restituisce l'errore se l'esecuzione **fallisce**.

    **Creare una sessione e farla eseguire sono due cose diverse**, e la seconda
    puo' fallire dove la prima e' riuscita. Su Arch, con MIGraphX imposto, la
    sessione si lega al provider e poi l'inferenza muore: quel provider
    ri-analizza il grafo da un buffer e cerca il file dei pesi esterni
    (`model.onnx_data`, che `multilingual-e5-large` ha perche' supera i 2 GB)
    nella directory corrente invece che accanto al modello.

    Un'eccezione qui non e' un guasto dello script: **e' il risultato**. Prima
    usciva come traceback, cioe' nel modo in cui un risultato non si legge.
    """
    print("\n== il throughput ==")
    demo = ROOT / "data" / "demo"
    file = sorted(demo.glob("*.jsonl"))
    if not file:
        riga("saltato", "data/demo/ non c'e': niente testi con cui confrontarsi")
        return None

    testi = []
    for f in file:
        for r in f.read_text(encoding="utf-8").splitlines():
            if r:
                testi.append(json.loads(r)["payload"]["text"])
            if len(testi) >= TESTI:
                break
        if len(testi) >= TESTI:
            break

    from src.index import embed

    # **Due giri, e il primo si butta.** Alcuni provider compilano il grafo alla
    # prima esecuzione: su MIGraphX sono stati **279 secondi su 281**, e un
    # numero solo li avrebbe spalmati sui 32 chunk facendo leggere 0,1 embed/s
    # per un provider che a regime va. E' l'artefatto di A-05 (*«tempi di prima
    # query, cioe' caricamento riportato come costo per richiesta»*), e si evita
    # nell'unico modo che funziona: misurare la seconda volta.
    t0 = time.perf_counter()
    try:
        embed.encode(testi, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH)
    except Exception as e:  # noqa: BLE001 - qualunque cosa sia, e' il risultato
        riga("esecuzione", "FALLITA: la sessione si e' creata ma non esegue")
        # Solo l'ultima riga: l'eccezione di onnxruntime e' un muro di testo, e
        # la riga che nomina il nodo o il file mancante e' quella in fondo.
        ultima = str(e).strip().splitlines()[-1] if str(e).strip() else type(e).__name__
        riga("errore", ultima[:160])
        return ultima
    primo = time.perf_counter() - t0

    t0 = time.perf_counter()
    embed.encode(testi, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH)
    regime = time.perf_counter() - t0

    lunghezza = sum(len(t) for t in testi) // len(testi)
    riga("testi", f"{len(testi)} chunk, {lunghezza} caratteri in media")
    riga("prima esecuzione", f"{primo:.1f} s", "compilazione del grafo compresa")
    riga("a regime", f"{regime:.1f} s")
    riga(
        "throughput",
        f"{len(testi) / regime:.1f} embed/s",
        "noti: ~10 DirectML, ~2,4 CPU (I-07)",
    )
    if primo > regime * 3:
        print(f"\n  La prima esecuzione e' costata {primo / regime:.0f} volte la seconda: questo")
        print("  provider compila il grafo, e il costo si paga una volta per processo.")
        print("  Per un servizio che resta acceso non conta; per uno script che parte e")
        print("  finisce, e' il costo dominante.")
    return None


def non_nominati(offerti: list[str]) -> list[str]:
    """Gli acceleratori che la macchina offre e che il nostro ordine ignora.

    Senza questa riga una macchina cosi' e' **indistinguibile da una senza
    GPU**: si finisce su CPU e il verdetto dice «coerente». E' il caso vero di
    Arch, dove `python-onnxruntime-rocm` espone il provider MIGraphX e
    non il provider ROCm.

    Sta fuori dal verdetto perche' serve anche a `--veloce`, che il verdetto non
    lo calcola: **e' la domanda che vale la pena fare per prima**, e costa due
    secondi invece di due caricamenti di modello. La prima versione la faceva
    solo alla fine, e su Arch non e' comparsa affatto.
    """
    from src.providers import CPU, PREFERRED_ACCELERATORS

    ignoti = [p for p in offerti if p != CPU and p not in PREFERRED_ACCELERATORS]
    if ignoti:
        riga("offerti e non nominati", ignoti)
        print("\n  Questa macchina offre acceleratori che il nostro ordine di preferenza non")
        print("  elenca, quindi non li prova nemmeno. Per provarne uno senza toccare il")
        print("  codice basta imporlo (Q-05), e se regge va aggiunto a")
        print("  PREFERRED_ACCELERATORS in `src/providers.py`:")
        print(f"\n      ONNX_PROVIDERS={ignoti[0]},{CPU} python scripts/verify_platform.py\n")
    return ignoti


def verdetto(
    offerti: list[str],
    scelti: list[str],
    effettivi: list[str],
    distribuzioni: list[str] | None = None,
    errore_esecuzione: str | None = None,
) -> int:
    # Il nome del provider CPU si chiede a `src/providers.py` invece di
    # scriverlo, ed e' la cucitura di Q-05 applicata a chi **riferisce** una
    # scelta invece di compierla. Un test guarda che nessun modulo fuori di li'
    # nomini un execution provider: ha trovato queste due righe, e aveva ragione.
    from src.providers import CPU

    print("\n== verdetto ==")

    # **Prima di tutto il resto, perche' rende inaffidabile tutto il resto**: con
    # due distribuzioni il modulo importato e' quello che ha scritto i file per
    # ultimo, e le righe qui sopra descrivono uno stato che il prossimo
    # `pip install` puo' cambiare da solo.
    if distribuzioni and len(distribuzioni) > 1:
        riga("ambiente", "ROTTO: due distribuzioni di onnxruntime insieme")
        print(f"\n  {distribuzioni}")
        print("  Forniscono lo stesso modulo e si escludono a vicenda: vince chi ha scritto")
        print("  i file per ultimo. `pip install -e \".[gpu-...]\"` ci arriva da solo, perche'")
        print("  fastembed richiede `onnxruntime`. Togline una:  pip uninstall -y onnxruntime")
        return 1

    primo = effettivi[0] if effettivi else ""

    # **Legato ma non funzionante.** E' lo stato piu' insidioso dei tre, perche'
    # le tre domande dicono tutte di si' e il sistema non gira lo stesso: la
    # sessione si e' creata sul provider, e poi l'inferenza e' morta. Senza
    # questa riga il verdetto direbbe «verificato» di un provider inutilizzabile.
    if primo and primo != CPU and errore_esecuzione:
        riga("acceleratore in uso", f"{primo}, ma NON esegue")
        print(f"\n  La sessione si e' legata a {primo}, e l'inferenza e' fallita:")
        print(f"    {errore_esecuzione[:160]}")
        print("\n  D-10 **non** e' verificato per questo provider: legarsi non e' eseguire.")
        return 1

    if primo and primo != CPU:
        riga("acceleratore in uso", primo)
        print("\n  D-10 per questo provider e' verificato: la sessione ci gira davvero.")
        print("  Riporta anche le variabili qui sopra: sono la condizione che lo rende vero.")
        return 0

    riga("acceleratore in uso", "nessuno: si gira su CPU")
    non_nominati(offerti)

    voluti = [p for p in scelti if p != CPU]
    if not voluti:
        print("\n  E' coerente: nessun acceleratore fra quelli offerti. Non e' un guasto,")
        print("  e' una macchina senza GPU utilizzabile (o l'extra giusto non e' installato).")
        return 0

    # Il caso interessante: il progetto ha scelto un acceleratore e la sessione
    # non ce l'ha fatta. E' esattamente il guasto che le prime due domande da
    # sole non vedono.
    print(f"\n  ATTENZIONE: il progetto aveva scelto {voluti}, e la sessione e' su CPU.")
    print("  onnxruntime scarta in silenzio un provider che non riesce a inizializzare:")
    print("  qui offerti e scelti dicono una cosa, la sessione ne dice un'altra.")
    print(f"  offerti: {offerti}")
    return 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--veloce",
        action="store_true",
        help="solo l'ambiente: non carica modelli e non misura niente",
    )
    args = ap.parse_args()

    la_macchina()
    le_variabili()
    distribuzioni, offerti = onnx()
    scelti = la_scelta()

    if args.veloce:
        # Le due cose che si vedono **senza caricare niente**, e sono quelle per
        # cui `--veloce` esiste: un ambiente rotto, e un acceleratore che il
        # nostro ordine non nomina.
        if len(distribuzioni) > 1:
            sys.exit(verdetto(offerti, scelti, [], distribuzioni))
        print()
        non_nominati(offerti)
        print("(--veloce: la sessione vera e il throughput non sono stati provati)")
        return

    effettivi = la_sessione_vera()
    errore = il_throughput()
    sys.exit(verdetto(offerti, scelti, effettivi, distribuzioni, errore))


if __name__ == "__main__":
    main()
