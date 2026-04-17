# notify-bridge

Microservizio bridge che riceve notifiche da **changedetection.io** tramite
un endpoint compatibile con Apprise (`json://`) e le inoltra via
**[Resend](https://resend.com) API**.

Le credenziali (API key Resend) rimangono confinate nel container Docker e
non sono mai esposte in changedetection. Il token di autenticazione del bridge
può essere revocato in qualsiasi momento senza toccare l'account Resend.

---

## Struttura

```
notify-bridge/
├── app.py                      # Flask app (endpoint + chiamata Resend API)
├── Dockerfile
├── requirements.txt
├── docker-compose.snippet.yml  # Blocco da aggiungere al tuo compose
└── README.md
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

### 2. Crea il file `.env` (non committarlo mai)

```env
BRIDGE_TOKEN=il_token_generato_sopra
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
MAIL_FROM=notify@tuodominio.com
MAIL_FROM_NAME=ChangeDetection
MAIL_TO=destinatario@email.com
```

Per più destinatari: `MAIL_TO=uno@email.com,due@email.com`

### 3. Aggiungi il servizio al docker-compose.yml

Copia il contenuto di `docker-compose.snippet.yml` nella sezione `services:`
del tuo `docker-compose.yml` esistente, poi gestisci la rete in base alla
tua configurazione:

**Caso A — nessun blocco `networks:` esplicito nel compose:**
Docker Compose collega automaticamente tutti i servizi alla stessa rete di
default. Non aggiungere nulla: `notify-bridge` e changedetection si vedono
già per nome. Rimuovi o commenta il blocco `networks:` nello snippet.

**Caso B — rete esplicita già dichiarata (es. `changedetection_net`):**
Decommenta il blocco `networks:` nello snippet e usa il nome della rete
già presente nel tuo compose. Non ridichiarare il blocco globale `networks:`,
è già lì.

### 4. Avvia

```bash
docker compose up -d --build notify-bridge
```

### 5. Verifica health

```bash
docker compose exec notify-bridge wget -qO- http://localhost:5000/health
# → {"status":"ok"}
```

---

## Configurazione in changedetection.io

Vai in **Settings → Notifications** e aggiungi l'URL Apprise:

```
json://notify-bridge:5000/IL_TUO_TOKEN
```

- `notify-bridge` → nome del servizio Docker, risolto internamente
- `5000` → porta interna, non esposta sull'host
- `IL_TUO_TOKEN` → valore di `BRIDGE_TOKEN` nel `.env`

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

Vai su resend.com → API Keys → revoca la chiave, generane una nuova,
aggiorna `RESEND_API_KEY` nel `.env` e riavvia il container.
Il token del bridge non cambia.

---

## Variabili d'ambiente

| Variabile        | Default            | Note                                        |
|------------------|--------------------|---------------------------------------------|
| `BRIDGE_TOKEN`   | **obbligatorio**   | Token di autenticazione del bridge          |
| `RESEND_API_KEY` | **obbligatorio**   | API key Resend (`re_...`)                   |
| `MAIL_FROM`      | **obbligatorio**   | Mittente, dominio verificato su Resend      |
| `MAIL_FROM_NAME` | `ChangeDetection`  | Nome visualizzato nel campo "Da:"           |
| `MAIL_TO`        | **obbligatorio**   | Destinatari, separati da virgola            |
