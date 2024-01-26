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

import os
import tkinter as tk
from tkinter import filedialog
from zipfile import ZipFile


def select_folder(prompt):
    """Prompts the user to select a folder."""
    root = tk.Tk()
    root.withdraw()  # Hide the main window.
    folder_path = filedialog.askdirectory(title=prompt)
    return folder_path


def extract_files(src_folder, dest_folder):
    """Extracts files with a given extension from all zip files in the source folder."""
    for item in os.listdir(src_folder):
        if item.endswith('.zip'):
            file_path = os.path.join(src_folder, item)
            with ZipFile(file_path, 'r') as zip_ref:
                # Extract only files with the specified extension
                for file_info in zip_ref.infolist():
                    filename = file_info.filename
                    if filename.endswith('.jbeam') or filename.endswith('.pc'):
                        zip_ref.extract(file_info, dest_folder)


source_folder = select_folder("Select the \"vehicles\" folder containing all the vehicles' zip files")
destination_folder = select_folder("Select the folder to extract to")
extract_files(source_folder, destination_folder)
