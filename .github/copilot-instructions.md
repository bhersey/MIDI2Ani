# MIDI2Ani

Blender add-on (extension format, `blender_manifest.toml`, Blender ≥ 4.5, macOS only) that streams live MIDI Note/CC data from the macOS IAC Driver into scene properties so they can drive animation (drivers/nodes).

## Git / remote

- The repository's `origin` must use the owner's **personal** GitHub account, not the account linked to Copilot. Never set or push `origin` to the Copilot-linked account; ask the user for the personal account/URL if `origin` needs to be configured.

## Build / test / lint

No build system, tests, or linter exist. `bpy` is only available inside Blender, so code can't be run standalone. To try changes, install the folder as an extension in Blender (e.g. `blender --command extension build` from the repo root to produce a zip) and enable it.

`mido` and `python-rtmidi` are not yet bundled; `blender_manifest.toml` documents the `pip download ... -d wheels/` procedure (cp311 for Blender 4.5 LTS, cp313 for 5.2 LTS; arm64 and x64) and the `wheels = [...]` list to add.

## Architecture

- `__init__.py` – `register()`/`unregister()` order matters: custom_properties first, then the MIDI handler; unregister reverses this (stop handlers/timer/thread before deleting properties).
- `custom_properties.py` – stores `midi_cc_values` / `midi_note_values` as 128-int **ID properties** on the Scene (`scene["midi_cc_values"][n]`), not RNA properties: Blender caps RNA vector properties at 32 elements. `ensure(scene)` creates them; `register()` must not touch `bpy.data` (restricted during registration), so `ensure_all()` runs from a `load_post` handler and the first timer tick. Index = CC/note number; note value is velocity, note_off is 0.
- `midi_handler.py` – data pipeline:
  1. A daemon worker thread opens the first input port whose name contains "IAC" (retries every 1s if missing or on error) and polls with `iter_pending()`.
  2. Messages become plain `(kind, index, value)` tuples pushed to a bounded `queue.Queue` (dropped when full).
  3. On the main thread, `drain_queue()` collapses the queue (last value wins) and writes to the scene ID properties and calls `scene.update_tag()` (ID-prop writes don't tag the depsgraph). It's called from both a `depsgraph_update_pre` handler and a ~60 Hz persistent `bpy.app.timers` timer (handlers alone don't fire while idle).

## Conventions

- The worker thread must never touch `bpy`; only plain ints cross the queue. All `bpy` writes happen in `drain_queue()` on the main thread.
- Runtime MIDI/bpy errors must never propagate out of the timer/handlers: `_to_item` validates index/value ranges and `drain_queue` catches and logs (deduplicated) write failures.
- `mido` is imported lazily inside the worker so the add-on still loads if it's missing.
- Every register step needs a matching, idempotent unregister (check `is_registered` / list membership before removing).
- Only `control_change`, `note_on`, `note_off` are handled; extend `_to_item` for other message types.
