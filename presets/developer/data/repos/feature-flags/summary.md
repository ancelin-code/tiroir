---
type: repo
slug: feature-flags
name: Toggleroom
aliases: [flags, toggles]
language: go
status: active
---
# Toggleroom

## Purpose

Stores feature flags and rolls them out to a percentage of users.

## Architecture

A Go service publishing a signed snapshot every ten seconds. Clients evaluate rules locally.

## Conventions

A flag has an owner and an expiry date. Expired flags are reported weekly.

## Decisions

FF-18: evaluation is local, never a network call. FF-22: flags are removed within 90 days of full rollout.

## Gotchas

The snapshot is cached by the CDN for 30 seconds longer than expected. Percentage rollouts use the user id, so anonymous users flip on every visit.

## Open questions

How do we test flag combinations?
