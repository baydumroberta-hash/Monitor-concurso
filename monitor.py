#!/usr/bin/env python3
"""
Monitor de concursos DPU + DPEs (todas as regiões).

O que este script faz a cada execução:
1. Lê a lista de fontes oficiais (DPU + 27 DPEs) e agregadoras em config.json
2. Baixa o texto de cada página
3. Procura pelas palavras-chave de gatilho (edital, inscrições abertas, etc.)
4. Compara com o estado salvo na última execução (state.json)
5. Se encontrar algo NOVO relacionado a concurso, envia notificação por WhatsApp
6. Salva o novo estado para a próxima execução

Este script é feito para rodar via GitHub Actions (cron diário), mas também
roda localmente com: python monitor.py
"""

import json
import os
import re
import sys
import time
import hashlib
import unicodedata
import urllib.parse
import urllib.request

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
STATE_PATH = os.path.join(os.path.dirname(__file__), "state.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def normalizar(texto: str) -> str:
    """Remove acentos e baixa para minúsculas, para comparação de palavras-chave."""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.lower()


def baixar_texto(url: str) -> str:
    """Baixa uma página e extrai apenas o texto visível (remoção simples de tags)."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    # remoção simples de tags/scripts/estilos - suficiente para hashing e busca de palavras-chave
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    texto = re.sub(r"<[^>]+>", " ", html)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def encontra_trecho_relevante(texto: str, palavras_chave: list) -> str | None:
    """Retorna um trecho (~220 caracteres) ao redor da primeira palavra-chave encontrada."""
    texto_norm = normalizar(texto)
    for palavra in palavras_chave:
        p_norm = normalizar(palavra)
        idx = texto_norm.find(p_norm)
        if idx != -1:
            inicio = max(0, idx - 100)
            fim = min(len(texto), idx + 150)
            return texto[inicio:fim].strip()
    return None


def enviar_whatsapp(config: dict, mensagem: str) -> bool:
    """Envia a mensagem para TODOS os destinatários cadastrados em config.json.
    Retorna True se pelo menos um envio funcionou."""
    destinatarios = config["notificacao"].get("destinatarios", [])
    if not destinatarios:
        print("[AVISO] Nenhum destinatário configurado em config.json.")
        return False

    algum_enviado = False
    for dest in destinatarios:
        telefone = dest.get("telefone", "")
        apikey = dest.get("callmebot_apikey", "")

        if "SEU_NUMERO" in telefone or "SUA_APIKEY" in apikey or not telefone or not apikey:
            print(f"[AVISO] Destinatário sem telefone/apikey válidos, pulando. "
                  f"Mensagem que seria enviada:\n{mensagem}")
            continue

        texto_url = urllib.parse.quote(mensagem)
        url = (f"https://api.callmebot.com/whatsapp.php?"
               f"phone={telefone}&text={texto_url}&apikey={apikey}")
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp.read()
            print(f"  -> enviado para {telefone}")
            algum_enviado = True
        except Exception as e:
            print(f"[ERRO] Falha ao enviar WhatsApp para {telefone}: {e}")
        time.sleep(2)  # espaçar entre destinatários por causa do rate-limit do CallMeBot

    return algum_enviado


def carregar_json(caminho: str, padrao):
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return padrao


def salvar_json(caminho: str, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def main():
    config = carregar_json(CONFIG_PATH, None)
    if config is None:
        print("config.json não encontrado.")
        sys.exit(1)

    estado_anterior = carregar_json(STATE_PATH, {})
    estado_novo = {}
    alertas = []

    palavras_chave = config["palavras_chave_gatilho"]
    todas_fontes = config["fontes_oficiais"] + config["fontes_agregadoras"]

    for fonte in todas_fontes:
        nome = fonte.get("regiao") or fonte.get("nome")
        url = fonte["url"]
        print(f"Verificando: {nome} ({url})")
        try:
            texto = baixar_texto(url)
        except Exception as e:
            print(f"  [ERRO] não foi possível acessar {url}: {e}")
            # mantém o estado anterior se o site estiver fora do ar
            if url in estado_anterior:
                estado_novo[url] = estado_anterior[url]
            continue

        hash_atual = hashlib.sha256(texto.encode("utf-8")).hexdigest()
        trecho = encontra_trecho_relevante(texto, palavras_chave)

        info_anterior = estado_anterior.get(url, {})
        hash_anterior = info_anterior.get("hash")
        trecho_anterior = info_anterior.get("trecho")

        estado_novo[url] = {"hash": hash_atual, "trecho": trecho}

        mudou = hash_atual != hash_anterior
        tem_gatilho = trecho is not None
        # só alerta se: já existe um estado anterior (não é a primeira execução para essa fonte)
        # E a página mudou E contém uma palavra-chave E o trecho é diferente do que já tínhamos
        primeira_execucao_da_fonte = url not in estado_anterior
        if not primeira_execucao_da_fonte and mudou and tem_gatilho and trecho != trecho_anterior:
            alertas.append({"regiao": nome, "url": url, "trecho": trecho})

        time.sleep(1)  # gentileza com os servidores das fontes

    salvar_json(STATE_PATH, estado_novo)

    if not alertas:
        print("Nenhuma novidade encontrada nesta execução.")
        return

    print(f"{len(alertas)} novidade(s) encontrada(s). Enviando notificações...")
    for alerta in alertas:
        mensagem = (
            f"🔔 Concurso {alerta['regiao']}\n"
            f"Encontrado: \"{alerta['trecho']}\"\n"
            f"Fonte: {alerta['url']}\n"
            f"Confira os detalhes completos (data de inscrição, vagas, edital) no site oficial."
        )
        enviado = enviar_whatsapp(config, mensagem)
        print(f"  -> {alerta['regiao']}: {'enviado' if enviado else 'NÃO enviado (ver aviso acima)'}")
        time.sleep(3)  # CallMeBot tem limite de taxa entre mensagens


if __name__ == "__main__":
    main()
