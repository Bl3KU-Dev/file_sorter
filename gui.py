#!/usr/bin/env python3
"""Sorter plików - interfejs w przeglądarce.

Nie duplikuje logiki: korzysta z funkcji z sorter.py i bot.py.

Podnosi lokalny serwer na 127.0.0.1 i otwiera stronę w domyślnej przeglądarce.
Zero zależności - sama biblioteka standardowa - więc działa wszędzie tam, gdzie
jest Python, i pakuje się PyInstallerem na Windows, macOS i Linux bez doginania.

Uruchomienie:  python gui.py
"""

import json
import os
import secrets
import sys
import threading
import webbrowser
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from bot import POLL_INTERVAL_SECONDS, list_files
from sorter import categories, sort_files, sort_single_file

# Serwer slucha tylko na petli zwrotnej, ale to za malo: dowolna strona
# otwarta w przegladarce moze strzelac na 127.0.0.1. Token wpisany w adres
# i wymagany w naglowku X-Token to blokuje - przegladarka nie ustawi
# wlasnego naglowka w zapytaniu z innej domeny bez zgody naszego serwera,
# a my na preflight nie odpowiadamy.
TOKEN = secrets.token_urlsafe(16)


def say(message):
    """print(), ktory nie wywala sie w trybie okienkowym (brak konsoli).

    flush=True jest konieczne: przy przekierowanym wyjsciu print buforuje
    blokowo i adres wisialby w buforze az do konca programu, czyli nigdy.
    """
    if sys.stdout is not None:
        print(message, flush=True)


class LogWriter:
    """Udaje plik: to, co sorter drukuje przez print(), trafia do logu."""

    def __init__(self, log_line):
        self.log_line = log_line
        self.buffer = ""

    def write(self, text):
        self.buffer += text

        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self.log_line(line)

    def flush(self):
        if self.buffer:
            self.log_line(self.buffer)
            self.buffer = ""


class State:
    """Stan aplikacji dzielony miedzy watkiem roboczym a zapytaniami HTTP."""

    def __init__(self):
        self.lock = threading.Lock()
        self.log = []
        self.status = "Gotowe."
        self.busy = False
        self.watching = False
        self.worker = None
        self.stop_event = threading.Event()

    def log_line(self, line):
        with self.lock:
            self.log.append(line)

    def set_status(self, text):
        with self.lock:
            self.status = text

    def clear_log(self):
        with self.lock:
            self.log.clear()

    def snapshot(self, since):
        with self.lock:
            return {
                "lines": self.log[since:],
                "total": len(self.log),
                "status": self.status,
                "busy": self.busy,
                "watching": self.watching,
            }

    def try_claim(self, watching):
        """Rezerwuje prawo do pracy. Sortowanie i obserwowanie nie moga isc
        naraz, bo oba podmieniaja globalny sys.stdout."""
        with self.lock:
            if self.busy:
                return False
            self.busy = True
            self.watching = watching
            return True

    def release(self):
        with self.lock:
            self.busy = False
            self.watching = False


state = State()


# ----------------------------------------------------------------------
# akcje
# ----------------------------------------------------------------------


def folder_problem(folder):
    """Zwraca opis problemu ze sciezka albo None, gdy jest w porzadku."""
    if not folder:
        return "Najpierw podaj folder."

    if not os.path.isdir(folder):
        return f"To nie jest folder: {folder}"

    return None


def run_sort(folder):
    try:
        with redirect_stdout(LogWriter(state.log_line)):
            sort_files(folder, categories)
    except OSError as error:
        state.log_line(f"Błąd: {error}")
        state.set_status("Sortowanie przerwane błędem.")
    else:
        state.set_status("Gotowe.")
    finally:
        state.release()


def run_watch(folder):
    state.log_line(f"Watching folder: {folder}")

    try:
        with redirect_stdout(LogWriter(state.log_line)):
            known_files = list_files(folder)

            # wait() zwraca True dopiero gdy ktos poprosil o stop
            while not state.stop_event.wait(POLL_INTERVAL_SECONDS):
                current_files = list_files(folder)

                for file_name in current_files - known_files:
                    state.log_line(f"Detected new file: {file_name}")
                    sort_single_file(os.path.join(folder, file_name), categories)

                known_files = list_files(folder)
    except OSError as error:
        state.log_line(f"Błąd: {error}")
    finally:
        state.log_line("Bot stopped.")
        state.set_status("Gotowe.")
        state.release()


def start_job(folder, watching):
    """Wspolny start dla obu trybow. Zwraca komunikat bledu albo None."""
    folder = os.path.expanduser(folder.strip())
    problem = folder_problem(folder)

    if problem is not None:
        state.set_status(problem)
        state.log_line(f"Error: {folder} nie jest folderem.")
        return problem

    if not state.try_claim(watching):
        return "Coś już jest w toku."

    state.stop_event.clear()
    state.set_status(f"Obserwuję {folder}" if watching else f"Sortuję {folder}…")

    target = run_watch if watching else run_sort
    state.worker = threading.Thread(target=target, args=(folder,), daemon=True)
    state.worker.start()
    return None


