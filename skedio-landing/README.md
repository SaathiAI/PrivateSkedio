# SkedioAI Landing Page

This folder contains the landing page for SkedioAI.

Its role is different from the main application:

- the **main app** is where planning, progress, review, and study workflows happen
- the **landing page** is where the product is presented to someone visiting it for the first time

## What Is In This Folder

The landing page is a lightweight static site:

```text
skedio-landing/
├── index.html
├── styles.css
├── script.js
└── LANDING_PAGE_BRIEF.md
```

## Purpose

The landing page is meant to communicate:

- what SkedioAI is
- who it is for
- what kind of value it offers
- the feel and visual identity of the product

It is the presentation layer, not the operational study workspace.

## Relationship To The Main App

The main SkedioAI application lives in:

- `../Weekly-Study-Planner/`

That folder contains:

- the frontend app
- backend APIs
- agent system
- planning logic
- memory and database layers
- documentation for the product architecture

This landing page folder exists to complement that application with a public-facing entry point.

## Design Intent

The landing page should help a reviewer understand the product quickly:

- intelligent study planning
- calendar-aware scheduling
- progress tracking
- a more guided and supportive study workflow

## Summary

This folder is the marketing and presentation side of SkedioAI.

The actual product logic lives in the main application folder, while this folder gives the project a clearer first impression.
