---
title: Release checklist
---
# Release checklist

## Before tagging

Changelog updated, migrations reviewed, the full test suite green on `main`,
dependency audit clean.

## Tagging

Tag `vMAJOR.MINOR.PATCH` on `main`, push the tag, wait for the pipeline to
publish the artifact.

## After release

Deploy to staging on `staging.example.com`, run the smoke tests, then promote
to production. Watch the error rate for thirty minutes.

## Rollback

Redeploy the previous tag. Never revert a migration by hand; write a new one.
