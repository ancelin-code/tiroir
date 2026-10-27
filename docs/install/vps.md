# Install tiroir on a VPS

This guide takes an administrator from an empty Linux server to a running
tiroir server with a first member and a first store. It covers the skeleton
milestone: one server, one stack, started with Docker Compose behind Caddy,
which obtains the HTTPS certificate by itself. To connect Claude Desktop
afterwards, follow [Connect Claude Desktop](../connect/claude-desktop.md).

## Prerequisites

- A Linux VPS (`amd64` or `arm64`) with a container runtime that provides
  `docker compose` (Docker Engine with the Compose plugin).
- A domain name, for example `memoire.example.org`, whose DNS `A` (and `AAAA`)
  record points to the VPS.
- Ports 80 and 443 open to the internet on the VPS and its firewall. Caddy uses
  port 80 to prove to the certificate authority that you control the domain.
- A shell on the VPS, and an e-mail address for the certificate authority's
  expiry notices.

tiroir keeps all its state in one Docker volume, `tiroir-data`. It needs no
database server and sends no e-mail.

## 1. Get the stack

The stack is three files: `compose.yaml`, `deploy/Caddyfile` and `.env`. Clone
the repository on the VPS:

```sh
git clone https://github.com/ancelin-code/tiroir.git
cd tiroir
```

## 2. Configure `.env`

```sh
cp .env.example .env
```

Edit `.env`:

| Variable | What to enter |
|---|---|
| `TIROIR_DOMAIN` | Your domain name, without `https://`. The server's public address, `https://<domain>`, is also its OAuth issuer, so it cannot change later without every member signing in again. Use `localhost` to try the stack on your own machine. |
| `TIROIR_ACME_EMAIL` | The e-mail address given to the certificate authority. |
| `TIROIR_TAG` | The image tag to run. Leave `latest`, or pin a release such as `v0.1.0`. |
| `TIROIR_PROXY_SUBNET` | The private subnet of the stack's network, where Caddy runs. Leave the default unless it clashes with a network of yours. |

## 3. Start the stack

```sh
docker compose up -d
```

Compose pulls the `tiroir` image and Caddy, then starts both. Check that they
run and that the server answers through Caddy:

```sh
docker compose ps
curl https://memoire.example.org/health
```

The health route answers `{"status": "ready", "version": …}`. Caddy needs a few
seconds to obtain the certificate on the first start; if `curl` fails with a
TLS error, wait and retry, and read `docker compose logs caddy` if it persists.

To try the stack locally with `TIROIR_DOMAIN=localhost`, build the image
instead of pulling it, and let `curl` accept Caddy's local certificate:

```sh
docker compose up -d --build
curl --insecure https://localhost/health
```

## 4. Create the administrator

```sh
docker compose exec tiroir tiroir admin init
```

The command creates the administrator, handle `admin`, and prints an initial
password once. Copy it now; it cannot be shown again. At the first sign-in,
tiroir asks for a new password of at least 12 characters. Choose a strong one:
tiroir has no second factor in this version, so limit who can reach the server
if you can.

`tiroir admin init` refuses to run twice (`the server already has an
administrator`).

## 5. Create a member

A personal store belongs to a member, so create one, here `alice`:

```sh
docker compose exec tiroir tiroir admin members add alice --name Alice
```

This also prints an initial password, shown once, that the member changes at
their first sign-in. List the members with `tiroir admin members list`.

## 6. Create a personal store from the preset

```sh
docker compose exec tiroir tiroir admin stores add alice-memory \
  --audience personal --language fr --owner alice --preset accounting-firm
docker compose exec tiroir tiroir admin stores list
```

`--preset accounting-firm` fills the store with the bundled synthetic dataset:
23 invented client drawers, each with a summary and a log. The owner gets
access to the store. The command prints `store: alice-memory`, and the list
shows `alice-memory  personal  fr  1 members`.

The store is a bare Git repository, `/data/stores/<id>.git` in the container,
named by an id rather than by the store's name:

```sh
docker compose exec tiroir ls /data/stores
```

Indexes are brought up to date when the store is created and after each write.
To force it, run `docker compose exec tiroir tiroir admin index`.

## 7. Upgrade

In this version, an upgrade pulls the new image and restarts the stack:

```sh
docker compose pull
docker compose up -d
```

The server migrates its database at start, and logs a warning if the database
was written by a newer version than the image, which is the sign of a
downgrade: do not run an older image on the data of a newer one. There is no
backup command yet: copy the `tiroir-data` volume before upgrading if the data
matters.

## Next

[Connect Claude Desktop](../connect/claude-desktop.md) to the server, as the
member you created.
