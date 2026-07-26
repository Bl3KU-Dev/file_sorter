import os
import shutil

# To sortuje pliki według kategorii i folderów.
categories = {
    "images": [".jpg", ".png", ".gif", ".svg", ".webp"],
    "documents": [".pdf", ".docx", ".xlsx", ".pptx"],
    "files": [".txt", ".csv"],
    "packages": [".zip", ".tar", ".gz", ".tar.gz", ".deb", ".rpm", ".apk", ".tar.bz2", ".7z"],
}


def sort_single_file(file_path, categories):
    """Sorts a single file into a category subfolder based on its extension."""
    if not os.path.isfile(file_path):
        return

    folder_path = os.path.dirname(file_path)
    file = os.path.basename(file_path)

    _, file_extension = os.path.splitext(file)
    rozszerzenie = file_extension.lower()
    przeniesiono = False

    for category, extensions in categories.items():
        if rozszerzenie in extensions:
            output_path = os.path.join(folder_path, category)
            os.makedirs(output_path, exist_ok=True)
            shutil.move(file_path, os.path.join(output_path, file))
            przeniesiono = True
            break

    if not przeniesiono:
        output_path = os.path.join(folder_path, "Inne")
        os.makedirs(output_path, exist_ok=True)
        shutil.move(file_path, os.path.join(output_path, file))

    print(f"Sorted: {file}")


def sort_files(input_path, categories):
    """Sorts every file currently in input_path."""
    if not os.path.exists(input_path):
        print(f"Error: ścieżka {input_path} nie istnieje.")
        return

    if not os.path.isdir(input_path):
        print(f"Error: {input_path} nie jest folderem.")
        return

    for file in os.listdir(input_path):
        file_path = os.path.join(input_path, file)

        if os.path.isdir(file_path):
            continue

        sort_single_file(file_path, categories)

    print("Gotowe, skończono sortowanie plików.")


if __name__ == "__main__":
    input_path = os.path.expanduser(input("Podaj ścieżkę do folderu: "))
    sort_files(input_path, categories)
