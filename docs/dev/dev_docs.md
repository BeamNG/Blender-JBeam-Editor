## Blender JBeam Editor Developer Documentation

### Introduction
This is the developer's documentation for the Blender JBeam Editor.

**[Python 3](https://www.python.org/downloads/) is required to use the development tools below.**

### Plugin Development
I recommend developing this Blender plugin (or any Blender plugin) in Visual Studio Code (VSC) with the following addons:
- [Python VSC extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python) (you should be prompted to install this when opening a Python file)
- [Blender Development VSC extension](https://marketplace.visualstudio.com/items?itemName=JacquesLucke.blender-development) makes it easy to run and debug your code
- [fake-bpy-module-latest](https://pypi.org/project/fake-bpy-module-latest/) for auto code completion

### Plugin Testing
This repository contains a test suite to make sure that the plugin's functionalities work as expected. A test case imports a JBeam file, performs certain actions (e.g. moving a node to a certain position in Blender) and exports the changes to a JBeam file, and checks if the result matches an expected JBeam file (e.g. the node is moved to that expected location in the JBeam file).

#### Testing Setup
1. Download the *blender-addon-tester* library (https://github.com/angelo234/blender-addon-tester) and place it somewhere on your computer.
2. In *test_blender_plugin.py*, set the path to where you installed the testing library (default reference location is *D:\\blender-addon-tester*) by modifying this variable `blender_addon_tester_dir = "D:\\blender-addon-tester"`
3. Run *test_blender_plugin.bat* which runs all tests located in *tests* folder

#### Creating Tests
Tests are located in *tests* folder and have the following file structure:
* test_suite_name
    * test_case_name (multiple test cases can exist)
        * original (contains starting JBeam files)
        * expected (contains expected result JBeam files)
        * import.json (declares which JBeam file and part to import)
    * test_suite.py (runs the test cases)

You can look at the current test suites to get an idea of how to create a test.

### Plugin Building
* Build automatically
    1. Run *build.bat*
* Build manually yourself
    1. Zip the *.py files in the root directory like so:
        * blender_jbeam_editor.zip
            * jbeam_editor (folder)
                * *.py files