def list_subfolders(path):
    """Dane dla przegladarki katalogow na stronie."""
    path = os.path.abspath(os.path.expanduser(path or "~"))
    parent = os.path.dirname(path)

    try:
        names = sorted(os.listdir(path), key=str.lower)
    except OSError as error:
        return {"path": path, "parent": parent, "dirs": [], "error": str(error)}

    dirs = [
        name
        for name in names
        if not name.startswith(".") and os.path.isdir(os.path.join(path, name))
    ]
    return {"path": path, "parent": parent, "dirs": dirs, "error": None}


# ----------------------------------------------------------------------
# strona
# ----------------------------------------------------------------------

PAGE = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sorter plików</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #fbfbfd; --fg: #1a1a1c; --muted: #6b6b75;
    --card: #ffffff; --line: #e2e2e8; --accent: #2f6df6; --accent-fg: #fff;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #16161a; --fg: #e8e8ec; --muted: #9a9aa4;
      --card: #1e1e24; --line: #33333d; --accent: #5b8cff; --accent-fg: #0b0b0f;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 24px; background: var(--bg); color: var(--fg);
    font: 15px/1.5 system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  }
  .wrap { max-width: 860px; margin: 0 auto; }
  h1 { font-size: 20px; margin: 0 0 16px; }
  .card {
    background: var(--card); border: 1px solid var(--line);
    border-radius: 10px; padding: 16px; margin-bottom: 14px;
  }
  .row { display: flex; gap: 8px; flex-wrap: wrap; }
  input[type=text] {
    flex: 1 1 320px; min-width: 0; padding: 9px 11px; font: inherit;
    border: 1px solid var(--line); border-radius: 7px;
    background: var(--bg); color: var(--fg);
  }
  button {
    padding: 9px 15px; font: inherit; cursor: pointer;
    border: 1px solid var(--line); border-radius: 7px;
    background: var(--bg); color: var(--fg);
  }
  button:hover:not(:disabled) { border-color: var(--accent); }
  button:disabled { opacity: .45; cursor: default; }
  button.primary { background: var(--accent); color: var(--accent-fg); border-color: var(--accent); }
  .hint { color: var(--muted); font-size: 13px; margin-top: 10px; }
  #log {
    margin: 0; padding: 12px; height: 320px; overflow: auto;
    background: var(--bg); border: 1px solid var(--line); border-radius: 7px;
    font: 13px/1.45 ui-monospace, SFMono-Regular, Consolas, monospace;
    white-space: pre-wrap; word-break: break-word;
  }
  #status { color: var(--muted); font-size: 13px; margin-top: 10px; }
  dialog {
    border: 1px solid var(--line); border-radius: 10px; padding: 0;
    background: var(--card); color: var(--fg); width: min(560px, 92vw);
  }
  dialog::backdrop { background: rgba(0,0,0,.45); }
  .dlg-head, .dlg-foot { padding: 14px 16px; }
  .dlg-head { border-bottom: 1px solid var(--line); }
  .dlg-foot { border-top: 1px solid var(--line); display: flex; gap: 8px; justify-content: flex-end; }
  #here { font: 13px ui-monospace, monospace; color: var(--muted); word-break: break-all; }
  #dirs { list-style: none; margin: 0; padding: 6px; max-height: 46vh; overflow: auto; }
  #dirs li { padding: 8px 10px; border-radius: 6px; cursor: pointer; }
  #dirs li:hover { background: var(--bg); }
</style>
</head>
<body>
<div class="wrap">
  <h1>Sorter plików</h1>

  <div class="card">
    <div class="row">
      <input type="text" id="folder" placeholder="Ścieżka do folderu…">
      <button id="browse">Przeglądaj…</button>
    </div>
    <div class="row" style="margin-top:10px">
      <button id="sort" class="primary">Sortuj teraz</button>
      <button id="watch">Obserwuj folder</button>
      <button id="clear">Wyczyść log</button>
      <button id="quit" style="margin-left:auto">Zakończ</button>
    </div>
    <div class="hint" id="cats"></div>
  </div>

  <div class="card">
    <pre id="log"></pre>
    <div id="status">Gotowe.</div>
  </div>
</div>

<dialog id="picker">
  <div class="dlg-head"><div id="here"></div></div>
  <ul id="dirs"></ul>
  <div class="dlg-foot">
    <button id="cancel">Anuluj</button>
    <button id="pick" class="primary">Wybierz ten folder</button>
  </div>
</dialog>

<script>
const TOKEN = new URLSearchParams(location.search).get("t") || "";
const $ = (id) => document.getElementById(id);
let shown = 0, here = "";

async function api(path, body) {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-Token": TOKEN, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return res.json();
}

