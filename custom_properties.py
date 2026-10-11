import bpy
from bpy.props import IntVectorProperty


def register():
    # Index = CC number / note number; value = raw 0-127 (note value is velocity, 0 = off).
    bpy.types.Scene.midi_cc_values = IntVectorProperty(
        name="MIDI CC Values", size=128, min=0, max=127, default=(0,) * 128
    )
    bpy.types.Scene.midi_note_values = IntVectorProperty(
        name="MIDI Note Velocities", size=128, min=0, max=127, default=(0,) * 128
    )


def unregister():
    del bpy.types.Scene.midi_note_values
    del bpy.types.Scene.midi_cc_values
