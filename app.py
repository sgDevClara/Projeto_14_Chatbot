import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODELO = "openai/gpt-oss-120b"

app = Flask(__name__)
ARQUIVO = Path("data.json")

CARDAPIO = {
    "entrada": ["Carpaccio de carne", "Salada de burrata", "Creme de abóbora"],
    "principal": ["Filé ao molho madeira", "Salmão com risoto de limão", "Risoto de cogumelos"],
    "sobremesa": ["Petit gâteau", "Torta de limão", "Mousse de maracujá"],
}

# Nome do prato -> arquivo dentro de static/img/
IMAGENS = {
    "Carpaccio de carne": "carpaccio.png",
    "Salada de burrata": "burrata.png",
    "Creme de abóbora": "abobora.png",
    "Filé ao molho madeira": "file.png",
    "Salmão com risoto de limão": "salmao.png",
    "Risoto de cogumelos": "risoto.png",
    "Petit gâteau": "petit-gateau.png",
    "Torta de limão": "torta-limao.png",
    "Mousse de maracujá": "mousse.png",
}


def ler():
    if ARQUIVO.exists():
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    return []


def salvar(convidados):
    ARQUIVO.write_text(json.dumps(convidados, ensure_ascii=False, indent=2), encoding="utf-8")


def resumo_texto(convidados):
    """Texto curto com os números atuais, enviado como contexto para a IA."""
    linhas = [f"Total de convidados: {len(convidados)}"]
    for categoria, opcoes in CARDAPIO.items():
        contagem = {o: sum(1 for c in convidados if c.get(categoria) == o) for o in opcoes}
        linhas.append(f"{categoria}: " + ", ".join(f"{o} = {n}" for o, n in contagem.items()))
    restricoes = [f"{c['nome']}: {c['restricao']}" for c in convidados if c.get("restricao")]
    linhas.append("Restrições alimentares: " + ("; ".join(restricoes) or "nenhuma"))
    return "\n".join(linhas)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/estado")
def estado():
    return jsonify({"cardapio": CARDAPIO, "imagens": IMAGENS, "convidados": ler()})


@app.post("/api/convidados")
def adicionar():
    dados = request.get_json(force=True)
    nome = (dados.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "Informe o nome do convidado."}), 400
    convidado = {
        "id": uuid.uuid4().hex[:8],
        "nome": nome[:80],
        "entrada": dados.get("entrada"),
        "principal": dados.get("principal"),
        "sobremesa": dados.get("sobremesa"),
        "restricao": (dados.get("restricao") or "").strip()[:120],
    }
    convidados = ler()
    convidados.append(convidado)
    salvar(convidados)
    return jsonify(convidado), 201


@app.delete("/api/convidados/<id>")
def remover(id):
    salvar([c for c in ler() if c["id"] != id])
    return "", 204


@app.post("/api/chat")
def chat():
    dados = request.get_json(force=True)
    historico = [
        {"role": m["role"], "content": str(m["content"])[:2000]}
        for m in dados.get("historico", [])[-10:]
        if m.get("role") in ("user", "assistant")
    ]
    sistema = (
        "Você é o assistente de um casal que organiza o cardápio do casamento. "
        "Responda em português do Brasil, de forma curta e prática. "
        "Use os números abaixo para sugerir quantidades, alertar sobre restrições "
        "alimentares e ajudar a decidir o cardápio.\n\n" + resumo_texto(ler())
    )
    try:
        resposta = client.chat.completions.create(
            model=MODELO,
            messages=[{"role": "system", "content": sistema}] + historico,
        )
        return jsonify({"texto": resposta.choices[0].message.content})
    except Exception as e:
        return jsonify({"erro": f"Não foi possível falar com a Groq: {e}"}), 502


if __name__ == "__main__":
    app.run(debug=True)