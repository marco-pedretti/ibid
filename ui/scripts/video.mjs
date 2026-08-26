/**
 * La ripresa di U-10, guidata da uno script invece che da una mano.
 *
 * Il criterio del task vieta i tagli che nascondono la latenza reale, e questo
 * e' il modo piu' letterale di rispettarlo: **non c'e' un montaggio**. Il
 * browser esegue il copione dal vivo, la registrazione parte prima del primo
 * clic e si ferma dopo l'ultimo, e i secondi di attesa sono quelli che il
 * sistema impiega davvero, quel giorno, su quella scheda.
 *
 * L'altro motivo per cui e' uno script: **il video invecchia con
 * l'interfaccia**, e una ripresa a mano si rifa' solo rifacendola. Questa si
 * rifa' con un comando, che e' la differenza fra aggiornare la GIF quando U-13
 * sposta la corsia e lasciarla vecchia.
 *
 *   npm run video              # italiano, tema scuro
 *   npm run video -- --en      # inglese
 *   npm run video -- --chiaro  # tema chiaro
 *
 * Servono il backend e Vite gia' accesi (`make dev`) e l'indice costruito. Il
 * copione, i tempi misurati e i controlli da fare prima stanno in
 * `docs/video.md`.
 *
 * ## Le tre cose che questo script fa, e che una mano non farebbe meglio
 *
 * **Aspetta gli eventi veri, non i secondi.** La fine della generazione non e'
 * un `sleep`: e' la scomparsa del comando «Ferma», che esiste solo mentre lo
 * stream scorre. Se un giorno il modello ci mettesse il doppio, la ripresa
 * durerebbe il doppio invece di tagliare la risposta a meta'.
 *
 * **Il puntatore e' disegnato.** Playwright non registra il cursore di sistema,
 * quindi senza un surrogato i clic sembrerebbero accadere da soli. E' un
 * cerchietto nel DOM che segue gli stessi bersagli dei clic veri: non tocca
 * niente della pagina, e la pagina non sa che c'e'.
 *
 * **La guida di U-20 si salta dal deposito**, non chiudendola a mano: un profilo
 * di browser nuovo la mostrerebbe a ogni ripresa, e i suoi cinque passi non
 * stanno in novanta secondi insieme al resto.
 */
