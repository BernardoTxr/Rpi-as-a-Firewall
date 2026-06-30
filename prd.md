# PRD — RPi Guardian: Firewall e IDS Out-of-Band para Laboratório Acadêmico

**Versão:** 0.2  
**Data:** Junho de 2026  
**Status:** Em revisão

---

## 1. Visão Geral

### 1.1 Problema

Qualquer computador conectado a uma rede pode enviar ou receber tráfego malicioso — seja por malware de mineração de criptomoedas, agentes de C2 (Command & Control) ou exfiltração silenciosa de dados. Inspecionar o tráfego diretamente no host-destino é não-confiável: o software malicioso pode suprimir ou falsificar qualquer agente rodando nele.

### 1.2 Solução

Um **Raspberry Pi posicionado fisicamente entre o remetente (Computador A) e o destinatário (Computador B)** intercepta e valida todos os pacotes antes de repassá-los. A inspeção acontece inteiramente no RPi — externo a ambos os hosts — e não pode ser desativada nem manipulada por nenhum deles. Pacotes aprovados são repassados a B; pacotes rejeitados são descartados e registrados no dashboard, acessível pelo próprio B.

### 1.3 Topologia de Rede

```
[Computador A — remetente]
    │  WiFi (conectado ao hotspot do RPi)
    ▼
[Raspberry Pi — RPi Guardian]
    │  wlan0: 192.168.4.1/24  ← A recebe IP nesta faixa via DHCP
    │  eth0:  192.168.50.1/24 → cabo direto para B
    ▼
[Computador B — destinatário / dashboard]
    IP: 192.168.50.2 (fixo)
    Porta 80: servidor HTTP (alvo dos pacotes de A)
    Porta 8501: dashboard Streamlit (visualização do tráfego)
```

O RPi cria um hotspot WiFi (SSID "RPi-Guardian") usando a interface WiFi integrada (`wlan0`). A se conecta a esse hotspot. O RPi está ligado a B via cabo Ethernet direto (`eth0`). Todo o tráfego de A para B obrigatoriamente passa pelo RPi — não há outro caminho físico disponível.

> Sem adaptador WiFi externo: o WiFi integrado do RPi é suficiente para o cenário de laboratório com poucos dispositivos.

> Sem dependência de roteador: o RPi não precisa de acesso à internet. A topologia é completamente auto-contida entre os três dispositivos.

---

## 2. Objetivos do Produto

| # | Objetivo | Métrica de Sucesso |
|---|---|---|
| O1 | Todo pacote de A para B passa obrigatoriamente pelo RPi | 100% dos pacotes interceptados — verificável via `tcpdump` em B |
| O2 | Detectar e bloquear tráfego malicioso conhecido (mining, C2, beaconing) | Taxa de falsos negativos < 5% nos padrões testados |
| O3 | Inspecionar tráfego HTTP e registrar host, método e tamanho de cada requisição | 100% das requisições HTTP logadas no SQLite |
| O4 | Bloquear automaticamente pacotes identificados como ameaça | Bloqueio em < 10 s após detecção |
| O5 | Exibir alertas no dashboard Streamlit acessível pelo Computador B | Alerta visível no dashboard em < 5 s após bloqueio |

---

## 4. Requisitos Funcionais

1. **RF-01:** O RPi intercepta e inspeciona todos os pacotes enviados de A para B; pacotes aprovados são repassados, pacotes rejeitados são descartados.
   - Teste: A faz `curl http://192.168.50.2` — confirmar chegada em B via log do servidor HTTP; A faz requisição com assinatura Stratum — confirmar descarte via `tcpdump` em B.
2. **RF-02:** O RPi inspeciona requisições HTTP e registra host, método HTTP e tamanho do payload de cada requisição.
   - Teste: A acessa o servidor HTTP em B; verificar entrada correspondente na tabela `events` do SQLite no RPi.
3. **RF-03:** Ao bloquear um pacote, o RPi exibe o alerta (IP de A, host destino, categoria da ameaça) no dashboard acessível em `http://192.168.50.1:8501` pelo Computador B.
   - Teste: A faz requisição com padrão Stratum ou beaconing; confirmar que o alerta aparece no dashboard em < 5 s.

---

## 5. Requisitos Não-Funcionais

1. **RNF-01:** A inspeção de pacotes adiciona menos de 50 ms de latência ao fluxo normal.
   - Teste: medir `curl -w %{time_total}` de A para o servidor HTTP em B com e sem o RPi ativo; overhead < 0,05 s.
