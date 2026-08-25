"""
Sistema de Monitoramento Inteligente de Rede com Alertas via Telegram
------------------------------------------------------------------------
TCC - Redes de Computadores
Autor: (preencher com o nome do aluno)
Orientador: (preencher com o nome do orientador)

Descrição geral:
    Este script monitora continuamente a conectividade e a latência de
    um host de referência (por padrão, o DNS público do Google:
    8.8.8.8). Quando a latência ultrapassa um limite configurável ou o
    host se torna inacessível, o sistema envia automaticamente um
    alerta para um chat do Telegram por meio da API de Bots.

    Todas as medições são também gravadas em um arquivo CSV, permitindo
    a geração posterior de gráficos e tabelas para o capítulo de
    Resultados do TCC.

Dependências:
    pip install requests ping3

Como usar:
    1. Preencha as variáveis TOKEN_BOT e ID_CHAT abaixo (ou defina as
       variáveis de ambiente TELEGRAM_TOKEN e TELEGRAM_CHAT_ID).
    2. Execute: python monitor_rede.py
    3. Interrompa com Ctrl+C.
"""

import csv
import logging
import os
import time
from datetime import datetime

import requests
from ping3 import ping

# ---------------------------------------------------------------------------
# CONFIGURAÇÕES GERAIS
# ---------------------------------------------------------------------------

# Token do bot do Telegram, obtido junto ao @BotFather.
TOKEN_BOT = os.getenv("TELEGRAM_TOKEN", "SEU_TOKEN_AQUI")

# ID do chat/canal que receberá os alertas.
ID_CHAT = os.getenv("TELEGRAM_CHAT_ID", "SEU_ID_DE_CHAT_AQUI")

# Host de referência para o teste de conectividade (DNS público do Google).
ALVO = "8.8.8.8"

# Limite de latência, em segundos, a partir do qual um alerta é disparado.
LIMITE_LATENCIA = 0.150  # 150 ms

# Intervalo entre verificações, em segundos.
INTERVALO_VERIFICACAO = 60

# Número de falhas consecutivas de ping para considerar a rede "fora do ar".
# Evita alertas de falso positivo causados por uma única perda de pacote.
TENTATIVAS_PARA_CRITICO = 2

# Arquivo de log de medições, usado posteriormente para gerar gráficos.
ARQUIVO_CSV = "historico_rede.csv"

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO DE LOG
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("monitor_rede.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------------------------------------------

def enviar_alerta_telegram(mensagem: str) -> bool:
    """Envia uma mensagem de alerta para o chat configurado no Telegram.

    Retorna True se o envio foi bem-sucedido e False caso contrário.
    """
    url = f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage"
    payload = {"chat_id": ID_CHAT, "text": mensagem}

    try:
        resposta = requests.post(url, json=payload, timeout=10)
        resposta.raise_for_status()
        logger.info("Alerta enviado ao Telegram com sucesso.")
        return True
    except requests.exceptions.RequestException as erro:
        logger.error("Falha ao enviar alerta ao Telegram: %s", erro)
        return False


def registrar_medicao(timestamp: str, status: str, latencia_ms):
    """Grava uma linha de medição no arquivo CSV de histórico."""
    arquivo_novo = not os.path.exists(ARQUIVO_CSV)

    with open(ARQUIVO_CSV, mode="a", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        if arquivo_novo:
            escritor.writerow(["timestamp", "status", "latencia_ms"])
        escritor.writerow([timestamp, status, latencia_ms])


def classificar_medicao(tempo_resposta):
    """Classifica o resultado do ping em um dos três status possíveis:
    'OK', 'ALERTA' (latência alta) ou 'CRITICO' (host inacessível).
    """
    if tempo_resposta is None:
        return "CRITICO", None

    latencia_ms = round(tempo_resposta * 1000, 2)

    if tempo_resposta > LIMITE_LATENCIA:
        return "ALERTA", latencia_ms

    return "OK", latencia_ms


# ---------------------------------------------------------------------------
# LOOP PRINCIPAL DE MONITORAMENTO
# ---------------------------------------------------------------------------

def monitorar_rede():
    logger.info("Monitoramento iniciado. Alvo: %s | Limite: %sms | Intervalo: %ss",
                ALVO, LIMITE_LATENCIA * 1000, INTERVALO_VERIFICACAO)

    falhas_consecutivas = 0

    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            tempo_resposta = ping(ALVO, timeout=4)
        except Exception as erro:  # falhas de baixo nível da biblioteca ping3
            logger.error("Erro ao executar ping: %s", erro)
            tempo_resposta = None

        status, latencia_ms = classificar_medicao(tempo_resposta)
        registrar_medicao(timestamp, status, latencia_ms)

        if status == "OK":
            falhas_consecutivas = 0
            logger.info("Rede OK - latência: %sms", latencia_ms)

        elif status == "ALERTA":
            falhas_consecutivas = 0
            logger.warning("Latência alta detectada: %sms", latencia_ms)
            enviar_alerta_telegram(
                f"⚠️ AVISO: Latência alta detectada!\n"
                f"Horário: {timestamp}\n"
                f"Tempo de resposta: {latencia_ms}ms"
            )

        else:  # CRITICO
            falhas_consecutivas += 1
            logger.error("Host %s inacessível (falha %s/%s).",
                         ALVO, falhas_consecutivas, TENTATIVAS_PARA_CRITICO)

            if falhas_consecutivas >= TENTATIVAS_PARA_CRITICO:
                enviar_alerta_telegram(
                    f"🚨 ALERTA CRÍTICO: Host {ALVO} inacessível!\n"
                    f"Horário: {timestamp}\n"
                    f"A conexão de rede pode estar fora do ar."
                )
                falhas_consecutivas = 0  # evita reenviar a cada ciclo

        time.sleep(INTERVALO_VERIFICACAO)


if __name__ == "__main__":
    try:
        monitorar_rede()
    except KeyboardInterrupt:
        logger.info("Monitoramento interrompido pelo usuário.")
