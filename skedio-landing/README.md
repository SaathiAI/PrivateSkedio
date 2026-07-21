# SkedioAI Landing Page

This folder contains the landing page for SkedioAI.

Its role is different from the main application:

- the **main app** is where planning, progress, review, and study workflows happen
- the **landing page** is where the product is presented to someone visiting it for the first time

These should not share the same public link.
The landing page and the app should be deployed as separate entry points.

## What Is In This Folder

The landing page is a standalone Vite/React frontend:

```text
skedio-landing/
├── index.html
├── package.json
├── src/
│   ├── main.jsx
│   └── components/
│       ├── LandingPage.jsx
│       ├── LandingPage.css
│       └── orbiting-circles.jsx
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

## URL Split

Recommended split:

```text
Landing page: https://skedio.ai/
Main app:     https://app.skedio.ai/
```

Local development can follow the same idea with separate ports:

```text
Landing page: http://localhost:5174/
Main app:     http://localhost:5173/
```

Run the landing page:

```bash
cd /home/puneet/saathi/skedio-landing
npm run dev -- --host 0.0.0.0 --port 5174
```

Run the main app:

```bash
cd /home/puneet/saathi/Weekly-Study-Planner/saathi-ui
npm run dev -- --host 0.0.0.0 --port 5173
```

The landing page should send users to the app through a clear CTA such as:

```text
Open SkedioAI
```

The app should remain its own workspace.
It should not be treated as another section of the landing page.

## Design Intent

The landing page should help a reviewer understand the product quickly:

- intelligent study planning
- calendar-aware scheduling
- progress tracking
- a more guided and supportive study workflow

## Summary

This folder is the marketing and presentation side of SkedioAI.

The actual product logic lives in the main application folder, while this folder gives the project a clearer first impression.
