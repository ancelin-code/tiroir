---
type: repo
slug: billing-service
name: Coinwillow Billing
aliases: [billing, invoicer]
language: java
status: active
---
# Coinwillow Billing

## Purpose

Creates invoices, applies taxes and collects payments for subscriptions.

## Architecture

A Spring-style service with a Postgres schema of its own and a retry queue for failed charges. Events go out to [[repos/notifier/summary]].

## Conventions

All amounts are integer cents with a currency code. Schema changes ship in two releases: add, then remove.

## Decisions

BILL-310: failed charges are retried three times over five days. BILL-338: invoices are immutable once sent.

## Gotchas

The tax table is loaded at start-up, so a rate change needs a restart. Time zones: billing days follow UTC, not the customer.

## Open questions

Should refunds create a credit note or reverse the invoice?
