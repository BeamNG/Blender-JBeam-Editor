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
