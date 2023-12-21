# Copyright (c) 2023 BeamNG GmbH, Angelo Matteo
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import bpy

import re

from . import constants
from . import import_vehicle
from . import import_jbeam
from . import utils

SCENE_PREV_TEXTS = 'jbeam_editor_text_editor_files_text'
#SCENE_FULL_TO_SHORT_FILENAME = 'jbeam_editor_text_editor_full_to_short_filename'
SCENE_SHORT_TO_FULL_FILENAME = 'jbeam_editor_text_editor_short_to_full_filename'

regex = re.compile(r'^.*/vehicles/(.*)$')

history_stack = []
history_stack_idx = -1

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
    context = bpy.context
    scene = context.scene

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
    curr_line, curr_char = file.current_line_index, file.current_character
    file.clear()
    file.write(text)
    file.cursor_set(curr_line, character=curr_char)

    if SCENE_PREV_TEXTS not in scene:
        scene[SCENE_PREV_TEXTS] = {}
    if short_filename not in scene[SCENE_PREV_TEXTS]:
        scene[SCENE_PREV_TEXTS][short_filename] = None

    #check_files_for_changes(context)


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


def check_open_file_for_changes(context: bpy.types.Context, undoing_redoing=False):
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
    last_file_text = scene[SCENE_PREV_TEXTS].get(short_filename, False)
    if last_file_text == False:
        return
    filename = scene[SCENE_SHORT_TO_FULL_FILENAME].get(short_filename)
    if filename is None:
        return

    files_changed = None

    if curr_file_text != last_file_text:
        # File changed!
        if constants.DEBUG:
            print('file changed!')

        scene[SCENE_PREV_TEXTS][short_filename] = curr_file_text

        import_vehicle.on_file_change(context, filename, curr_file_text)
        import_jbeam.on_file_change(context, filename, curr_file_text)

        if files_changed is None:
            files_changed = {}
        files_changed[short_filename] = curr_file_text

    if not undoing_redoing and files_changed is not None:
        # Insert new history into history stack
        # Overwrite history when stack idx is len(stack) - 1
        global history_stack, history_stack_idx
        history_stack_idx += 1
        history_stack.insert(history_stack_idx, files_changed)
        history_stack = history_stack[:history_stack_idx + 1]

        if constants.DEBUG:
            print('len(history_stack)', len(history_stack))
            print('history_stack_idx', history_stack_idx)


def check_files_for_changes(context: bpy.types.Context, filenames: list, undoing_redoing=False):
    scene = context.scene

    if SCENE_PREV_TEXTS not in scene:
        return

    files_changed = None

    for filename in filenames:
        short_filename = _to_short_filename(filename)
        text = bpy.data.texts[short_filename]
        curr_file_text = text.as_string()
        last_file_text = scene[SCENE_PREV_TEXTS].get(short_filename, False)
        if last_file_text == False:
            return
        filename = scene[SCENE_SHORT_TO_FULL_FILENAME].get(short_filename)
        if filename is None:
            return

        if curr_file_text != last_file_text:
            # File changed!
            if constants.DEBUG:
                print('file changed!', filename)

            scene[SCENE_PREV_TEXTS][short_filename] = curr_file_text

            import_vehicle.on_file_change(context, filename, curr_file_text)
            import_jbeam.on_file_change(context, filename, curr_file_text)

            if files_changed is None:
                files_changed = {}
            files_changed[short_filename] = curr_file_text

    if not undoing_redoing and files_changed is not None:
        # Insert new history into history stack
        # Overwrite history when stack idx is len(stack) - 1
        global history_stack, history_stack_idx
        history_stack_idx += 1
        history_stack.insert(history_stack_idx, files_changed)
        history_stack = history_stack[:history_stack_idx + 1]

        if constants.DEBUG:
            print('len(history_stack)', len(history_stack))
            print('history_stack_idx', history_stack_idx)


def on_undo_redo(context: bpy.types.Context, undoing: bool):
    scene = context.scene

    if SCENE_SHORT_TO_FULL_FILENAME not in scene or SCENE_PREV_TEXTS not in scene:
        return

    global history_stack_idx

    if history_stack_idx == -1:
        return

    if undoing:
        history_stack_idx -= 1
    else:
        history_stack_idx += 1

    history_stack_idx = utils.clamp(history_stack_idx, 0, len(history_stack) - 1)

    if constants.DEBUG:
        print('len(history_stack)', len(history_stack))
        print('history_stack_idx', history_stack_idx)

    entry = history_stack[history_stack_idx]
    filepaths = []

    for short_filename, text in entry.items():
        if short_filename not in bpy.data.texts:
            return

        file = bpy.data.texts[short_filename]

        curr_line, curr_char = file.current_line_index, file.current_character
        file.clear()
        file.write(text)
        file.cursor_set(curr_line, character=curr_char)

        filepaths.append(scene[SCENE_SHORT_TO_FULL_FILENAME].get(short_filename))

    check_files_for_changes(context, filepaths, True)
