import bpy

import re

from . import import_vehicle
from . import import_jbeam
from . import utils

SCENE_PREV_TEXTS = 'jbeam_editor_text_editor_files_text'
#SCENE_FULL_TO_SHORT_FILENAME = 'jbeam_editor_text_editor_full_to_short_filename'
SCENE_SHORT_TO_FULL_FILENAME = 'jbeam_editor_text_editor_short_to_full_filename'

regex = re.compile(r'^.*/vehicles/(.*)$')


def _get_short_jbeam_path(path: str):
    match = re.match(regex, path)
    if match is not None:
        return match.group(1)
    return None


def _to_short_filename(filename: str):
    new_filename = _get_short_jbeam_path(filename)
    if new_filename is None:
        new_filename = filename
    return new_filename[max(0, len(new_filename) - 60):] # roughly 60 character limit


def write_file_from_disk(filepath: str):
    filetext = utils.read_file(filepath)
    if filetext is None:
        return None
    write_file(filepath, filetext)
    return filetext


def write_file(filename: str, text: str):
    scene = bpy.context.scene

    # this full to short filename BS because of 63 character key limit...

    short_filename = _to_short_filename(filename)
    if SCENE_SHORT_TO_FULL_FILENAME not in scene:
        #scene[SCENE_FULL_TO_SHORT_FILENAME] = {}
        scene[SCENE_SHORT_TO_FULL_FILENAME] = {}

    #scene[SCENE_FULL_TO_SHORT_FILENAME][filename] = short_filename
    scene[SCENE_SHORT_TO_FULL_FILENAME][short_filename] = filename

    if short_filename not in bpy.data.texts:
        bpy.data.texts.new(short_filename)
    file = bpy.data.texts[short_filename]
    file.clear()
    file.write(text)

    if SCENE_PREV_TEXTS not in scene:
        scene[SCENE_PREV_TEXTS] = {}
    scene[SCENE_PREV_TEXTS][short_filename] = text


def read_file(filename: str, get_from_disk_if_not_exist=False) -> str | None:
    short_filename = _to_short_filename(filename)
    text: bpy.types.Text | None = bpy.data.texts.get(short_filename)
    if text is None:
        if get_from_disk_if_not_exist:
            filetext = write_file_from_disk(filename)
            if filetext is None:
                return None
        else:
            return None
    else:
        filetext = text.as_string()
    return filetext


def show_file(filename: str):
    short_filename = _to_short_filename(filename)
    text: bpy.types.Text | None = bpy.data.texts.get(short_filename)
    if text is None:
        return

    text_area = None
    for area in bpy.context.screen.areas:
        if area.type == "TEXT_EDITOR":
            text_area = area
            break

    if text_area is None:
        return

    if text_area.spaces[0].text != text:
        text_area.spaces[0].text = text


def check_files_for_changes(context: bpy.types.Context):
    scene = context.scene

    if SCENE_PREV_TEXTS not in scene:
        return

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
    last_file_text = scene[SCENE_PREV_TEXTS].get(short_filename)
    if last_file_text is None:
        return
    filename = scene[SCENE_SHORT_TO_FULL_FILENAME].get(short_filename)
    if filename is None:
        return

    if curr_file_text != last_file_text:
        # File changed!
        scene[SCENE_PREV_TEXTS][short_filename] = curr_file_text

        import_vehicle.on_file_change(context, filename, curr_file_text)
        import_jbeam.on_file_change(context, filename, curr_file_text)
