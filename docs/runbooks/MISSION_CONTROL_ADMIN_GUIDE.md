# Mission Control Admin Guide

## Purpose

This guide describes administrative review of Mission Control without changing
runtime or broker state.

## Admin Review Checklist

- Confirm branch and deployed build are approved.
- Confirm Mission Control routes are GET-only.
- Confirm source registry entries are present.
- Confirm final certification appears on the Certification and Readiness page.
- Confirm read-only permissions show no write routes or operator actions.
- Confirm secret-bearing fields are not displayed.

## RBAC Review

The RBAC console displays roles and permissions derived from existing CSS state.
It does not edit roles or assign permissions.

## Configuration Review

The configuration console displays safe non-secret summaries. Secrets,
credential material, token values, and private paths must remain redacted or
absent.