function render(s) {
  if (s.total < shown) { $("log").textContent = ""; shown = 0; }
  if (s.lines.length) {
    const atBottom = $("log").scrollTop + $("log").clientHeight >= $("log").scrollHeight - 20;
    $("log").textContent += s.lines.join("\\n") + "\\n";
    shown = s.total;
    if (atBottom) $("log").scrollTop = $("log").scrollHeight;
  }
  $("status").textContent = s.status;
  $("watch").textContent = s.watching ? "Zatrzymaj obserwowanie" : "Obserwuj folder";
  // W trakcie pracy blokujemy wszystko poza zatrzymaniem obserwowania.
  $("sort").disabled = s.busy;
  $("folder").disabled = s.busy;
  $("browse").disabled = s.busy;
  $("watch").disabled = s.busy && !s.watching;
}

async function poll() {
  try { render(await api("/api/state?since=" + shown)); } catch (e) {}
  setTimeout(poll, 500);
}

$("sort").onclick = () => api("/api/sort", { folder: $("folder").value });
$("watch").onclick = async () => {
  const s = await api("/api/state?since=" + shown);
  if (s.watching) api("/api/stop", {});
  else api("/api/watch", { folder: $("folder").value });
};
$("clear").onclick = async () => { await api("/api/clear", {}); $("log").textContent = ""; shown = 0; };
$("quit").onclick = async () => {
  await api("/api/quit", {});
  document.body.innerHTML = "<div class='wrap'><p>Zakończono. Możesz zamknąć tę kartę.</p></div>";
};

async function openAt(path) {
  const d = await api("/api/browse?path=" + encodeURIComponent(path));
  here = d.path;
  $("here").textContent = d.error ? d.path + "  —  " + d.error : d.path;
  $("dirs").innerHTML = "";
  const up = document.createElement("li");
  up.textContent = "⬅  .. (wyżej)";
  up.onclick = () => openAt(d.parent);
  $("dirs").appendChild(up);
  for (const name of d.dirs) {
    const li = document.createElement("li");
    li.textContent = "📁  " + name;
    li.onclick = () => openAt(d.path.replace(/\\/$/, "") + "/" + name);
    $("dirs").appendChild(li);
  }
}

$("browse").onclick = () => { openAt($("folder").value); $("picker").showModal(); };
$("cancel").onclick = () => $("picker").close();
$("pick").onclick = () => { $("folder").value = here; $("picker").close(); };

$("cats").textContent = "Kategorie: " + CATEGORIES.join(", ") + ", a reszta do Inne. Zmienisz je w sorter.py.";
$("folder").value = DEFAULT_FOLDER;
poll();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "SorterPlikow"

    def log_message(self, *args):
        pass  # bez zasmiecania konsoli kazdym zapytaniem

    # -- pomocnicze --------------------------------------------------

    def send_json(self, payload, code=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def token_ok(self):
        return secrets.compare_digest(self.headers.get("X-Token", ""), TOKEN)

    def read_body(self):
        length = int(self.headers.get("Content-Length") or 0)

        if not length:
            return {}

        try:
            return json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            return {}

    # -- trasy -------------------------------------------------------

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/":
            if not secrets.compare_digest(query.get("t", [""])[0], TOKEN):
                self.send_error(403, "Zly token")
                return

            page = PAGE.replace("CATEGORIES", json.dumps(list(categories))).replace(
                "DEFAULT_FOLDER", json.dumps(os.path.expanduser("~/Downloads"))
            )
            body = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if not self.token_ok():
            self.send_error(403, "Zly token")
            return

        if parsed.path == "/api/state":
            since = int(query.get("since", ["0"])[0] or 0)
            self.send_json(state.snapshot(since))
            return

        if parsed.path == "/api/browse":
            self.send_json(list_subfolders(query.get("path", [""])[0]))
            return

        self.send_error(404)

    def do_POST(self):
        if not self.token_ok():
            self.send_error(403, "Zly token")
            return

        path = urlparse(self.path).path
        data = self.read_body()

        if path == "/api/sort":
            self.send_json({"error": start_job(data.get("folder", ""), watching=False)})
            return

        if path == "/api/watch":
            self.send_json({"error": start_job(data.get("folder", ""), watching=True)})
            return

        if path == "/api/stop":
            state.stop_event.set()
            state.set_status("Zatrzymuję obserwowanie…")
            self.send_json({"error": None})
            return

        if path == "/api/clear":
            state.clear_log()
            self.send_json({"error": None})
            return

        if path == "/api/quit":
            self.send_json({"error": None})
            state.stop_event.set()
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        self.send_error(404)


def main():
    # port 0 = system przydziela wolny, wiec dwie kopie sobie nie wchodza w droge
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_port}/?t={TOKEN}"

    say("Sorter plików działa pod adresem:")
    say(f"  {url}")
    say("Zamknij kartę i wciśnij Ctrl+C, albo kliknij „Zakończ” na stronie.")

    threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        state.stop_event.set()
        say("Zakończono.")


if __name__ == "__main__":
    main()