2. **RNF-02:** O sistema pode ser iniciado manualmente em poucos comandos (cenário de demo, sem auto-start).
   - Teste: executar `setup/rpi/start_guardian.sh` e confirmar que `hostapd`, `dnsmasq`, `nftables`, `mitmdump` e o dashboard Streamlit ficam ativos. (Auto-start via systemd está fora de escopo desta demo.)
3. **RNF-03:** Logs de pacotes bloqueados persistem em disco e não se perdem em caso de queda.
   - Teste: forçar desligamento abrupto do RPi e confirmar que os registros anteriores ainda estão disponíveis no SQLite.

---

## 6. Arquitetura Técnica Proposta

### 6.1 Hardware

| Componente | Especificação |
|---|---|
| Raspberry Pi | RPi 3B+ ou superior (WiFi integrado obrigatório) |
| Cartão SD | 16 GB mínimo, Classe 10 |
| Cabo Ethernet | Cat5e ou Cat6 (RPi ↔ Computador B, cabo direto) |
| Alimentação | 5V 2,5A (RPi 3B+) / 5V 3A USB-C (RPi 4) |

> Adaptador WiFi externo não é utilizado. O WiFi integrado do RPi opera como Access Point (hostapd) para o Computador A.

### 6.2 Software Stack

| Camada | Tecnologia |
|---|---|
| OS | Raspberry Pi OS Lite (64-bit) |
| Hotspot WiFi | `hostapd` (AP em wlan0) |
| DHCP para A | `dnsmasq` (faixa 192.168.4.10–100) |
| Firewall / NAT | `nftables` — masquerade wlan0→eth0, redirect TCP 80 → :8080 |
| Proxy de inspeção | `mitmproxy` / `mitmdump` (modo transparente, porta 8080) |
| Motor de detecção | `detector.py` — Python custom (3 estágios: blacklist, assinatura, frequência) |
| Banco de dados | SQLite com WAL mode (log persistente de eventos) |
| Dashboard | Streamlit (UI servida em `http://192.168.50.1:8501`, acessada pelo B) |
| Servidor alvo (B) | `python3 -m http.server 80` (endpoint HTTP simples para a demo) |

### 6.3 Fluxo de Dados

```
[Computador A]
  │  HTTP request (TCP 80)  — via WiFi para wlan0 do RPi
  ▼
[nftables — PREROUTING]
  │  iifname "wlan0" tcp dport 80 → redirect :8080
  ▼
[mitmdump — porta 8080]
  │  Descriptografa / lê payload HTTP
  ▼
[detector.py]
  │  Estágio 1: host in blacklist?  → Bloqueia (HTTP 403)
  │  Estágio 2: regex no payload?   → Bloqueia (HTTP 403)
  │  Estágio 3: heartbeat do IP?    → Bloqueia (HTTP 403)
  │
  ├─ Aprovado ──→ [nftables FORWARD] ──→ [Computador B — porta 80]
  │
  └─ Bloqueado → [SQLite — grava evento async]
               → [Dashboard Streamlit — alerta em tempo real]
```

---

## 7. Categorias de Ameaça e Severidade

| Categoria | Severidade | Ação Automática |
|---|---|---|
| Pacote com padrão Stratum (mining) | 🔴 CRÍTICO | Bloquear + exibir alerta no dashboard |
| Beaconing C2 confirmado | 🔴 CRÍTICO | Bloquear + exibir alerta no dashboard |
| DNS tunneling suspeito | 🟠 ALTO | Bloquear + exibir alerta no dashboard |
| TLS para IP sem SNI ou reputação ruim | 🟡 MÉDIO | Logar + exibir aviso no dashboard |
| Pacote em porta incomum | 🟡 MÉDIO | Logar; exibir aviso se recorrente |

---

## 8. Limitações Conhecidas e Riscos

| Limitação | Impacto | Mitigação |
|---|---|---|
| WiFi integrado do RPi como AP | Canal único; interferência em ambientes com muitas redes | Escolher canal menos congestionado via `hostapd.conf`; suficiente para demo em sala |
| HTTP-first na demo | HTTPS não é interceptado por padrão | Instalar CA do mitmproxy no Computador A para habilitar SSL Bump (etapa opcional de setup) |
| Apps com certificate pinning | Pacotes desses apps não são descriptografáveis | Registrar como tráfego opaco; não bloquear por padrão |
| Throughput do RPi | Capacidade limitada com proxy ativo | Suficiente para uso de laboratório; documentar limitação |
| Topologia auto-contida | Sem acesso à internet nos dispositivos durante a demo | Cenário intencional; todos os feeds de blacklist são carregados em disco previamente |

