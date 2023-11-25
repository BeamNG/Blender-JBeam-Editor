import bpy

import re

SCENE_PREV_TEXTS = 'jbeam_editor_files_text'
SCENE_FULL_TO_SHORT_FILENAME = 'jbeam_editor_full_to_short_filename'
SCENE_SHORT_TO_FULL_FILENAME = 'jbeam_editor_short_to_full_filename'

def init():
    bpy.types.Scene.jbeam_editor_files_text = {}
    bpy.types.Scene.jbeam_editor_full_to_short_filename = {}
    bpy.types.Scene.jbeam_editor_short_to_full_filename = {}


def _get_short_jbeam_path(path: str):
    match = re.match(r'^.*/vehicles/(.*)$', path)
    if match is not None:
        return match.group(1)
    return None


def _to_short_filename(filename: str):
    new_filename = _get_short_jbeam_path(filename)
    if new_filename is None:
        new_filename = filename
    return new_filename[max(0, len(new_filename) - 60):] # roughly 60 character limit


def write_file(filename: str, text: str):
    scene = bpy.context.scene

    short_filename = _to_short_filename(filename)
    scene.jbeam_editor_full_to_short_filename[filename] = short_filename
    scene.jbeam_editor_short_to_full_filename[short_filename] = filename

    if short_filename not in bpy.data.texts:
        bpy.data.texts.new(short_filename)
    file = bpy.data.texts[short_filename]
    file.clear()
    file.write(text)
    scene.jbeam_editor_files_text[short_filename] = text


def read_file(filename: str) -> str | None:
    scene = bpy.context.scene

    short_filename = scene.jbeam_editor_full_to_short_filename.get(filename)
    if short_filename is None:
        return None

    text: bpy.types.Text | None = bpy.data.texts.get(short_filename)
    if text is None:
        return None
    return text.as_string()


'''def register_file_change_callback(filename: str, callback: function):


def remove_file_change_callback(filename: str, callback: function):'''



def show_file(filename: str):
    scene = bpy.context.scene

    short_filename = scene.jbeam_editor_full_to_short_filename.get(filename)
    if short_filename is None:
        return

    text = bpy.data.texts.get(short_filename)
    if text is None:
        return

    text_area = None
    for area in bpy.context.screen.areas:
        if area.type == "TEXT_EDITOR":
            text_area = area
            break

    if text_area is not None:
        if text_area.spaces[0].text != text:
            text_area.spaces[0].text = text

from . import constants
from . import utils
from . import import_vehicle

def check_files_for_changes():
    context = bpy.context
    scene = context.scene

    # If active file changed, reimport jbeam file/vehicle
    text = None
    text_area = None
    for area in context.screen.areas:
        if area.type == "TEXT_EDITOR":
            text_area = area
            break

    if text_area is not None:
        text = text_area.spaces[0].text
    if text is None:
        return

    short_filename, curr_file_text = text.name, text.as_string()
    last_file_text = scene.jbeam_editor_files_text.get(short_filename)
    if last_file_text is None:
        return
    filename = scene.jbeam_editor_short_to_full_filename.get(short_filename)
    if filename is None:
        return

    if curr_file_text != last_file_text:
        # File changed!
        scene.jbeam_editor_files_text[short_filename] = curr_file_text

        veh_collection = context.collection
        if veh_collection.get(constants.COLLECTION_VEHICLE_MODEL) is None:
            return

        # import cProfile, pstats, io
        # import pstats
        # pr = cProfile.Profile()
        # with cProfile.Profile() as pr:
        #     import_vehicle.reimport_vehicle(veh_collection, blender_filepath)
        #     stats = pstats.Stats(pr)
        #     stats.strip_dirs().sort_stats('cumtime').print_stats()

        # Check if jbeam file is parseable before reimporting vehicle
        data = utils.sjson_decode(curr_file_text, filename)
        if data is None:
            return
        import_vehicle.reimport_vehicle(veh_collection, filename)
