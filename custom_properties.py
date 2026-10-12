import bpy

# RNA vector properties are capped at 32 elements, so 128-slot arrays are stored as
# ID properties instead. Read from drivers as scene["midi_cc_values"][n].
# Index = CC number / note number; value = raw 0-127 (note value is velocity, 0 = off).
CC_KEY = "midi_cc_values"
NOTE_KEY = "midi_note_values"
_KEYS = (CC_KEY, NOTE_KEY)
_SIZE = 128


def ensure(scene):
    for key in _KEYS:
        arr = scene.get(key)
        if arr is None or len(arr) != _SIZE:
            scene[key] = [0] * _SIZE


def ensure_all():
    for scene in bpy.data.scenes:
        ensure(scene)


def register():
    # bpy.data is restricted during registration; callers use ensure_all() later
    # (load_post handler / first timer tick) instead.
    pass


def unregister():
    pass