---

## 9. Milestones de Desenvolvimento

| Semana | Entregável | Foco |
|---|---|---|
| 1 | Rede A → RPi → B funcionando | Configurar `hostapd` (AP em wlan0), `dnsmasq` (DHCP para A), IP estático em eth0, `nftables` (NAT masquerade + redirect TCP 80 → :8080), servidor HTTP em B |
| 2 | Inspeção HTTP e detecção básica | Implementar `mitmdump` transparente + `detector.py` com estágios de blacklist, assinatura regex e frequência; gravar eventos no SQLite |
| 3 | Dashboard e persistência | Dashboard Streamlit acessível de B com tabela de eventos em tempo real; inicialização manual via scripts (`setup/rpi/start_guardian.sh`) |

> Prazo total: 3 semanas. Caminho mínimo viável: interceptação de pacotes, inspeção HTTP, detecção em 3 estágios e dashboard local de alertas.
---

## 10. Glossário

| Termo | Definição |
|---|---|
| Out-of-band | Monitoramento realizado fora do sistema alvo, não influenciável por ele |
| SSL Bump / MITM local | Técnica de interceptação de TLS onde o proxy apresenta um certificado próprio ao cliente |
| Beaconing | Padrão de comunicação periódica de malware com servidor C2 |
| Stratum | Protocolo de comunicação entre mineradores e mining pools |
| DGA | Domain Generation Algorithm — técnica de malware para gerar domínios C2 dinamicamente |
| CA | Certificate Authority — entidade que assina certificados digitais |
| nftables | Framework de filtragem de pacotes do kernel Linux (substituto do iptables) |

---

*Documento gerado para fins de pesquisa acadêmica. A inspeção TLS (SSL bump) deve ser realizada apenas em dispositivos de propriedade da instituição ou com consentimento explícito do usuário.*

## 11. Guia de Setup (Topologia A → RPi → B)

### 11.1 Pré-requisitos

- Raspberry Pi com WiFi integrado rodando Raspberry Pi OS Lite (64-bit).
- Cabo Ethernet RJ45 conectando diretamente a porta `eth0` do RPi ao Computador B.
- Computador A disponível para conectar ao WiFi "RPi-Guardian".
- Computador B com IP fixo `192.168.50.2/24` configurado na interface Ethernet.

### 11.2 Passo a Passo

**1. IP estático em eth0 (RPi → B)**

```bash
# Aplicar temporariamente (testes)
sudo ip addr add 192.168.50.1/24 dev eth0
sudo ip link set eth0 up

# Persistir via /etc/dhcpcd.conf
echo -e "\ninterface eth0\nstatic ip_address=192.168.50.1/24" | sudo tee -a /etc/dhcpcd.conf
```

**2. Hotspot WiFi em wlan0 (RPi ← A)**

Instalar e configurar `hostapd`:

```bash
sudo apt install hostapd -y
sudo systemctl unmask hostapd
```

`/etc/hostapd/hostapd.conf`:

```
interface=wlan0
driver=nl80211
ssid=RPi-Guardian
hw_mode=g
channel=6
auth_algs=1
wpa=2
wpa_passphrase=guardian123
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
```

Apontar o arquivo: `echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' | sudo tee -a /etc/default/hostapd`

**3. DHCP para Computador A**

```bash
sudo apt install dnsmasq -y
```

`/etc/dnsmasq.conf`:

```
interface=wlan0
dhcp-range=192.168.4.10,192.168.4.100,255.255.255.0,24h
```

Adicionar IP à interface: `sudo ip addr add 192.168.4.1/24 dev wlan0`

**4. IP Forwarding**

```bash
# Temporário
sudo sysctl -w net.ipv4.ip_forward=1

# Persistente
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
```

**5. Firewall e NAT (nftables)**

```bash
sudo apt install nftables -y
```

`/etc/nftables.conf`:

```
flush ruleset

table ip nat {
    chain prerouting {
        type nat hook prerouting priority dstnat; policy accept;
        iifname "wlan0" tcp dport 80 redirect to :8080
    }
    chain postrouting {
        type nat hook postrouting priority srcnat; policy accept;
        oifname "eth0" masquerade
    }
}
```

Aplicar: `sudo nft -f /etc/nftables.conf`

**6. Instalar e iniciar o mitmproxy**

