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

import datetime
import os
import zipfile

# get the current date and time
now = datetime.datetime.now()

# format the date and time as a string to use as a timestamp
timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')

# specify the root directory to be zipped
root_dir = os.path.join(os.getcwd(), 'jbeam_editor')

readme_dir = os.path.join(os.getcwd(), 'README.md')
license_dir = os.path.join(os.getcwd(), 'LICENSE.txt')
blender_png_dir = os.path.join(os.getcwd(), 'blender.png')

# specify the name and path of the output zip file
output_filename = f'blender_jbeam_editor_{timestamp}.zip'

# create a ZipFile object with the output file name and mode
with zipfile.ZipFile(output_filename, 'x', zipfile.ZIP_DEFLATED) as zipf:
    # iterate over all the files and folders in the root directory
    for root, dirs, files in os.walk(root_dir):
        relative_path = os.path.relpath(root, root_dir)
        if relative_path.endswith('__pycache__'):
            continue

        for file in files:
            #print(root)
            file_path = os.path.join(root, file)
            relative_path = 'jbeam_editor\\' + os.path.relpath(file_path, root_dir)
            zipf.write(file_path, arcname=relative_path)

    zipf.write(readme_dir, arcname='jbeam_editor\\README.md')
    zipf.write(license_dir, arcname='jbeam_editor\\LICENSE.txt')
    zipf.write(blender_png_dir, arcname='jbeam_editor\\blender.png')