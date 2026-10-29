# CLI reference

tiroir is administered with one command, `tiroir`, that ships inside the
server's image. In version 0.1.0 it holds the **administration CLI**,
`tiroir admin`, which you run in the server's container from the directory of
the stack:

```sh
docker compose exec tiroir tiroir admin <command> [options]
```

It works directly on the server's data, so it needs no token: shell access to
the container is the administrator's credential. A change to members or access
takes effect at the members' next request.

Every command accepts `-h` or `--help`, which prints its usage. The examples
below leave out the `docker compose exec tiroir` prefix.

!!! note "Coming later"

    A member CLI, run on a member's own machine against the server (search,
    read, log, proposals), and the administration commands for embeddings,
    mirrors, evaluation, backups and the server's state are planned for later
    releases. They are not in 0.1.0, and this page will document them when they
    are.

## `tiroir`

```text
usage: tiroir [-h] [--version] {admin} ...
```

| Option | Meaning |
|---|---|
| `--version` | Print the version, for example `0.1.0`, and exit. |

## `tiroir admin init`

```text
usage: tiroir admin init [-h]
```

Creates the first administrator, handle `admin`, and prints its initial
password once. The administrator chooses a new password at the first sign-in.
The command refuses to run on a server that already has an administrator.
On a new server, it first prints the steps that set up the server's database.

```text
$ tiroir admin init
server database migrated to version 1
…
member created: …
administrator: admin
initial password (shown once, to change at first sign-in): …
```

## `tiroir admin members`

```text
usage: tiroir admin members [-h] {list,add,disable,reset-password} ...
```

Lists and changes the server's members. Without an action, it lists them.

### `members list`

```text
usage: tiroir admin members list [-h]
```

Prints one member per line: handle, display name, and `[admin]` or
`[disabled]` when they apply.

```text
$ tiroir admin members list
admin	Administrator  [admin]
alice	Alice
```

### `members add`

```text
usage: tiroir admin members add [-h] --name NAME [--admin] handle
```

| Argument | Meaning |
|---|---|
| `handle` | The member's sign-in name: lowercase letters, digits, `-` and `_`. |
| `--name NAME` | The display name. Required. |
| `--admin` | Make the member an administrator. |

Creates the member and prints an initial password once, to change at the first
sign-in.

```text
$ tiroir admin members add alice --name Alice
member created: …
member: alice
initial password (shown once, to change at first sign-in): …
```

### `members disable`

```text
usage: tiroir admin members disable [-h] handle
```

Disables the member and removes their access to every store: they can no
longer sign in. The handle stays reserved.

```text
$ tiroir admin members disable alice
member disabled: …
alice: disabled
```

### `members reset-password`

```text
usage: tiroir admin members reset-password [-h] handle
```

Gives the member a new password, printed once, to change at their next
sign-in.

```text
$ tiroir admin members reset-password alice
member password reset: …
alice: new password (shown once, to change at next sign-in)
…
```

## `tiroir admin stores`

```text
usage: tiroir admin stores [-h] {list,add} ...
```

Lists and creates stores. Without an action, it lists them.

### `stores list`

```text
usage: tiroir admin stores list [-h]
```

Prints one store per line: name, audience, language, and the number of members
with access to it.

```text
$ tiroir admin stores list
alice-memory	personal	fr	1 members
team-memory	team	en	1 members
```

### `stores add`

```text
usage: tiroir admin stores add [-h] --audience {personal,team}
                               --language LANGUAGE [--owner OWNER]
                               [--preset PRESET]
                               name
```

| Argument | Meaning |
|---|---|
| `name` | The store's name, a lowercase slug such as `alice-memory`. |
| `--audience {personal,team}` | `personal`: one member's memory. `team`: shared by the members you grant. Required. |
| `--language LANGUAGE` | The language of the store's content, such as `fr` or `en`. Required. |
| `--owner OWNER` | The handle of the member who owns the store. They get write access, and the store becomes their default. Required for a `personal` store. |
| `--preset PRESET` | The preset the store starts from. In 0.1.0, every store starts from a preset, and the only one is `accounting-firm`, filled with invented client drawers. |

Creates the store and indexes it.

```text
$ tiroir admin stores add alice-memory --audience personal --language fr \
    --owner alice --preset accounting-firm
store: alice-memory
```

## `tiroir admin grant`

```text
usage: tiroir admin grant [-h] handle store {read,write}
```

| Argument | Meaning |
|---|---|
| `handle` | The member. |
| `store` | The store's name. |
| `{read,write}` | The access to give. Granting again replaces the previous access. |

A personal store has its owner only: granting it to another member is refused.

```text
$ tiroir admin grant bob team-memory read
bob: read access to team-memory
```

## `tiroir admin revoke`

```text
usage: tiroir admin revoke [-h] handle store
```

Removes the member's access to the store. Revoking an access the member does
not have is not an error.

```text
$ tiroir admin revoke bob team-memory
bob: no access to team-memory
```

## `tiroir admin index`

```text
usage: tiroir admin index [-h] [--store STORE] [--rebuild]
```

| Option | Meaning |
|---|---|
| `--store STORE` | Index this store only. Without it, every store. |
| `--rebuild` | Rebuild the index from scratch instead of bringing it up to date. |

Indexes are brought up to date when a store is created and after each write,
so this is rarely needed. It prints, per store, the files it indexed (none
when the index was already up to date) and the chunks the index holds.

```text
$ tiroir admin index --store alice-memory
alice-memory: 0 files indexed, 399 chunks
$ tiroir admin index --rebuild
alice-memory: 247 files indexed, 399 chunks
team-memory: 247 files indexed, 399 chunks
```

## `tiroir admin serve`

```text
usage: tiroir admin serve [-h]
```

Runs the server on port 8080. It is the image's entry point, which Compose
starts for you; you do not run it by hand.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success. |
| `1` | The operation failed, for example an unknown member or a store name already used. The reason is on stderr. |
| `2` | Usage error: an unknown command or option, or a missing argument. The usage is on stderr. |
| `3` | Refused by an access rule, for example granting a personal store to a second member. |
| `5` | The store is busy; try again. |