import { mkdir, readdir, rename, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

const QUI = dirname(fileURLToPath(import.meta.url));
const RADICE = join(QUI, "..", "..");

const args = process.argv.slice(2);
const LINGUA = args.includes("--en") ? "en" : "it";
/** `--scatto` prende l'immagine ferma invece del video: stesso copione,
 *  fermato alla battuta in cui c'e' tutto da vedere. */
const SCATTO = args.includes("--scatto");
/** Il tema della ripresa. **Scuro di default**, che e' come il progetto si
 *  mostra nei due README; `--chiaro` per l'altro. */
const TEMA = args.includes("--chiaro") ? "light" : "dark";
const URL = valore("--url") ?? "http://localhost:5173";
const USCITA = valore("--out") ?? join(RADICE, "docs");

function valore(nome) {
  const i = args.indexOf(nome);
  return i >= 0 ? args[i + 1] : null;
}

/**
 * Le quattro etichette che servono a trovare un comando e che non hanno un
 * testo indipendente dalla lingua. Vengono da `src/i18n/strings.ts`
 * (`chat.send`, `chat.stop`, `history.new`, `corpus.back`): sono copiate qui e
 * non importate perche' questo file gira in Node, fuori da Vite. Se cambiano,
 * lo script **fallisce con un timeout invece di registrare una ripresa
 * sbagliata**, che e' il verso giusto in cui rompersi.
 *
 * Tutto il resto si trova senza tradurre niente: le domande d'esempio portano
 * la query inglese in mono anche nell'interfaccia italiana, e il nome del
 * documento e' un identificatore.
 */
const ETICHETTE = {
  it: {
    invia: "Invia",
    ferma: "Ferma",
    nuova: "Nuova conversazione",
    indietro: "Torna alla conversazione",
  },
  en: {
    invia: "Send",
    ferma: "Stop",
    nuova: "New conversation",
    indietro: "Back to the conversation",
  },
};

/** Quanto si lascia leggere ogni battuta. Le attese **vere** non sono qui,
 *  perche' non sono numeri: sono eventi dell'interfaccia. */
const LEGGI = {
  esempi: 3500, // lo stato vuoto: le tre domande e la loro nota
  fonti: 1500, // le fonti sono arrivate, la risposta non e' cominciata
  verdetti: 7000, // i verdetti per frase, a risposta finita
  fonte: 7500, // il chunk citato dentro il documento
  astensione: 6500, // il rifiuto, e la ragione
  // La traccia video puo' finire **prima** dell'orologio dello script, e di
  // quanto cambia da una ripresa all'altra: fra due consecutive, 0,25 s e
  // 3,4 s. Quel che manca lo paga l'ultima battuta, quindi la coda e' larga.
  // Non costa niente nel file finito: i fotogrammi identici si fondono, e
  // cinque secondi di schermata ferma diventano un fotogramma solo.
  coda: 5000,
};

const attesa = (ms) => new Promise((r) => setTimeout(r, ms));

/* --- il puntatore disegnato ----------------------------------------------- */

const CURSORE = `
#__cursore {
  position: fixed; top: 0; left: 0; width: 20px; height: 20px;
  margin: -10px 0 0 -10px; border-radius: 50%;
  border: 2px solid rgba(90, 90, 110, .85);
  background: rgba(140, 140, 170, .22);
  box-shadow: 0 1px 4px rgba(0, 0, 0, .25);
  z-index: 2147483647; pointer-events: none;
  transition: transform .45s cubic-bezier(.4, 0, .2, 1), width .12s, height .12s, margin .12s;
}
#__cursore.giu {
  width: 13px; height: 13px; margin: -6.5px 0 0 -6.5px;
  background: rgba(120, 120, 160, .5);
}
`;

async function disegnaCursore(page) {
  await page.addStyleTag({ content: CURSORE });
  await page.evaluate(() => {
    if (document.getElementById("__cursore") !== null) return;
    const d = document.createElement("div");
    d.id = "__cursore";
    d.style.transform = "translate(640px, 720px)";
    document.body.appendChild(d);
  });
}

/** Porta il puntatore sul bersaglio, ci passa sopra col mouse vero (cosi' gli
 *  stati `hover` si vedono) e clicca. */
async function clicca(page, loc, { prima = 550 } = {}) {
  const box = await loc.boundingBox();
  if (box === null) throw new Error("bersaglio senza riquadro: la pagina non e' quella attesa");
  const x = Math.round(box.x + box.width / 2);
  const y = Math.round(box.y + Math.min(box.height / 2, 22));
  await page.evaluate(
    ([px, py]) => {
      const d = document.getElementById("__cursore");
      if (d !== null) d.style.transform = `translate(${px}px, ${py}px)`;
    },
    [x, y],
  );
  await page.mouse.move(x, y);
  await attesa(prima);
  await page.evaluate(() => document.getElementById("__cursore")?.classList.add("giu"));
  await attesa(120);
  await loc.click();
  await page.evaluate(() => document.getElementById("__cursore")?.classList.remove("giu"));
}

/**
 * Aspetta che la battuta finisca.
 *
 * Il segnale e' il comando di arresto, che esiste **solo** mentre una risposta
 * scorre. Quando sparisce la risposta e' completa; quando non compare affatto
 * il gate ha chiuso prima di generare, ed e' altrettanto finita. Il primo
 * `waitFor` ha un margine corto proprio per il secondo caso: l'astensione
 * misurata costa 0,3 secondi.
 */
async function attendiFineRisposta(page, et) {
  const ferma = page.getByRole("button", { name: et.ferma }).first();
  await ferma.waitFor({ state: "visible", timeout: 8_000 }).catch(() => {});
  await ferma.waitFor({ state: "hidden", timeout: 180_000 });
  await page.getByRole("button", { name: et.invia }).first().waitFor({ state: "visible" });
}

/**
 * Il riscaldamento, e la cosa che ha quasi falsificato la ripresa.
 *
 * Due cose sono fredde alla prima esecuzione e nessuna delle due e' la
 * pipeline. **Vite compila i moduli al primo caricamento**, e senza questo giro
 * la registrazione si aprirebbe su tre secondi di scheletro. **Il motore rimette
 * il modello in VRAM alla prima domanda dopo una pausa**: misurato, 24,8 s a
 * freddo contro 14,3 s subito dopo, sulla stessa domanda.
 *
 * ## La cache del prefill, che e' un taglio senza forbici
 *
 * Ollama tiene la cache del prompt, e **una domanda gia' fatta non paga il
 * prefill**. Misurato oggi sulla domanda del copione: 16,9 s la prima volta,
 * **3,9 s** dopo averla ripetuta qualche volta. Una ripresa fatta in quello
 * stato mostrerebbe «generation 3,91 s» a schermo, senza tagliare un
 * fotogramma: sarebbe esattamente cio' che il criterio vieta, ottenuto per via
 * di una cache invece che di un montaggio.
 *
 * E non basta scaldare con una domanda diversa: le cache sono piu' d'una, e
 * quella della domanda del copione sopravvive. **Quindi il modello si scarica**
 * (`keep_alive: 0`), poi si ricarica con una domanda che nel video non compare.
 * Cosi' la domanda del copione paga il proprio prefill davvero, e la riga dei
 * tempi a schermo dice il vero qualunque numero esca.
 *
 * Lo scarico e' un'operazione dell'API nativa di Ollama, quindi **si tenta e non
 * si pretende**: con `llama-server` non esiste, e in quel caso lo script lo dice
 * invece di fingere. Chi vuole riprendere il primo avvio di tutto passa
 * `--freddo`.
 */
async function scalda(browser) {
  if (args.includes("--freddo")) return;

  const motore = valore("--motore") ?? "http://localhost:11434";
  const modello = valore("--modello") ?? "gemma4:latest";
  try {
    const r = await fetch(`${motore}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: modello, keep_alive: 0 }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    await r.text();
    await attesa(2500);
  } catch (e) {
    console.warn(
      `  ! non ho potuto scaricare il modello da ${motore} (${e.message}).\n` +
        "    Se il motore tiene la cache del prompt, la ripresa mostrera' una\n" +
        "    latenza piu' bassa di quella vera. Vedi docs/video.md.",
    );
  }

  const c = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const p = await c.newPage();
  await p.goto(URL, { waitUntil: "domcontentloaded" });
  await p
    .getByRole("button", { name: /MLMM/ })
    .first()
    .waitFor({ state: "visible", timeout: 60_000 });
  // La domanda che ricarica il modello: **diversa da quelle del copione**, per
  // la ragione scritta in cima a questa funzione.
  await p.evaluate(async () => {
    await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query:
          "In year 2018, what did The Sherwin-Williams Company report for selling, general, and administrative expenses?",
        dataset_id: "ledger",
      }),
    });
  });
  await c.close();
}

/* --- il copione ----------------------------------------------------------- */

async function main() {
  const et = ETICHETTE[LINGUA];
  const tmp = join(USCITA, ".video-grezzo");
  await rm(tmp, { recursive: true, force: true });
  await mkdir(tmp, { recursive: true });

  const browser = await chromium.launch();
  await scalda(browser);

  // Con `--scatto` la stessa sequenza si ferma a risposta verificata e salva
  // un'immagine invece di un video: e' la schermata che U-11 aveva lasciato
  // indietro, e va presa **qui** perche' e' l'unico fotogramma in cui si vedono
  // insieme il testo con i marcatori, i verdetti per frase e le fonti. Al
  // doppio della densita', che su un'immagine ferma si vede e su un video no.
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: SCATTO ? 2 : 1,
    ...(SCATTO ? {} : { recordVideo: { dir: tmp, size: { width: 1280, height: 800 } } }),
    locale: LINGUA === "it" ? "it-IT" : "en-US",
    // Il tema lo decide il deposito, non la media query. Questo serve al resto:
    // barre di scorrimento e controlli nativi, che altrimenti restano chiari
    // dentro una pagina scura.
    colorScheme: TEMA,
  });

  // Il deposito prima che l'app lo legga: la guida gia' fatta (U-20) e la lingua
  // scelta. Il dataset non si tocca: il primo interrogabile e' `open_ragbench`,
  // che e' quello del copione.
  // I valori sono stringhe nude e non JSON: e' il formato che il deposito usa
  // davvero (`leggiLingua` confronta con l'elenco delle lingue, e lo script in
  // testa a `index.html` legge il tema prima che React parta). Scritti fra
  // virgolette JSON non corrispondevano a niente e venivano ignorati in
  // silenzio: la lingua tornava giusta solo perche' la decideva il `locale`.
  await context.addInitScript(
    ([lingua, tema]) => {
      try {
        window.localStorage.setItem("ibid.avvio", "fatto");
        window.localStorage.setItem("ibid.lang", lingua);
        window.localStorage.setItem("ibid.theme", tema);
      } catch {
        /* un deposito negato non deve fermare la ripresa */
      }
    },
    [LINGUA, TEMA],
  );

  const page = await context.newPage();
  const t0 = Date.now();
  /**
   * Le battute, con il secondo in cui sono cadute. Servono a due cose: si
   * leggono a schermo mentre la ripresa va, e finiscono in un file accanto al
   * video perche' **il montaggio non deve indovinare dove comincia il
   * copione**. `scripts/video_gif.py` taglia esattamente al primo, cioe' al
   * momento in cui l'applicazione ha finito di caricare, e non un fotogramma
   * piu' in la'.
   */
  const battute = [];
  const battuta = (nome) => {
    const s = (Date.now() - t0) / 1000;
    battute.push({ nome, s: Number(s.toFixed(2)) });
    console.log(`  ${s.toFixed(1).padStart(5)}s  ${nome}`);
  };

  await page.goto(URL, { waitUntil: "domcontentloaded" });

  // 1. Lo stato vuoto, con le tre domande d'esempio.
  const esempio1 = page.getByRole("button", { name: /MLMM/ }).first();
  await esempio1.waitFor({ state: "visible", timeout: 60_000 });
  await disegnaCursore(page);
  battuta("stato vuoto");
  await attesa(LEGGI.esempi);

  // 2. La prima domanda parte.
  await clicca(page, esempio1);
  battuta("domanda inviata");

  // 3. Le fonti arrivano **prima** del primo token: e' il §3.5, misurato a 0,3 s.
  const primaFonte = page.getByRole("button", { name: "2401.07294v4" }).first();
  await primaFonte.waitFor({ state: "visible", timeout: 60_000 });
  battuta("fonti arrivate");
  await attesa(LEGGI.fonti);

  // 4. La risposta scorre, e finisce quando finisce.
  await attendiFineRisposta(page, et);
  battuta("risposta finita");

  if (SCATTO) {
    // Il puntatore disegnato non va in una schermata ferma: nel video dice chi
    // sta cliccando, qui sarebbe solo un cerchio in mezzo al testo.
    await page.evaluate(() => document.getElementById("__cursore")?.remove());
    await attesa(600);
    const png = join(USCITA, LINGUA === "it" ? "screenshot.png" : "screenshot.en.png");
    await page.screenshot({ path: png });
    await context.close();
    await browser.close();
    await rm(tmp, { recursive: true, force: true });
    console.log(`
${png}`);
    return;
  }

  await attesa(LEGGI.verdetti);

  // 5. La fonte si apre nell'esploratore, sul chunk citato.
  await clicca(page, primaFonte);
  const indietro = page.getByRole("button", { name: et.indietro }).first();
  await indietro.waitFor({ state: "visible", timeout: 30_000 });
  battuta("fonte aperta");
  await attesa(LEGGI.fonte);

  // 6. Si torna, si ricomincia, e si chiede una cosa che il corpus non ha.
  await clicca(page, indietro);
  const nuova = page.getByRole("button", { name: et.nuova }).first();
  await nuova.waitFor({ state: "visible", timeout: 15_000 });
  await clicca(page, nuova);
  const esempio3 = page.getByRole("button", { name: /Allison Transmission/ }).first();
  await esempio3.waitFor({ state: "visible", timeout: 15_000 });
  battuta("conversazione nuova");
  await clicca(page, esempio3);

  // 7. Il gate chiude in mezzo secondo: nessun token, nessuna risposta inventata.
  await attendiFineRisposta(page, et);
  battuta("astensione");
  await attesa(LEGGI.astensione);
  await attesa(LEGGI.coda);

  const durata = (Date.now() - t0) / 1000;

  // Quanto e' costata la risposta, dedotto dalle battute. **Sopra i quindici
  // secondi il sospetto non e' il modello, e' la memoria**: con le sessioni ONNX
  // del backend residenti in VRAM, su una scheda da 12 GB il motore finisce a
  // copiare invece che a calcolare, e la stessa domanda passa da 8 a 26 secondi
  // (misurato tutte e due). Non e' una latenza da pubblicare: e' una macchina in
  // contesa, e la diagnosi sta in `docs/hardware.md`.
  const fonti = battute.find((b) => b.nome === "fonti arrivate");
  const finita = battute.find((b) => b.nome === "risposta finita");
  if (fonti !== undefined && finita !== undefined && finita.s - fonti.s > 15) {
    console.warn(
      `\n  ! la risposta ha impiegato ${(finita.s - fonti.s).toFixed(1)} s.\n` +
        "    Di solito ne bastano otto: prima di tenere questa ripresa, riavvia il\n" +
        "    backend per liberare la VRAM delle sessioni ONNX. Vedi docs/video.md.",
    );
  }
  await context.close();
  await browser.close();

  const nome = LINGUA === "it" ? "demo.webm" : "demo.en.webm";
  const grezzi = (await readdir(tmp)).filter((f) => f.endsWith(".webm"));
  if (grezzi.length !== 1) throw new Error(`attesa una registrazione, trovate ${grezzi.length}`);
  await rename(join(tmp, grezzi[0]), join(USCITA, nome));
  await rm(tmp, { recursive: true, force: true });
  await writeFile(
    join(USCITA, nome.replace(/\.webm$/, ".tempi.json")),
    JSON.stringify({ lingua: LINGUA, durata: Number(durata.toFixed(2)), battute }, null, 2) + "\n",
    "utf8",
  );

  console.log(`\n${nome}  ${durata.toFixed(1)}s${durata > 90 ? "   ATTENZIONE: oltre i 90" : ""}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
