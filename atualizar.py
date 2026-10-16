# Robô do Meu Bolso: roda no GitHub a cada hora e salva dados.json com
# notícias de investimento, indicadores do Banco Central e cotações.
import datetime
import email.utils
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (MeuBolso; +https://github.com)"}
AGORA = datetime.datetime.now(datetime.timezone.utc)


def baixar(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def indicador(codigo):
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/1?formato=json"
    ultimo = json.loads(baixar(url))[-1]
    return {"valor": float(ultimo["valor"].replace(",", ".")), "data": ultimo["data"]}


def cotacoes():
    url = "https://economia.awesomeapi.com.br/json/last/USD-BRL,EUR-BRL,BTC-BRL"
    dados = json.loads(baixar(url))
    return {k: {"valor": float(v["bid"]), "variacao": float(v["pctChange"])} for k, v in dados.items()}


BUSCAS = [
    '(investimentos OR "renda fixa" OR "Tesouro Direto" OR CDB OR Selic) when:2d',
    '(Ibovespa OR dólar OR Copom OR inflação OR IPCA) when:1d',
]


def noticias():
    lista, vistos = [], set()
    for busca in BUSCAS:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": busca, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"})
        try:
            raiz = ET.fromstring(baixar(url))
        except Exception as erro:
            print("notícias:", erro)
            continue
        for item in raiz.iter("item"):
            titulo = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            fonte_el = item.find("source")
            fonte = (fonte_el.text or "").strip() if fonte_el is not None else ""
            if fonte and titulo.endswith(" - " + fonte):
                titulo = titulo[: -len(" - " + fonte)]
            try:
                data = email.utils.parsedate_to_datetime(item.findtext("pubDate"))
                data = data.astimezone(datetime.timezone.utc).isoformat(timespec="seconds")
            except Exception:
                data = None
            chave = re.sub(r"\W+", "", titulo.lower())[:60]
            if not titulo or not link.startswith("https://") or chave in vistos:
                continue
            vistos.add(chave)
            lista.append({"titulo": titulo, "fonte": fonte, "link": link, "data": data})
    lista.sort(key=lambda n: n["data"] or "", reverse=True)
    return lista[:12]


def main():
    try:
        with open("dados.json", encoding="utf-8") as f:
            antigo = json.load(f)
    except Exception:
        antigo = {}

    saida = {"atualizado": AGORA.isoformat(timespec="seconds"), "indicadores": {}, "cotacoes": {}, "noticias": []}

    # Selic meta (432), CDI anualizado (4389) e IPCA acumulado em 12 meses (13522)
    for nome, codigo in [("selic", 432), ("cdi", 4389), ("ipca12m", 13522)]:
        try:
            saida["indicadores"][nome] = indicador(codigo)
        except Exception as erro:
            print(nome, erro)
            if nome in antigo.get("indicadores", {}):
                saida["indicadores"][nome] = antigo["indicadores"][nome]

    try:
        saida["cotacoes"] = cotacoes()
    except Exception as erro:
        print("cotações:", erro)
        saida["cotacoes"] = antigo.get("cotacoes", {})

    saida["noticias"] = noticias() or antigo.get("noticias", [])

    with open("dados.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
    print("ok:", len(saida["noticias"]), "notícias")


if __name__ == "__main__":
    main()
