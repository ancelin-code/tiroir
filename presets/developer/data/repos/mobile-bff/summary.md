---
type: repo
slug: mobile-bff
name: Brambleworth Mobile Backend
aliases: [bff, mobile backend]
language: typescript
status: active
---
# Brambleworth Mobile Backend

## Purpose

A backend-for-frontend that shapes API responses for the iOS and Android apps.

## Architecture

A Node service that composes calls to [[repos/api/summary]] into one payload per screen. Deployed next to the gateway.

## Conventions

Every endpoint is named after a screen. Old app versions are supported for twelve months.

## Decisions

MOB-45: the version gate refuses apps older than 3.0. MOB-52: payloads are capped at 64 KB.

## Gotchas

The push registrar keeps tokens of uninstalled apps for 90 days. Android emulators report a wrong locale.

## Open questions

Can we retire the screen cache now that the API is faster?
