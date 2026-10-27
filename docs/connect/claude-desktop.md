# Connect Claude Desktop

A member adds tiroir to Claude Desktop as a custom connector, signs in once,
and then asks Claude to search and write their memory. Nothing is installed on
the member's machine. This page covers Claude Desktop only; the web and mobile
apps and the Claude Code plugin come later.

You need:

- the server's address, `https://<domain>`, from the administrator who
  followed [Install tiroir on a VPS](../install/vps.md);
- your handle and the initial password the administrator gave you;
- a Claude plan that allows custom connectors.

## 1. Add the connector

1. In Claude Desktop, open **Settings**, then **Connectors**.
2. Choose **Add custom connector**.
3. Fill in the dialog:

   | Field | What to enter |
   |---|---|
   | Name | `tiroir`, or any name you like. |
   | Remote MCP server URL | The server's address followed by `/mcp`, for example `https://memoire.example.org/mcp`. |
   | OAuth Client ID, OAuth Client Secret (under **Advanced settings**, if shown) | Leave both empty. tiroir registers the application by itself. |

4. Confirm with **Add**.

## 2. Sign in

Choosing **Connect** on the new connector opens your browser on the tiroir
server. Two pages follow, both plain and titled "tiroir":

1. **Sign in**: a form with *Handle* and *Password*. Enter your handle and the
   initial password. On the first sign-in only, a second page, **Choose your
   password**, asks for a new password of at least 12 characters, typed twice.
2. **Connect an application**: the consent page. It says that the application
   (named, normally *Claude*) asks to use your memory as your handle, with the
   access you have to your stores, and shows the application's identifier and
   the address it will return to. Choose **Allow**. **Deny** refuses, and
   Claude Desktop reports that the connection failed.

The browser then hands control back to Claude Desktop, and the connector shows
as connected. You stay signed in until you revoke the connection or the
administrator disables your account.

## 3. A first search

Start a new conversation, enable the connector's tools if Claude asks, and
ask:

> Search my tiroir memory for "échéance TVA".

Claude calls `tiroir_search` and shows the hits, each naming its store,
drawer, and date. If nothing matches, tiroir says so explicitly instead of
returning loose results.

## 4. A first log entry

Pick a client drawer from the search results and ask:

> Add a log entry to client C001: "Appel du client, relance TVA prévue lundi."

Claude calls `tiroir_write` with the action `log`. In a personal store the
entry is written at once. Ask Claude to search for a word of the entry; it
should be found straight away.

## If it does not work

- *The connector cannot be added*: check that the address ends in `/mcp` and
  opens in a browser (`/health` on the same domain should answer `ready`).
- *The sign-in page rejects the password*: the initial password works once; ask
  the administrator for a new one (`tiroir admin members reset-password`).
- *Claude reports an authorisation error later*: remove the connector and add
  it again.
