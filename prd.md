# PRD — RPi Guardian: Firewall e IDS Out-of-Band para Laboratório Acadêmico

**Versão:** 0.1 — Rascunho Inicial  
**Data:** Junho de 2026  
**Status:** Em revisão

---

## 1. Visão Geral

### 1.1 Problema

Qualquer notebook conectado a uma rede de internet pode receber tráfego malicioso na rede — seja por malware de mineração de criptomoedas, agentes de C2 (Command & Control) ou exfiltração silenciosa de dados. Inspecionar o tráfego diretamente no host é não-confiável: o software malicioso pode suprimir ou falsificar qualquer agente rodando nele.

### 1.2 Solução

Um **Raspberry Pi posicionado fisicamente entre o notebook e o roteador** intercepta e valida todos os pacotes destinados ao notebook antes de repassá-los. A inspeção acontece inteiramente no RPi — externo ao host — por isso não pode ser desativada nem manipulada pelo notebook. Pacotes aprovados são repassados; pacotes rejeitados são bloqueados e registrados no dashboard.

### 1.3 Topologia de Rede

```
Internet
    │
[Roteador doméstico]
    │  (Ethernet)
[Raspberry Pi — RPi Guardian]
    │  (WiFi Hotspot)
[Notebook alvo]
```

O RPi se conecta ao roteador via cabo Ethernet e cria um hotspot WiFi privado ao qual o notebook se conecta. Para o notebook, a experiência é idêntica a qualquer outro WiFi — sem indicação de que está sendo inspecionado.

> Dependência de roteador: não será feita nenhuma configuração complexa no roteador. O RPi precisa apenas de uma conexão upstream via Ethernet como cliente normal, sem ajustes adicionais no roteador.

---

## 2. Objetivos do Produto

| # | Objetivo | Métrica de Sucesso |
|---|---|---|
| O1 | Validar pacotes de rede em borda antes de repassá-los ao notebook | 100% dos pacotes passam pelo RPi antes de chegar ao destino |
| O2 | Detectar pacotes maliciosos (mining, C2, DNS tunneling) | Taxa de falsos negativos < 5% nos padrões conhecidos |
| O3 | Inspecionar pacotes HTTPS via proxy TLS | > 95% do tráfego HTTPS descriptografado e inspecionado |
| O4 | Bloquear automaticamente pacotes identificados como ameaça | Bloqueio em < 10s após detecção |
| O5 | Exibir alertas de pacotes bloqueados no dashboard do próprio RPi | Alerta visível no dashboard em < 5s após bloqueio |

---

## 4. Requisitos Funcionais

1. RF-01: O RPi intercepta e inspeciona todos os pacotes entre a internet e o notebook; pacotes aprovados são repassados, pacotes rejeitados são descartados.
   - Teste: enviar um pacote legítimo e confirmar chegada ao notebook; enviar pacote com assinatura maliciosa e confirmar descarte via `tcpdump`.
2. RF-02: O RPi inspeciona pacotes HTTPS por proxy TLS e registra host, método e tamanho de cada requisição.
   - Teste: acessar um site HTTPS e verificar a entrada correspondente no log do proxy.
3. RF-03: Ao bloquear um pacote, o RPi exibe o alerta (IP, porta, categoria) no dashboard exposto em sua própria interface web.
   - Teste: simular pacote Stratum ou beaconing C2 e confirmar que o alerta aparece no dashboard em < 5s.

---

## 5. Requisitos Não-Funcionais

1. RNF-01: A inspeção de pacotes adiciona menos de 50 ms de latência ao fluxo normal.
   - Teste: medir tempo de requisição HTTPS com `curl -w %{time_total}` com e sem o RPi no caminho; overhead < 0,05 s.
2. RNF-02: O sistema retoma automaticamente a inspeção de pacotes após reboot.
   - Teste: reiniciar o RPi e confirmar que `hostapd`, `nftables` e o proxy TLS estão ativos sem intervenção manual.
3. RNF-03: Logs de pacotes bloqueados persistem em disco e não se perdem em caso de queda.
   - Teste: forçar desligamento abrupto e confirmar que os registros anteriores ainda estão disponíveis no storage.

---

## 6. Arquitetura Técnica Proposta

### 6.1 Hardware

| Componente | Especificação mínima | Recomendado |
|---|---|---|
| Raspberry Pi | RPi 3B+ | **RPi 4 (4GB RAM)** |
| Cartão SD | 16 GB | 32 GB Classe 10 / A2 |
| Adaptador WiFi | Integrado RPi 4 | Adaptador USB dual-band externo |
| Cabo Ethernet | Cat5e | Cat6 |
| Alimentação | 5V 2.5A | 5V 3A (USB-C no RPi 4) |

### 6.2 Software Stack

| Camada | Tecnologia |
|---|---|
| OS | Raspberry Pi OS Lite (64-bit) |
| Roteador/NAT | `hostapd` (AP WiFi) + `dnsmasq` (DHCP/DNS) + `nftables` (firewall/NAT) |
| Proxy TLS | `mitmproxy` (Python, extensível) |
| IDS / Detecção | Validação de pacotes em borda com Python custom + `scapy` + `pyshark` |
| Feeds de reputação | AbuseIPDB API, Emerging Threats rules, listas de mining pools do GitHub |
| Banco de dados | SQLite (registro de pacotes bloqueados e alertas) |
| Dashboard | Flask (API + interface web servida pelo próprio RPi) |

### 6.3 Fluxo de Dados

```
Internet
  │
  ▼
[nftables — PREROUTING]      → Redireciona TCP 443 → mitmproxy :8080
  │                          → Redireciona TCP 80  → mitmproxy :8080
  ▼
[mitmproxy]                  → Descriptografa TLS, inspeciona pacotes HTTP(S)
  │
  ▼
[Motor de Detecção Python]   → Valida cada pacote; classifica por categoria de ameaça
  │
  ├─ Aprovado → [nftables FORWARD] → Notebook
  └─ Bloqueado → [nftables DROP]
                → [SQLite — log do evento]
                → [Dashboard Flask — alerta no RPi]
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
| Throughput do RPi 4 | Capacidade limitada a ~400 Mbps com proxy TLS ativo | Suficiente para uso de laboratório; documentar limitação |
| Instalação da CA no notebook | Requer acesso físico para instalar o certificado raiz | Etapa obrigatória de setup documentada |
| Evasão via DoH (DNS-over-HTTPS) | Consultas DNS cifradas dentro de HTTPS escapam da análise DNS | mitmproxy inspeciona o payload desde que TLS bump esteja ativo |
| Apps com certificate pinning | Pacotes desses apps não são descriptografáveis | Registrar como tráfego opaco; não bloquear por padrão |

---

## 9. Milestones de Desenvolvimento

| Semana | Entregável | Foco |
|---|---|---|
| 1 | Rede e NAT WiFi funcionando | Configurar `hostapd`, `dnsmasq`, `nftables` e conexão upstream ao roteador |
| 2 | Proxy TLS transparente e detecção básica | Implementar `mitmproxy`, geração de CA local e regras de ameaça para mining/C2 |
| 3 | Persistência e dashboard local | Gravar alertas em SQLite, validar reinício automático e entregar dashboard Flask no próprio RPi |

> Prazo total: 3 semanas. Este cronograma prioriza o caminho mínimo viável: interceptação de pacotes, inspeção TLS e dashboard local de alertas no RPi.
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