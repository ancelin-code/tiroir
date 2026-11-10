---
type: repo
slug: notifier
name: Pigeonloft
aliases: [notifications, mailer]
language: python
status: active
---
# Pigeonloft

## Purpose

Sends e-mails, SMS and push messages triggered by events from the other services.

## Architecture

A queue consumer with one worker pool per channel. Templates are Jinja files in the repository.

## Conventions

Every template has a plain-text twin. Sender addresses use `example.com`.

## Decisions

NOTE-55: no message is sent between 22:00 and 07:00 local time. NOTE-58: bounces are suppressed after two hard failures.

## Gotchas

Template rendering silently drops an unknown variable. The SMS provider limits to 30 messages per second.

## Open questions

How do we prove consent for old subscribers?
