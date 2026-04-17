# notify-bridge

Bridge microservice that receives notifications from **changedetection.io**
through an Apprise-compatible (`json://`) endpoint and forwards them via the
**[Resend](https://resend.com) API**.

Resend API credentials stay confined to the Docker container and are never
exposed to changedetection. The bridge authentication token can be revoked at
any time without touching the Resend account.

---

## Structure

```
notify-bridge/
├── app.py                      # Flask app (endpoint + Resend API call)
├── Dockerfile
├── requirements.txt
├── docker-compose.snippet.yml  # Block to add to your compose file
├── README.md
└── README-IT.md
```

---

## Prerequisites

- A [Resend](https://resend.com) account with a **verified domain**
- A Resend API key (`re_xxxxxxxxxxxx`)
- The `MAIL_FROM` address must use the domain verified in Resend
  (for example `notify@yourdomain.com`)

---

## Setup

### 1. Generate a secure bridge token

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Use a token made only of URL-safe characters. Avoid `/`, `+`, `=`, spaces,
and quotes. The command above already generates a safe token.
You can also use this preconfigured generator:
[tools.gioxx.org password generator](https://tools.gioxx.org/en/tools/password-generator/?s=VYtBDsIwDAT_sudcgFtuPCUppkRy4ii2i1DVv6MiQOpxdnZWLIinALVkhLiCqc32QLycAybxZh_tvdOYkhKiDacAludxaF4zDf2hvmoWVsR7Yt251M7_c1qk3K41l9nFv822vQE).

### 2. Create the `.env` file (never commit it)

```env
BRIDGE_TOKEN=the_token_generated_above
BRIDGE_PORT=5001                        # optional, change only if 5001 is already in use
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
MAIL_FROM=notify@yourdomain.com
MAIL_FROM_NAME=ChangeDetection
MAIL_TO=recipient@email.com
```

If you set a custom token manually, keep it URL-safe. Stick to letters,
numbers, `_`, and `-`.

For multiple recipients: `MAIL_TO=one@email.com,two@email.com`

### 3. Add the service to docker-compose.yml

Copy the contents of `docker-compose.snippet.yml` into the `services:`
section of your existing `docker-compose.yml`, then handle networking based on
your setup:

**Case A - no explicit `networks:` block in the compose file:**
Docker Compose automatically connects all services to the default network.
Do not add anything: `notify-bridge` and changedetection can already see each
other by name. Remove or comment out the `networks:` block in the snippet.

**Case B - an explicit network is already declared (for example `changedetection_net`):**
Uncomment the `networks:` block in the snippet and use the name of the network
already present in your compose file. Do not redeclare the global `networks:`
block; it is already there.

> **Port note:** changedetection.io uses port 5000 internally. notify-bridge
> uses **5001** by default, so there is no conflict. Both ports stay inside
> the Docker network and are not exposed on the host. If 5001 is also in use,
> just set `BRIDGE_PORT` in `.env` to a different value.

### 4. Start it

```bash
docker compose up -d --build notify-bridge
```

### 5. Check health

```bash
docker compose exec notify-bridge wget -qO- http://localhost:5001/health
# → {"status":"ok"}
```

---

## changedetection.io configuration

Go to **Settings → Notifications** and add the Apprise URL:

```
json://notify-bridge:5001/YOUR_TOKEN
```

- `notify-bridge` -> Docker service name, resolved internally
- `5001` -> internal bridge port, not exposed on the host
- `YOUR_TOKEN` -> value of `BRIDGE_TOKEN` in `.env`

If you changed `BRIDGE_PORT`, update the number in the URL accordingly.

---

## Revoke the bridge token

```bash
# 1. Generate a new token
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Update BRIDGE_TOKEN in .env

# 3. Restart only the bridge
docker compose up -d notify-bridge

# 4. Update the URL in changedetection
```

The Resend API key is never touched.

---

## Revoke the Resend API key

Go to resend.com -> API Keys -> revoke the key, generate a new one, update
`RESEND_API_KEY` in `.env`, and restart the container. The bridge token does
not change.

---

## Environment variables

| Variable         | Default           | Notes                                                     |
|------------------|-------------------|-----------------------------------------------------------|
| `BRIDGE_TOKEN`   | **required**      | Bridge authentication token                               |
| `BRIDGE_PORT`    | `5001`            | Internal container port, not exposed on the host          |
| `RESEND_API_KEY` | **required**      | Resend API key (`re_...`)                                 |
| `MAIL_FROM`      | **required**      | Sender, verified domain on Resend                         |
| `MAIL_FROM_NAME` | `ChangeDetection` | Display name in the "From:" field                         |
| `MAIL_TO`        | **required**      | Recipients, separated by commas                           |
