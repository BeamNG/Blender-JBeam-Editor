# JBeam Editor Blender Plugin

This Blender plugin allows you to create JBeam parts from scratch, import existing JBeam parts, modify them, and export them to a new or existing JBeam file, all within Blender, requiring **no** copying and pasting of JBeam code!

## Current Features

* Create JBeam from scratch
* Import JBeam files
* Move nodes
* Rename nodes
* Add/delete nodes
* Undo/redo changes
* Export changes directly to JBeam file

## Documentation

Find more information about installing and using this plugin at:
https://documentation.beamng.com/modding/vehicle/tutorials/jbeam_editor_blender_plugin/

## Development Instructions (requires Python 3)

**Plugin Testing Instructions:**

1. Download the *blender-addon-tester* library (https://github.com/angelo234/blender-addon-tester) and place it somewhere on your computer.
2. In *test_blender_plugin.py*, set the path to where you installed the testing library (default reference location is *D:\\blender-addon-tester*) by modifying this variable `blender_addon_tester_dir = "D:\\blender-addon-tester"`
3. Run *test_blender_plugin.bat*

**Build Instructions:**

* Build automatically
    1. Run *build.bat*
* Build manually yourself
    1. Zip the *.py files in the root directory like so:
        * blender_jbeam_editor.zip
            * jbeam_editor (folder)
                * *.py files