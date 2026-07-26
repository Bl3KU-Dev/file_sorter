import os
import time

from sorter import categories, sort_single_file

POLL_INTERVAL_SECONDS = 2



def list_files(folder_path):
    """Returns the set of file names (not directories) currently in folder_path."""
    files = set()

    for name in os.listdir(folder_path):
        full_path = os.path.join(folder_path, name)

        if os.path.isfile(full_path):
            files.add(name)

    return files


def detect_and_sort(folder_path):
    folder_path = os.path.expanduser(folder_path)

    if not os.path.exists(folder_path):
        print(f"Error: ścieżka {folder_path} nie istnieje.")
        return

    if not os.path.isdir(folder_path):
        print(f"Error: {folder_path} nie jest folderem.")
        return

    print(f"Watching folder: {folder_path}")
    print("Bot is running. Press Ctrl+C to stop.")

    known_files = list_files(folder_path)

    try:
        while True:
            time.sleep(POLL_INTERVAL_SECONDS)
            current_files = list_files(folder_path)
            new_files = current_files - known_files

            for file_name in new_files:
                file_path = os.path.join(folder_path, file_name)
                print(f"Detected new file: {file_name}")
                sort_single_file(file_path, categories)

            known_files = list_files(folder_path)

    except KeyboardInterrupt:
        print("\nBot stopped.")


if __name__ == "__main__":
    folder = input("Podaj ścieżkę do folderu do obserwowania: ")
    detect_and_sort(folder)
