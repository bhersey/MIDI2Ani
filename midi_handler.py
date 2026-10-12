import queue
import threading

import bpy
from bpy.app.handlers import persistent

from . import custom_properties

_PORT_KEYWORD = "IAC"
_POLL_SECONDS = 0.002
_RETRY_SECONDS = 1.0
_DRAIN_INTERVAL = 1 / 60
_SIZE = 128
_last_error = None
_initialised = False

# Items are (kind, index, value) tuples of plain ints; never bpy objects.
_queue = queue.Queue(maxsize=4096)
_stop_event = threading.Event()
_thread = None


def _find_port_name(mido):
    for name in mido.get_input_names():
        if _PORT_KEYWORD.lower() in name.lower():
            return name
    return None


def _worker(stop_event):
    # Runs off the main thread: must not touch bpy.
    try:
        import mido
    except ImportError as exc:
        print(f"[MIDI2Ani] mido unavailable: {exc}")
        return

    while not stop_event.is_set():
        try:
            name = _find_port_name(mido)
            if name is None:
                stop_event.wait(_RETRY_SECONDS)
                continue
            # The context manager closes the port on every exit path.
            with mido.open_input(name) as port:
                while not stop_event.is_set():
                    for msg in port.iter_pending():
                        item = _to_item(msg)
                        if item is None:
                            continue
                        try:
                            _queue.put_nowait(item)
                        except queue.Full:
                            pass  # drop rather than block the MIDI thread
                    stop_event.wait(_POLL_SECONDS)
        except Exception as exc:
            print(f"[MIDI2Ani] MIDI error: {exc}")
            stop_event.wait(_RETRY_SECONDS)


def _to_item(msg):
    try:
        if msg.type == "control_change":
            kind, index, value = "cc", msg.control, msg.value
        elif msg.type == "note_on":
            kind, index, value = "note", msg.note, msg.velocity
        elif msg.type == "note_off":
            kind, index, value = "note", msg.note, 0
        else:
            return None
    except AttributeError:
        return None
    if not (0 <= index < _SIZE):
        return None
    return (kind, index, max(0, min(127, int(value))))


def start_thread():
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(
        target=_worker, args=(_stop_event,), name="MIDI2Ani-input", daemon=True
    )
    _thread.start()


def stop_thread():
    global _thread
    _stop_event.set()
    if _thread is not None:
        _thread.join(timeout=2.0)
        _thread = None
    while True:
        try:
            _queue.get_nowait()
        except queue.Empty:
            break


def drain_queue():
    """Main-thread only: move queued MIDI data into scene properties."""
    cc = {}
    notes = {}
    try:
        while True:
            kind, index, value = _queue.get_nowait()
            (cc if kind == "cc" else notes)[index] = value  # last value wins
    except queue.Empty:
        pass

    if not cc and not notes:
        return

    global _last_error
    try:
        scene = bpy.context.scene
        if scene is None:
            return
        custom_properties.ensure(scene)
        cc_arr = scene[custom_properties.CC_KEY]
        note_arr = scene[custom_properties.NOTE_KEY]
        for index, value in cc.items():
            cc_arr[index] = value
        for index, value in notes.items():
            note_arr[index] = value
        # ID-property writes don't tag the depsgraph, so drivers need an explicit nudge.
        scene.update_tag()
    except Exception as exc:
        # Context can be restricted/unavailable (e.g. during file load); drop this batch.
        msg = str(exc)
        if msg != _last_error:
            _last_error = msg
            print(f"[MIDI2Ani] could not write MIDI data: {msg}")


# `scene_update_pre` was removed in Blender 2.8; `depsgraph_update_pre` replaces it.
_PRE_HANDLERS = bpy.app.handlers.depsgraph_update_pre


@persistent
def _on_update_pre(*_args):
    drain_queue()


@persistent
def _on_load_post(*_args):
    _ensure_all_safe()


def _ensure_all_safe():
    try:
        custom_properties.ensure_all()
    except Exception as exc:
        print(f"[MIDI2Ani] could not initialise scene properties: {exc}")


def _timer():
    # Handlers only fire on depsgraph changes, so this keeps data live while idle.
    global _initialised
    if not _initialised:
        _ensure_all_safe()  # first tick: bpy.data is fully available here
        _initialised = True
    drain_queue()
    return _DRAIN_INTERVAL


def register():
    global _initialised
    _initialised = False
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)
    if _on_update_pre not in _PRE_HANDLERS:
        _PRE_HANDLERS.append(_on_update_pre)
    if not bpy.app.timers.is_registered(_timer):
        bpy.app.timers.register(_timer, persistent=True)
    start_thread()


def unregister():
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
    if bpy.app.timers.is_registered(_timer):
        bpy.app.timers.unregister(_timer)
    if _on_update_pre in _PRE_HANDLERS:
        _PRE_HANDLERS.remove(_on_update_pre)
    stop_thread()
