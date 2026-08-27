#!/usr/bin/env python3
"""U-08: carica su Qdrant l'indice `demo` che sta in git.

    python scripts/seed_demo.py
    python scripts/seed_demo.py --qdrant-url http://localhost:6399

Non fa niente per conto suo: la logica sta in `src/index/demo.py`, e sta li'
perche' **la esegue anche il container**, dove `scripts/` non c'e' (il Dockerfile
copia `src`, non il repository). Un caricamento scritto qui dentro avrebbe
obbligato a spedire anche gli script, oppure a scriverlo due volte.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.index.demo import main

if __name__ == "__main__":
    main()
