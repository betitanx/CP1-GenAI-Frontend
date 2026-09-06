"""Estado local persistido atomicamente para uma sessão compartilhada."""

import json
from pathlib import Path


class Armazenamento:
    def __init__(self, caminho: Path):
        self.caminho = caminho

    def ler(self) -> dict:
        if self.caminho.exists():
            return json.loads(self.caminho.read_text(encoding="utf-8"))
        return {"documentos": [], "chunks": [], "personas": [], "dataset": [], "configuracao": {}}

    def salvar(self, estado: dict) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.caminho.with_suffix(".tmp")
        temporario.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
        temporario.replace(self.caminho)
