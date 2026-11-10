---
type: repo
slug: admin-console
name: Brambleworth Back Office
aliases: [backoffice, admin]
language: ruby
status: active
---
# Brambleworth Back Office

## Purpose

The internal web console used by support staff to look up orders and issue refunds.

## Architecture

A Rails-style monolith with its own database replica. Sign-in goes through [[repos/auth-service/summary]].

## Conventions

Every action writes an audit record. Feature specs cover each screen.

## Decisions

ADM-140: refunds above 500 need a second approver. ADM-151: personal data is masked by default.

## Gotchas

The order search is slow without the date filter and times out after 30 seconds. Seeds create real-looking addresses; never run them in staging.

## Open questions

Can support see less data and still do their job?
