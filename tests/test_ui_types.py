"""U-00: il contratto TypeScript non puo' divergere da quello Python.

La Fase 8 vieta al frontend di importare `src/`, quindi il contratto del §3.5
esiste in due linguaggi. Due copie a mano divergono -- e la seconda diverge
**in silenzio**, perche' nessun test Python guarda dentro `ui/`.

Questi test sono quello sguardo. Girano nella suite normale, senza Node: chi
aggiunge un campo a `AnswerResponse` e non rigenera lo scopre qui, non dal
browser che riceve `undefined`.
"""

import re

import pytest
from scripts.gen_api_types import OUT, TIPI_ESPLICITI, genera, tipo_ts
from src.api.schema import EVENT_NAMES, AnswerResponse, Capabilities, QueryRequest
from src.service.answer import ABSTAINED_BY_GATE, ABSTAINED_BY_MODEL, NO_ABSTENTION


class TestFileGenerato:
    def test_il_file_committato_e_quello_che_il_generatore_produce_oggi(self):
        """Il solo test che conta: tutti gli altri sono commenti eseguibili.

        Fallisce se un campo e' stato aggiunto, tolto o rinominato in
        `src/api/schema.py` senza rigenerare -- cioe' se il frontend sta
        leggendo un contratto che il backend non parla piu'.
        """
        assert OUT.exists(), f"manca {OUT}: esegui python scripts/gen_api_types.py"
        assert OUT.read_text(encoding="utf-8") == genera(), (
            "ui/src/api/types.ts non e' aggiornato: "
            "esegui python scripts/gen_api_types.py"
        )

    def test_dice_di_essere_generato(self):
        """Un file generato che non lo dichiara viene modificato a mano una volta."""
        assert "non modificare a mano" in OUT.read_text(encoding="utf-8").splitlines()[0]


class TestRichiestaMinima:
    """Il criterio di A-07 espresso nel tipo, non solo in un test.

    `TestContrattoAdditivo` verifica che `{"query": "..."}` basti ancora al
    server. Qui la stessa cosa dal lato del client: se un campo perdesse il suo
    default diventerebbe obbligatorio in TS, e il codice del frontend smetterebbe
    di compilare -- che e' la forma piu' precoce in cui quella rottura puo'
    manifestarsi.
    """

    def _campi(self, interfaccia: str) -> dict[str, bool]:
        """Nome -> obbligatorio, letti dal file generato."""
        corpo = re.search(
            rf"export interface {interfaccia} \{{(.*?)\n\}}",
            OUT.read_text(encoding="utf-8"),
            re.S,
        )
        assert corpo, f"interface {interfaccia} assente"
        return {
            m.group(1): m.group(2) != "?"
            for m in re.finditer(r"^\s+(\w+)(\??):", corpo.group(1), re.M)
        }

    def test_solo_query_e_obbligatorio(self):
        campi = self._campi("QueryRequest")
        assert campi["query"] is True
        assert [n for n, obbligatorio in campi.items() if obbligatorio] == ["query"]

    def test_ogni_campo_di_query_request_c_e(self):
        assert set(self._campi("QueryRequest")) == set(QueryRequest.model_fields)

    def test_i_campi_della_risposta_non_sono_opzionali(self):
        """Il server li manda sempre: `?` costringerebbe ogni lettura a un guardia
        per un caso che non esiste, e renderebbe invisibile quello che esiste."""
        assert all(self._campi("AnswerResponse").values())
        assert set(self._campi("AnswerResponse")) == set(AnswerResponse.model_fields)


class TestStream:
    """Gli eventi sono l'unico pezzo di contratto costruito a mano in `to_wire()`."""

    def test_ogni_evento_del_protocollo_ha_un_ramo(self):
        testo = OUT.read_text(encoding="utf-8")
        for nome in EVENT_NAMES.values():
            assert f'| {{ event: "{nome}"; data: ' in testo, f"evento {nome!r} senza tipo"

    def test_l_unione_non_ha_rami_che_il_protocollo_non_conosce(self):
        rami = set(re.findall(r'\| \{ event: "(\w+)";', OUT.read_text(encoding="utf-8")))
        assert rami == set(EVENT_NAMES.values())

    def test_verification_pending_sopravvive(self):
        """Lo stato piu' scomodo del §3.5 -- testo si', verdetti non ancora --
        e' disegnabile solo se questo campo arriva fino al client."""
        assert "verification_pending: boolean;" in OUT.read_text(encoding="utf-8")

    def test_i_valori_di_abstention_arrivano_al_client(self):
        """«Non ho trovato niente» e «il modello non se l'e' sentita» sono due
        risposte diverse, e il client puo' distinguerle solo confrontando
        `abstention` -- che nel contratto e' un `str` qualunque.

        I tre valori vengono generati invece che ricopiati: cambiarli in
        `src/service/answer.py` senza rigenerare rompe qui, prima del browser.
        """
        testo = OUT.read_text(encoding="utf-8")
        for chiave, valore in (
            ("nessuna", NO_ABSTENTION),
            ("gate", ABSTAINED_BY_GATE),
            ("modello", ABSTAINED_BY_MODEL),
        ):
            assert f'{chiave}: "{valore}",' in testo, f"{chiave} non e' nel file generato"

    def test_i_tipi_espliciti_sono_ancora_sul_filo(self):
        """`genera()` solleva se uno dei nomi dichiarati e' sparito da `to_wire()`.

        Una dichiarazione manuale che nessuno rilegge diventa falsa senza dirlo;
        questa non puo'.
        """
        assert TIPI_ESPLICITI
        genera()  # non solleva


class TestTraduzione:
    def test_bool_non_diventa_number(self):
        """In Python `bool` e' un sottotipo di `int`: l'ordine dei controlli conta."""
        assert tipo_ts(bool) == "boolean"

    def test_l_opzionale_diventa_null_e_non_undefined(self):
        """`null` e non `undefined`: JSON non ha `undefined`, e un campo che il
        server manda a `null` non e' un campo assente."""
        assert tipo_ts(str | None) == "string | null"

    def test_le_liste_di_unioni_sono_parentesizzate(self):
        assert tipo_ts(list[str | None]) == "(string | null)[]"

    def test_il_bbox_resta_una_quadrupla(self):
        """Quattro numeri e non `number[]`: U-06 ne legge gli angoli per indice."""
        assert tipo_ts(tuple[float, float, float, float] | None) == (
            "[number, number, number, number] | null"
        )

    def test_cio_che_non_sa_tradurre_solleva(self):
        """Nessun ripiego su `any`: sarebbe un campo su cui il compilatore smette
        di controllare, cioe' il buco che questo file esiste per chiudere."""
        with pytest.raises(TypeError):
            tipo_ts(complex)

    def test_le_capabilities_restano_elenchi_di_stringhe(self):
        """Q-06 in TypeScript: il frontend non porta una copia di `RETRIEVAL_MODES`,
        la riceve. Se diventassero letterali, un valore nuovo lato server
        romperebbe il frontend invece di arrivarci."""
        for campo in ("retrieval_modes", "baseline_prompts", "reasoning_efforts", "models"):
            assert tipo_ts(Capabilities.model_fields[campo].annotation) == "string[]"
