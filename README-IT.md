# notify-bridge

Microservizio bridge che riceve notifiche da **changedetection.io** tramite
un endpoint compatibile con Apprise (`json://`) e le inoltra via
**[Resend](https://resend.com) API**.

Le credenziali (API key Resend) rimangono confinate nel container Docker e
non sono mai esposte in changedetection. Il token di autenticazione del bridge
puo essere revocato in qualsiasi momento senza toccare l'account Resend.

---

## Struttura

```
notify-bridge/
├── app.py                      # Flask app (endpoint + chiamata Resend API)
├── Dockerfile
├── requirements.txt
├── docker-compose.snippet.yml  # Blocco da aggiungere al tuo compose
├── README.md
└── README-IT.md
```

---

## Prerequisiti

- Un account [Resend](https://resend.com) con **dominio verificato**
- Una API key Resend (`re_xxxxxxxxxxxx`)
- L'indirizzo `MAIL_FROM` deve usare il dominio verificato su Resend
  (es. `notify@tuodominio.com`)

---

## Setup

### 1. Genera un token sicuro per il bridge

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Usa un token composto solo da caratteri URL-safe. Evita `/`, `+`, `=`,
spazi e virgolette. Il comando sopra genera già un token sicuro.
Puoi anche usare questo generatore già configurato:
[tools.gioxx.org password generator](https://tools.gioxx.org/en/tools/password-generator/?s=VYtBDsIwDAT_sudcgFtuPCUppkRy4ii2i1DVv6MiQOpxdnZWLIinALVkhLiCqc32QLycAybxZh_tvdOYkhKiDacAludxaF4zDf2hvmoWVsR7Yt251M7_c1qk3K41l9nFv822vQE).

### 2. Crea il file `.env` (non committarlo mai)

```env
BRIDGE_TOKEN=il_token_generato_sopra
BRIDGE_PORT=5001                        # opzionale, cambia solo se 5001 è già occupata
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
MAIL_FROM=notify@tuodominio.com
MAIL_FROM_NAME=ChangeDetection
MAIL_TO=destinatario@email.com
```

Se imposti un token manualmente, tienilo URL-safe. Usa solo lettere,
numeri, `_` e `-`.

Per più destinatari: `MAIL_TO=uno@email.com,due@email.com`

### 3. Aggiungi il servizio al docker-compose.yml

Copia il contenuto di `docker-compose.snippet.yml` nella sezione `services:`
del tuo `docker-compose.yml` esistente, poi gestisci la rete in base alla
tua configurazione:

**Caso A - nessun blocco `networks:` esplicito nel compose:**
Docker Compose collega automaticamente tutti i servizi alla stessa rete di
default. Non aggiungere nulla: `notify-bridge` e changedetection si vedono
gia per nome. Rimuovi o commenta il blocco `networks:` nello snippet.

**Caso B - rete esplicita gia dichiarata (es. `changedetection_net`):**
Decommenta il blocco `networks:` nello snippet e usa il nome della rete
gia presente nel tuo compose. Non ridichiarare il blocco globale `networks:`,
e gia li.

> **Nota sulla porta:** changedetection.io usa la porta 5000 internamente.
> notify-bridge usa la **5001** come default, quindi non c'e conflitto.
> Entrambe le porte sono interne alla rete Docker e non vengono esposte
> sull'host. Se anche la 5001 fosse occupata, basta impostare `BRIDGE_PORT`
> nel `.env` con un valore diverso.

### 4. Avvia

```bash
docker compose up -d --build notify-bridge
```

### 5. Verifica health

```bash
docker compose exec notify-bridge wget -qO- http://localhost:5001/health
# → {"status":"ok"}
```

---

## Configurazione in changedetection.io

Vai in **Settings → Notifications** e aggiungi l'URL Apprise:

```
json://notify-bridge:5001/IL_TUO_TOKEN
```

- `notify-bridge` -> nome del servizio Docker, risolto internamente
- `5001` -> porta interna del bridge, non esposta sull'host
- `IL_TUO_TOKEN` -> valore di `BRIDGE_TOKEN` nel `.env`

Se hai cambiato `BRIDGE_PORT`, aggiorna il numero nell'URL di conseguenza.

---

## Revocare il token del bridge

```bash
# 1. Genera un nuovo token
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Aggiorna BRIDGE_TOKEN nel .env

# 3. Riavvia solo il bridge
docker compose up -d notify-bridge

# 4. Aggiorna l'URL in changedetection
```

L'API key Resend non viene mai toccata.

---

## Revocare la API key Resend

Vai su resend.com -> API Keys -> revoca la chiave, generane una nuova,
aggiorna `RESEND_API_KEY` nel `.env` e riavvia il container.
Il token del bridge non cambia.

---

## Variabili d'ambiente

| Variabile        | Default            | Note                                                      |
|------------------|--------------------|-----------------------------------------------------------|
| `BRIDGE_TOKEN`   | **obbligatorio**   | Token di autenticazione del bridge                        |
| `BRIDGE_PORT`    | `5001`             | Porta interna del container (non esposta sull'host)       |
| `RESEND_API_KEY` | **obbligatorio**   | API key Resend (`re_...`)                                 |
| `MAIL_FROM`      | **obbligatorio**   | Mittente, dominio verificato su Resend                    |
| `MAIL_FROM_NAME` | `ChangeDetection`  | Nome visualizzato nel campo "Da:"                         |
| `MAIL_TO`        | **obbligatorio**   | Destinatari, separati da virgola                          |
