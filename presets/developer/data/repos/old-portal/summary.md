---
type: repo
slug: old-portal
name: Brambleworth Partner Portal
aliases: [portal, legacy portal]
language: ruby
status: archived
---
# Brambleworth Partner Portal

## Purpose

The previous partner portal, replaced by the console in 2025. Kept read-only for audit.

## Architecture

A Rails monolith frozen on its last release, running on one small virtual machine.

## Conventions

Nothing changes here except security patches.

## Decisions

PORT-300: shut down after the audit period ends. PORT-305: the database was archived to cold storage.

## Gotchas

The certificate expires every 90 days and nobody is paged. It still holds the only copy of 2019 statements.

## Open questions

When can the machine be deleted?
