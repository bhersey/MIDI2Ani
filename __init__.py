from . import custom_properties, midi_handler


def register():
    custom_properties.register()
    midi_handler.register()


def unregister():
    # Handlers/timer first, then the thread (closes the port), then the properties.
    midi_handler.unregister()
    custom_properties.unregister()
