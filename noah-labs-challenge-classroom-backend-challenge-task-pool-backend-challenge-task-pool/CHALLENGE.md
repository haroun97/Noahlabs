# Backend Challenge: Postgres-Backed Task Pool

> Original Noah Labs challenge brief (for reference).

## Goal

Build a simple task pool system backed by PostgreSQL. It must support:

- Multiple `producers` and multiple `consumers` in parallel
- Multiple message types (i.e. `topics`)
- A `task` must never be processed twice
- Tasks can fail, failed tasks must be retained for further inspection and not re-processed
- Tasks do _not_ need to processed in any specific order

## Challenge Overview

### Task Pool functions

- Implement a reusable `add_task(...)` function that takes the required arguments to put a `task` in the pool.
- Implement a reusable `get_task(...)` function that takes the required arguments to get a `task` from the pool and process it.

### Producer Script

Use `add_task` to submit example jobs for two topics:

- `predict_voice`
  - Payload:
    - `user_id` (UUID)
    - `audio_s3_url` (string)
- `raise_voice_alert`
  - Payload:
    - `user_id` (UUID)
    - `measured_at` (datetime)
    - `audio_quality` (float, interval [0,1])
    - `voice_score` (float, interval [0,1])

### Consumer Script

- Fetches the next available task(s) for processing
- Safely supports multiple processes working in parallel
- Marks tasks complete once processed or failed
- You can use a `sleep` to simulate processing the tasks.

## Acceptance Criteria

### End-to-End Scripts

- You can produce and consume jobs for the two topics (`predict_voice` and `raise_voice_alert`) with their respective payloads via your scripts.

### Typing First

- Leverage the type system to express all payloads and function contracts, as well as your invariants and assumptions across the code. Type-level programming (i.e. generics) is encouraged.

### Documentation

- Provide a README that explains how to set up, run the producer, and start one or more consumers.

### Concurrent Consumers

- The consumer script works correctly when run in multiple containers simultaneously.
