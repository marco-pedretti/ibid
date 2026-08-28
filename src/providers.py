"""Quale acceleratore ONNX usare, deciso in un posto solo (Q-05).

Prima di questo modulo la decisione era copiata **tre volte** in `src/`
(`index/embed.py`, `generation/entailment.py`, `retrieval/reranker.py`) e altre
due volte come lista letterale in un probe, sempre nella stessa forma:

    ["DmlExecutionProvider", "CPUExecutionProvider"]
    if "DmlExecutionProvider" in onnxruntime.get_available_providers()
    else ["CPUExecutionProvider"]

Non e' solo duplicazione: e' **la cucitura della portabilita'**. DirectML esiste
solo su Windows, quindi quel blocco su Linux ripiega sempre su CPU -- anche su
una macchina con una GPU capace -- e finche' stava in cinque posti, sistemarlo
voleva dire cinque modifiche coerenti fra loro.

## Cosa fa

Prende l'ordine di preferenza qui sotto, tiene solo cio' che onnxruntime dichiara
disponibile, e mette sempre la CPU in fondo come rete di sicurezza. Se non resta
nessun acceleratore, **lo dice** invece di degradare in silenzio: su questo
progetto la differenza fra GPU e CPU e' ~10 embed/s contro ~2,4, cioe' un'
ingestione da 2 ore che ne diventa 8, e scoprirlo a run finita e' caro.

## Cosa NON fa

Non installa niente e non indovina: se il pacchetto onnxruntime giusto per la
piattaforma non c'e', il provider non compare fra i disponibili e non viene
scelto. Le varianti GPU sono extra opzionali di `pyproject.toml`, una per
piattaforma, perche' si escludono a vicenda -- forniscono tutte il modulo
`onnxruntime` e installarne due insieme rompe l'import.

**Provati su Linux il 2026-08-28** (D-10, dentro U-12), su Arch con una RX 6750
XT. Il risultato non e' quello che l'elenco lasciava prevedere: il pacchetto
ROCm della distribuzione **non spedisce `libonnxruntime_providers_rocm.so`**, e
quindi `ROCMExecutionProvider` non compare fra i disponibili e non viene scelto.
Spedisce invece **MIGraphX**, che questo elenco non nomina: senza `ONNX_PROVIDERS`
quella macchina finisce su CPU pur avendo una GPU capace.

Perche' MIGraphX non e' qui sotto, pur essendo il piu' veloce dei tre misurati,
e' scritto accanto all'elenco. CUDA resta dichiarato e non verificato: qui non
c'e' hardware NVIDIA.
"""

from __future__ import annotations

import warnings

import onnxruntime

import src.config as cfg

#: Il nome del provider CPU, che c'e' sempre.
CPU = "CPUExecutionProvider"

#: Solo CPU, esplicito. Non e' un ripiego: alcuni probe tokenizzano soltanto, e
#: caricare un modello su GPU per contare token costa piu' di quanto renda.
CPU_ONLY: list[str] = [CPU]

#: Acceleratori in ordine di preferenza. onnxruntime li prova in quest'ordine e
#: usa il primo che sa eseguire un dato nodo del grafo.
#:
#: DirectML per primo perche' e' l'unico provato su questo hardware (AMD RX 6750
#: XT, ~10 embed/s via DirectX 12). ROCm e CUDA seguono per Linux, dove DirectML
#: non esiste.
#:
#: **MIGraphX non e' in questo elenco, ed e' una scelta, non una dimenticanza.**
#: Sulla stessa GPU, su Arch, fa **26,3 embed/s** contro i 10,0 di DirectML e i
#: 2,4 della CPU: e' il piu' veloce dei tre misurati. Non e' qui per una ragione
#: che il numero non mostra. Quel provider ri-analizza il grafo da un buffer, e
#: cosi' facendo perde la cartella del modello: cerca i pesi esterni
#: (`model.onnx_data`, che `multilingual-e5-large` ha perche' supera i 2 GB)
#: nella **directory corrente**. Se non ce li trova l'inferenza muore, dopo che
#: la sessione si e' legata al provider senza lamentarsi. Metterlo qui lo
#: farebbe scegliere da solo su ogni macchina che lo offre, e la rottura
#: arriverebbe alla prima query invece che all'avvio.
#:
#: Resta raggiungibile dove il costo si conosce, con la variabile che esiste
#: apposta:
#:
#:     ONNX_PROVIDERS=MIGraphXExecutionProvider,CPUExecutionProvider
#:
#: e un `model.onnx_data` nella CWD. Il secondo costo, da sapere prima: la
#: **prima** esecuzione compila il grafo e costa ~278 s, la seconda 1,2. Per un
#: servizio acceso si paga una volta; per uno script che parte e finisce e' il
#: costo dominante.
PREFERRED_ACCELERATORS: tuple[str, ...] = (
    "DmlExecutionProvider",
    "ROCMExecutionProvider",
    "CUDAExecutionProvider",
)


class NoAcceleratorWarning(UserWarning):
    """Nessun acceleratore disponibile: si va a CPU.

    Ha una classe sua perche' un avviso che si puo' filtrare per tipo si puo'
    anche cercare in un test, e perche' in un log va distinto dal rumore.
    """


def _from_env() -> list[str] | None:
    """L'elenco imposto a mano, se c'e'.

    Serve a due cose reali: forzare la CPU per confrontare i tempi, e provare un
    provider su una macchina dove non lo sceglieremmo da soli.
    """
    raw = (cfg.ONNX_PROVIDERS or "").strip()
    if not raw:
        return None
    names = [p.strip() for p in raw.split(",") if p.strip()]
    return names or None


def available() -> list[str]:
    """Cosa onnxruntime dichiara di poter usare su questa macchina."""
    return list(onnxruntime.get_available_providers())


def onnx_providers(warn: bool = True) -> list[str]:
    """L'elenco da passare a `providers=`, migliore per primo.

    La CPU e' sempre in fondo: e' l'unico provider garantito, e ometterlo
    trasformerebbe un acceleratore mancante in un errore invece che in una
    prestazione peggiore.
    """
    forced = _from_env()
    if forced is not None:
        return forced

    have = set(available())
    chosen = [p for p in PREFERRED_ACCELERATORS if p in have]
    if not chosen and warn:
        warnings.warn(
            "Nessun acceleratore ONNX disponibile: si esegue su CPU. "
            f"onnxruntime offre {sorted(have)}; cercavo uno fra "
            f"{list(PREFERRED_ACCELERATORS)}. Su questo progetto la differenza "
            "misurata e' ~10 embed/s contro ~2,4 (I-07). Installa l'extra GPU "
            "adatto alla piattaforma -- vedi pyproject.toml.",
            NoAcceleratorWarning,
            stacklevel=2,
        )
    return [*chosen, CPU]


def active_accelerator() -> str | None:
    """Il primo provider non-CPU che verra' usato, o `None` se si va a CPU."""
    first = onnx_providers(warn=False)[0]
    return None if first == CPU else first


def describe() -> str:
    """Una riga leggibile per i log di avvio."""
    acc = active_accelerator()
    forced = " (imposto da ONNX_PROVIDERS)" if _from_env() is not None else ""
    return f"ONNX: {acc or 'solo CPU'}{forced}"
