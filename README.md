# IMUSI

This repository contains the **IMUSI** local music player project, consisting of:

- **backend/** – FastAPI + SQLAlchemy backend API (SQLite) with authentication, song import, and streaming.
- **mobile/** – React Native (Expo) client app that talks to the backend and plays audio.

See each subfolder for detailed instructions; the top-level READMEs and docs are maintained inside `backend/README.md` and `mobile/README.md`.

## Getting started

1. Clone this repo and `cd` into it.
2. Follow the instructions in the appropriate subdirectory (`backend/README.md` or `mobile/README.md`).

## Ignored files

Generated artifacts such as virtual environments, build output, database files, and `node_modules` directories are excluded via the root `.gitignore`.

> **Note:** the backend is not packaged inside the mobile app; both components work independently and communicate over HTTP.