```bash
sudo apt install pipx python3-dev -y
pipx install mitmproxy

~/.local/bin/mitmdump --mode transparent -s ~/guardian/detector.py --listen-port 8080
```

**7. Servidor HTTP no Computador B**

```bash
python3 -m http.server 80
```

**8. Acessar o dashboard**

No Computador B, abrir o navegador em `http://192.168.50.1:8501`.

### 11.3 Tabela de Validação

| Componente | Comando | Resultado Esperado |
|---|---|---|
| Conexão A → RPi | `ping 192.168.4.1` (em A) | Resposta do RPi |
| Conexão RPi → B | `ping 192.168.50.2` (no RPi) | Resposta de B |
| IP Forwarding | `cat /proc/sys/net/ipv4/ip_forward` | `1` |
| Regras NAT/Proxy | `sudo nft list ruleset` | Tabelas `prerouting` (→ 8080) e `postrouting` (masquerade) |
| Escuta mitmproxy | `ss -tlnp \| grep 8080` | Processo Python ouvindo a porta |
| Tráfego interceptado | `curl http://192.168.50.2` (em A) | Entrada aparece no dashboard |

---

## 12. Roteiro da Demo ao Vivo

| Passo | Ação de A | Resultado Visível em B (dashboard) |
|---|---|---|
| 1 — Tráfego normal | `curl http://192.168.50.2` | Linha verde: "Permitido" |
| 2 — Blacklist | Requisição para domínio de mining pool cadastrado | Linha vermelha: "Bloqueado — Blacklist" |
| 3 — Assinatura | Requisição com `stratum+tcp` na URL ou payload | Linha vermelha: "Bloqueado — Assinatura" |
| 4 — Beaconing | Script em A envia 15 requisições em 30 s | Linha vermelha: "Bloqueado — Frequência (C2)" |

> Na demo, o servidor HTTP em B não recebe os pacotes bloqueados — confirmável via log do `http.server`.

---


## 13. Lógica de Detecção — `detector.py`

### Estratégia de Filtragem (3 Estágios em Hierarquia)

- **Estágio 1 — Blacklist (RAM):** Compara o host da requisição com uma lista de domínios/IPs maliciosos conhecidos carregada em memória (mining pools, servidores C2). Se presente, bloqueia antes de inspecionar o payload.
- **Estágio 2 — Assinatura (regex):** Verifica padrões de texto nos headers e corpo. Exemplo: strings como `stratum+tcp` (mineração) ou `X-Beacon` (C2) disparam bloqueio.
- **Estágio 3 — Frequência (heartbeat):** Analisa o volume de requisições por IP de origem. Mais de 10 requisições para o mesmo destino em menos de 30 s é tratado como beaconing C2.

### Estrutura do Script (Python / mitmproxy)

```python
# Evento 'request' — executado para cada requisição de A
def request(flow):
    host = flow.request.pretty_host
    # Estágio 1
    if host in BLACKLIST:
        flow.response = http.Response.make(403, b"Blocked: blacklist")
        log_event(host, flow.request.method, "blacklist", "blocked")
        return
    # Estágio 2
    if SIGNATURE_RE.search(flow.request.text):
        flow.response = http.Response.make(403, b"Blocked: signature")
        log_event(host, flow.request.method, "signature", "blocked")
        return
    # Estágio 3 — registrar para análise de frequência
    record_request(flow.request.client_conn.address[0], host)

# Evento 'response' — executado quando B responderia
def response(flow):
    host = flow.request.pretty_host
    if is_beaconing(flow.request.client_conn.address[0], host):
        flow.response = http.Response.make(403, b"Blocked: beaconing")
        log_event(host, flow.request.method, "beaconing", "blocked")
        return
    log_event(host, flow.request.method, "allowed", "allowed")
```

### Persistência

Todo evento de bloqueio ou permissão chama `log_event()` de forma assíncrona (thread separada), gravando na tabela `events` do SQLite sem bloquear a thread principal de rede.

Esquema da tabela:

```sql
CREATE TABLE events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT    NOT NULL,
    src_ip    TEXT    NOT NULL,
    host      TEXT    NOT NULL,
    method    TEXT,
    category  TEXT,   -- blacklist | signature | beaconing | allowed
    action    TEXT    -- blocked | allowed
);
```

---

*Documento gerado para fins de pesquisa acadêmica. A inspeção HTTP/HTTPS deve ser realizada apenas em dispositivos de propriedade da instituição ou com consentimento explícito dos usuários envolvidos.*