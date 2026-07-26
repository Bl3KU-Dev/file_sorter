# file sorter
A blazing-fast, zero-dependency file organizer written in pure Python.

Drop it into any messy folder — Downloads, Desktop, a shared drive, whatever — and in seconds your chaos becomes order. No install wizards, no config files, no bloat. Just clean, instant organization.

---

 Features,
Instant sorting — organizes an entire directory in seconds, even with thousands of files,
Zero dependencies — runs on the Python standard library alone,
Cross-platform — works identically on Windows, macOS, and Linux,
Simple by design — one file, no config, no setup,


 Supported File Types,
| Category | Extensions |
|---|---|
|  Images | .jpg, .png, .gif, .svg, .webp |
|  Documents | .pdf, .docx, .xlsx, .pptx |
|  Files | .txt, .csv |
|  Packages | .zip, .tar, .gz, .tar.gz, .deb, .rpm, .apk, .tar.bz2, .7z |

More categories can be added by editing a single dictionary in the source — no architectural changes required.

git clone https://github.com/yourusername/file_sorter.git
cd file_sorter


That's it. There is nothing to pip install.

 Usage,
python3 code.py


When prompted, paste the path to the directory you want organized. File Sorter scans it, sorts matching files into images/, documents/, files/, and packages/ subfolders, and leaves everything else untouched.

 Example,
Before:
Downloads/
├── vacation_photo.jpg
├── invoice_march.pdf
├── notes.txt
├── project_archive.zip
├── budget.xlsx


After:
Downloads/
├── images/
│   └── vacation_photo.jpg
├── documents/
│   ├── invoice_march.pdf
│   └── budget.xlsx
├── files/
│   └── notes.txt
├── packages/
│   └── project_archive.zip


 License,
This project is licensed under the MIT License — do whatever you'd like with it.
