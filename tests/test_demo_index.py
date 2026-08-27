"""U-08: l'indice `demo` che sta in git dice la verita' su se stesso.

Questi test non toccano Qdrant e non embeddano niente: guardano i file di
`data/demo/`, che sono l'artefatto consegnato. E' l'unico posto da cui si
scopre, senza avviare la demo, che il ritaglio e' stato rifatto male.

**Il test che conta e' il secondo.** I sei esempi dello stato vuoto sono
verificati contro l'indice *completo* da `scripts/verify_esempi.py`, che ha
bisogno del corpus intero e della GPU; il vincolo che quei chunk siano anche in
quello ridotto e' precisamente cio' che nessuno riesegue, e infatti D-17 e' nato
dal suo equivalente. Qui gira nella suite normale.
"""

import json

import pytest
from scripts.build_demo_index import doc_id_di
from scripts.verify_esempi import esempi_dal_ts
from src.index.demo import CARTELLA, dataset_ridotti, manifesto

pytestmark = pytest.mark.skipif(
    not (CARTELLA / "manifest.json").exists(),
    reason="data/demo/ non c'e': `python scripts/build_demo_index.py`",
)

#: Il tetto, e non e' quello di GitHub (100 MB per file): e' quanto vale la
#: pena tenere per sempre nella storia del repository per una dimostrazione.
#: I `.npy` densi sono float32 quasi incomprimibili, quindi il peso in git e'
#: quasi tutto li'.
PESO_MAX_MB = 25.0


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads((CARTELLA / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def righe() -> dict[str, list[dict]]:
    fuori = {}
    for f in sorted(CARTELLA.glob("*.jsonl")):
        fuori[f.stem] = [json.loads(r) for r in f.read_text(encoding="utf-8").splitlines() if r]
    return fuori


class TestArtefatto:
    def test_il_manifesto_conta_quello_che_i_file_contengono(self, manifest, righe):
        """Un manifesto che conta diverso dal file e' un ritaglio rifatto a meta'."""
        for voce in manifest["datasets"]:
            assert len(righe[voce["dataset_id"]]) == voce["chunk"]

    def test_i_vettori_sono_tanti_quanti_i_chunk(self, manifest, righe):
        np = pytest.importorskip("numpy")
        for voce in manifest["datasets"]:
            dense = np.load(CARTELLA / f"{voce['dataset_id']}.dense.npy")
            assert dense.shape == (voce["chunk"], voce["dense_size"])
            # float32 e non float16, di proposito: il margine di astensione
            # dichiarato in `esempi.ts` e' +0,0078 su `ledger`, cioe' dentro
            # l'errore che mezza precisione introdurrebbe.
            assert dense.dtype == np.float32

    def test_dice_con_quale_embedder_e_stato_costruito(self, manifest):
        """Un indice interrogato con un altro embedder risponde spazzatura **senza
        errore**: e' il guasto piu' difficile da riconoscere, e l'unica difesa e'
        che il modello sia scritto accanto ai vettori."""
        import src.config as cfg

        assert manifest["embedding_model"] == cfg.EMBEDDING_MODEL
        assert manifest["sparse_embedding_model"] == cfg.SPARSE_EMBEDDING_MODEL

    def test_dice_da_quale_commit(self, manifest):
        assert len(manifest["git_commit"]) == 40

    def test_ogni_documento_e_intero(self, manifest, righe):
        """Il conteggio dei documenti del manifesto e quello dei file coincidono.

        L'unita' di selezione e' il documento: se qui i numeri divergono, il
        ritaglio ha preso chunk sciolti, e l'esploratore di A-07 mostrerebbe
        documenti bucati."""
        for voce in manifest["datasets"]:
            doc_ids = {doc_id_di(r["payload"]["chunk_id"]) for r in righe[voce["dataset_id"]]}
            assert len(doc_ids) == voce["documenti"]

    def test_il_payload_e_quello_del_contratto(self, righe):
        """§3: `dataset_id` su ogni record, e `chunk_id` che comincia con quello."""
        campi = {"chunk_id", "dataset_id", "doc_id", "doc_genre", "pipeline", "text"}
        for dataset, rs in righe.items():
            for r in rs[:50]:
                assert campi <= set(r["payload"])
                assert r["payload"]["dataset_id"] == dataset
                assert r["payload"]["chunk_id"].startswith(f"{dataset}:")

    def test_ogni_chunk_ha_il_suo_sparso(self, righe):
        for rs in righe.values():
            for r in rs[:50]:
                s = r["sparse"]
                assert len(s["indices"]) == len(s["values"])

    def test_non_pesa_piu_di_quanto_vale(self):
        mb = sum(f.stat().st_size for f in CARTELLA.iterdir() if f.is_file()) / 1e6
        assert mb <= PESO_MAX_MB, f"data/demo/ pesa {mb:.1f} MB: alza BUDGET solo di proposito"


class TestVincoloDegliEsempi:
    """Il vincolo che U-08 eredita da U-23, e che nessuno riesegue.

    «Nel profilo `demo` l'indice contiene solo i chunk d'oro di ~30 query: se
    questi esempi non sono fra quelle, il primo clic di chi prova il progetto
    finisce in un'astensione.»
    """

    def test_ogni_chunk_dichiarato_dagli_esempi_e_nell_indice_ridotto(self, righe):
        for dataset, esempi in esempi_dal_ts().items():
            presenti = {r["payload"]["chunk_id"] for r in righe.get(dataset, [])}
            attesi = [a["chunk"] for _, a in esempi if a["esito"] == "risponde"]
            assert attesi, f"{dataset}: nessun esempio che risponde"
            mancanti = [c for c in attesi if c not in presenti]
            assert not mancanti, (
                f"{dataset}: {mancanti} non e' nell'indice `demo`. Il primo clic di chi "
                "prova il progetto finirebbe in un'astensione: rifai "
                "`python scripts/build_demo_index.py`."
            )

    def test_ogni_dataset_degli_esempi_ha_il_suo_ritaglio(self, manifest):
        """Un dataset con esempi e senza indice ridotto e' uno stato vuoto che
        propone domande a un corpus che non c'e'."""
        con_ritaglio = {v["dataset_id"] for v in manifest["datasets"]}
        assert set(esempi_dal_ts()) <= con_ritaglio


class TestCartellino:
    """`manifesto()` e `dataset_ridotti()` senza un server: la domanda «sei una
    demo?» deve avere una risposta anche dove la collection non esiste."""

    class _Client:
        def __init__(self, payload=None):
            self._payload = payload

        def collection_exists(self, name):
            return self._payload is not None

        def scroll(self, name, **kw):
            return [type("P", (), {"payload": self._payload})()], None

    def test_un_server_normale_non_e_una_demo(self):
        assert manifesto(self._Client()) is None
        assert dataset_ridotti(self._Client()) == set()

    def test_un_server_demo_dice_quali_dataset_sono_ridotti(self):
        c = self._Client({"datasets": [{"dataset_id": "ledger", "chunk": 1100}]})
        assert dataset_ridotti(c) == {"ledger"}
