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

import hashlib
import re

from . import constants
from . import import_vehicle
from . import import_jbeam
from . import utils

SCENE_PREV_TEXTS = 'jbeam_editor_text_editor_files_text'
#SCENE_FULL_TO_SHORT_FILENAME = 'jbeam_editor_text_editor_full_to_short_filename'
SCENE_SHORT_TO_FULL_FILENAME = 'jbeam_editor_text_editor_short_to_full_filename'

HISTORY_STACK_SIZE = 250

regex = re.compile(r'^.*/vehicles/(.*)$')

history_stack = []
history_stack_idx = -1

def _get_short_jbeam_path(path: str):
    match = re.match(regex, path)
    if match is not None:
        return match.group(1)
    return None


def _to_short_filename(filename: str):
    return hashlib.md5(filename.encode('UTF-8')).hexdigest()

    # new_filename = _get_short_jbeam_path(filename)
    # if new_filename is None:
    #     new_filename = filename
    # return new_filename[max(0, len(new_filename) - 60):] # roughly 60 character limit


def write_from_ext_to_int_file(filepath: str):
    filetext = utils.read_file(filepath)
    if filetext is None:
        return None
    write_int_file(filepath, filetext)
    return filetext


def write_from_int_to_ext_file(filepath: str):
    short_filename = _to_short_filename(filepath)
    text: bpy.types.Text | None = bpy.data.texts.get(short_filename)
    if text is None:
        return False

    res = utils.write_file(filepath, text.as_string())
    return res


def write_int_file(filename: str, text: str):
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


def read_int_file(filename: str) -> str | None:
    short_filename = _to_short_filename(filename)
    text: bpy.types.Text | None = bpy.data.texts.get(short_filename)
    if text is None:
        return None
    return text.as_string()


def delete_int_file(filename: str):
    short_filename = _to_short_filename(filename)
    text: bpy.types.Text | None = bpy.data.texts.get(short_filename)
    if text is None:
        return
    bpy.data.texts.remove(text)


def show_int_file(filename: str):
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


def check_open_int_file_for_changes(context: bpy.types.Context, undoing_redoing=False):
    scene = context.scene

    if SCENE_PREV_TEXTS not in scene:
        return False

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
        return False

    short_filename, curr_file_text = text.name, text.as_string()
    last_file_text = scene[SCENE_PREV_TEXTS].get(short_filename, False)
    if last_file_text == False:
        return False
    filename = scene[SCENE_SHORT_TO_FULL_FILENAME].get(short_filename)
    if filename is None:
        return False

    file_changed = False

    if curr_file_text != last_file_text:
        # File changed!
        if constants.DEBUG:
            print('file changed!', filename)

        scene[SCENE_PREV_TEXTS][short_filename] = curr_file_text

        import_vehicle.on_files_change(context, {filename: curr_file_text})
        import_jbeam.on_file_change(context, filename)
        file_changed = True

    if not undoing_redoing and file_changed:
        # Insert new history into history stack
        # Overwrite history when stack idx is len(stack) - 1
        global history_stack, history_stack_idx
        history_stack_idx += 1
        history_stack.insert(history_stack_idx, {short_filename: curr_file_text})
        history_stack = history_stack[:history_stack_idx + 1]

        if len(history_stack) > HISTORY_STACK_SIZE:
            history_stack.pop(0)

        if constants.DEBUG:
            print('len(history_stack)', len(history_stack))
            print('history_stack_idx', history_stack_idx)

    return file_changed


def check_int_files_for_changes(context: bpy.types.Context, filenames: list, undoing_redoing=False, reimport=True):
    scene = context.scene

    if SCENE_PREV_TEXTS not in scene:
        return

    files_changed_short_names = None
    files_changed = None

    for filename in filenames:
        short_filename = _to_short_filename(filename)
        text = bpy.data.texts[short_filename]
        curr_file_text = text.as_string()
        last_file_text = scene[SCENE_PREV_TEXTS].get(short_filename, False)
        if last_file_text == False:
            continue
        filename = scene[SCENE_SHORT_TO_FULL_FILENAME].get(short_filename)
        if filename is None:
            continue

        if curr_file_text != last_file_text:
            # File changed!
            if constants.DEBUG:
                print('file changed!', filename)

            scene[SCENE_PREV_TEXTS][short_filename] = curr_file_text

            if reimport:
                import_jbeam.on_file_change(context, filename)

            if files_changed_short_names is None:
                files_changed_short_names = {}
                files_changed = {}
            files_changed_short_names[short_filename] = curr_file_text
            files_changed[filename] = curr_file_text

    if reimport and files_changed is not None:
        import_vehicle.on_files_change(context, files_changed)

    if not undoing_redoing and files_changed_short_names is not None:
        # Insert new history into history stack
        # Overwrite history when stack idx is less than len(stack) - 1
        global history_stack, history_stack_idx
        history_stack_idx += 1
        history_stack.insert(history_stack_idx, files_changed_short_names)
        history_stack = history_stack[:history_stack_idx + 1]

        if len(history_stack) > HISTORY_STACK_SIZE:
            history_stack.pop(0)

        if constants.DEBUG:
            print('len(history_stack)', len(history_stack))
            print('history_stack_idx', history_stack_idx)


def check_all_int_files_for_changes(context: bpy.types.Context, undoing_redoing=False, reimport=True):
    scene = context.scene
    check_int_files_for_changes(context, scene[SCENE_SHORT_TO_FULL_FILENAME].values(), undoing_redoing, reimport)


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

    check_int_files_for_changes(context, filepaths, True)
