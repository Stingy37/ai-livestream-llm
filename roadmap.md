# 🧭 AI Livestream System – Development Roadmap

This roadmap outlines the evolution of the **AI Livestream System** from its local (Colab) prototype to a cloud-hosted, modular architecture on AWS.  

---

## 🚧 Phase 1 — Organize & Stabilize Local Environment
**Goal:** Prepare the existing Colab codebase for deployment by modularizing, documenting, and validating async behaviors.

### ✅ Tasks
- [x] Restructure into subpackages (`core/`, `data/`, `generation/`, `diagnostics/`).
- [x] Add `__init__.py` files and fix all import paths.
- [x] Confirm async execution (`fetch_and_process_slot`, `generate_livestream`) is stable.
- [x] Add cleanup routines for ChromeDriver (`cleanup_chromedrivers()`).
- [x] Create centralized `configs.py` and `global_config` pattern.

**Outcome:**  
A clean, modular codebase that runs end-to-end in a single environment.

---

## ☁️ Phase 2 — EC2 Migration (Monolithic Setup)
**Goal:** Move the entire pipeline to a single EC2 instance and run it exactly as on Colab.

### ✅ Tasks
- [ ] Launch an Ubuntu EC2 instance.
- [ ] SSH into the instance 
- [ ] Clone the repository
- [ ] Refactor end-to-end scraping, TTS, and audio file generation to work on EC2.

**Outcome:**  
System runs reliably on a cloud machine, independent of Colab.

---

## 🔊 Phase 3 — Real-Time Streaming via WebSocket
**Goal:** Enable near-real-time delivery of audio and metadata for “live” playback.

### ✅ Tasks
- [ ] Add a `WebSocket /livestream` endpoint to FastAPI.
- [ ] Stream messages as JSON
- [ ] Client listens for updates and queues audio in sync.
- [ ] Handle session lifecycle: connect, send initial config, receive scene updates.
- [ ] Log connection events and dropped sockets for diagnostics.

**Outcome:**  
Client receives audio scene-by-scene in real time.

---
## 🗄️ Phase 4 — Modular Cloud Architecture
**Goal:** Split the system into logical AWS components

### ✅ Tasks
 - [ ] Store generated audio and images in S3
 - [ ] Move logs to CloudWatch
 - [ ] Move metadata (scene history, config) to DynamoDB or RDS.
 - [ ] Place FastAPI server in public subnet, worker/scraper in private subnet.
 - [ ] Use IAM roles for secure internal communication.
 - [ ] Configure VPC routing, security groups, and subnet isolation.

**Outcome:**  
A secure, scalable architecture.


