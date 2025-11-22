# AI-Orientierungshilfe für das pwnity-Projekt

Dieses Dokument dient als Orientierungshilfe für eine KI, um die Struktur, die Verantwortlichkeiten und die Kernkonzepte der `pwnity`-Applikation zu verstehen.

## 1. Grundlegendes Konzept

`pwnity` ist ein interaktives Kommandozeilen-Tool (CLI), das für Penetrationstests und CTFs entwickelt wurde. Es dient als zentraler Hub zur Verwaltung von Zielen (`targets`), externen Werkzeugen (`tools`), Wortlisten (`wordlists`), Berichten (`reports`) und anderen für einen Pentest relevanten Daten.

Die Anwendung ist modular aufgebaut und verwendet ein Manager-Pattern. Jeder "Manager" ist für die Verwaltung einer bestimmten Art von Entität zuständig (z.B. `TargetManager` für Ziele). Die meisten Manager erben von einem `JSONManager`, der grundlegende CRUD-Operationen für auf JSON-Dateien basierende Entitäten bereitstellt.

## 2. Verzeichnisstruktur & Verantwortlichkeiten

Die Hauptlogik befindet sich im `modules/`-Verzeichnis.

```
pwnity/
├── modules/
│   ├── managers/
│   │   ├── base_manager.py       # Abstrakte Basisklasse (JSONManager) für alle Manager.
│   │   ├── target_manager.py     # Verwaltet Ziele (IPs, Hostnames, URLs).
│   │   ├── tool_manager.py       # Konfiguriert externe Tools (nmap, gobuster, etc.).
│   │   ├── report_manager.py     # Verwaltet Reports, Notizen und Loot.
│   │   ├── wordlist_manager.py   # Verwaltet Referenzen auf Wortlist-Dateien.
│   │   ├── profile_manager.py    # Verwaltet globale Einstellungen (z.B. LHOST).
│   │   ├── proxy_manager.py      # Verwaltet globale und Session-Proxy-Einstellungen.
│   │   ├── library_manager.py    # Verwaltet eine Bibliothek von nützlichen Links/Ressourcen.
│   │   ├── manual_manager.py     # Verwaltet und zeigt interne Hilfeseiten (Manuals).
│   │   └── heartbeat_manager.py  # Überwacht die Erreichbarkeit von Zielen.
│   │
│   ├── services/
│   │   ├── config.py             # Lädt und stellt die globale Konfiguration (config.json) bereit.
│   │   ├── log.py                # Zentraler Logging-Service.
│   │   └── ...                   # Weitere Hilfsdienste.
│   │
│   ├── cli_sessions.py           # Definiert die CLISession-Klasse, die den Zustand hält.
│   ├── display_manager.py        # Zuständig für die formatierte Ausgabe mit `rich`.
│   ├── help_manager.py           # Generiert und zeigt kontextsensitive Hilfe an.
│   ├── job_manager.py            # Verwaltet Hintergrundprozesse.
│   ├── placeholders.py           # Löst dynamische Platzhalter wie `$target.ip` auf.
│   └── recon.py                  # Enthält den `ReconService` für die Informationsbeschaffung.
│
├── tests/                        # Unittests und Integrationstests.
│   ├── test_*.py                 # Die Tests sind eine exzellente Quelle, um das Verhalten der Module zu verstehen.
│
└── pwnity_cli.py                # Der Haupteinstiegspunkt der Anwendung.
```

## 3. Kernkomponenten im Detail

### `managers/base_manager.py`
- **Zweck**: Stellt die Basislogik für alle Manager bereit, die mit JSON-Dateien arbeiten.
- **Funktionen**:
  - CRUD: `create`, `load`, `update`, `delete` (Feld), `destroy` (Datei).
  - `rename`: Benennt eine Entität und ihre Datei um.
  - `exists`: Prüft, ob eine Entität existiert.
  - `list_all`: Listet alle Entitäten auf.
  - `dispatch`: Leitet CLI-Befehle an die entsprechenden `_cmd_*`-Methoden weiter.
- **Wichtig**: Sanitisiert Dateinamen, um ungültige Zeichen zu ersetzen (z.B. `/` -> `_`). Der interne `name`-Schlüssel in der JSON-Datei bleibt unverändert.

### `managers/target_manager.py`
- **Zweck**: Verwaltet alle Informationen über ein Ziel.
- **Kernlogik**: Die Methode `_parse_and_update_from_url` ist zentral. Sie nimmt eine URL entgegen und extrahiert automatisch `hostname`, `ip` (via DNS-Lookup), `port`, `protocol`, `domain` (via `tldextract`) etc.
- **Weitere Features**:
  - `gather`: Nutzt den `ReconService` aus `recon.py`, um weitere Informationen (DNS-Records, Whois, HTTP-Header) zu sammeln und dem Target hinzuzufügen.
  - `fork-domain`: Erstellt aus einem Subdomain-Target ein neues Target für die Hauptdomain.

### `managers/tool_manager.py`
- **Zweck**: Macht externe CLI-Tools innerhalb der Applikation konfigurierbar und nutzbar.
- **Struktur**: Ein "Tool" besteht aus einem Namen, einem Pfad und einer Liste von "Commands". Ein "Command" ist eine vordefinierte Befehlszeile für das Tool, bestehend aus mehreren "Params".
- **Kernlogik**: Die Methode `build_command` ist entscheidend. Sie:
  - Löst Platzhalter (`$target.ip`, `$profile.lhost`) auf.
  - Teilt Parameter mit Leerzeichen korrekt auf (via `shlex.split`).
  - Hängt temporäre `extra_params` an (für die `pwn ... -- <extras>`-Syntax).
  - Generiert bei `execute_per_param=True` separate Befehle für jeden Parameter.

### `job_manager.py`
- **Zweck**: Führt Befehle als asynchrone Hintergrundprozesse (Jobs) aus.
- **Funktionen**:
  - `start_job`: Startet einen Befehl in einem neuen Thread.
  - `kill_job`: Beendet einen laufenden Job.
  - `send_input`: Sendet Daten an den `stdin` eines laufenden Jobs.
  - `clear_finished_jobs`: Entfernt beendete Jobs aus der Liste.
- **Integration**: Protokolliert die Ergebnisse von beendeten Jobs im `LogbookManager` und `ReportManager`.

### `help_manager.py`
- **Zweck**: Stellt eine reichhaltige, kontextsensitive Hilfe bereit.
- **Funktionen**:
  - Nutzt `rich` für die Darstellung in Panels und Tabellen.
  - `show_subcommand_help` analysiert die `argparse`-Definitionen der Befehle, um automatisch Hilfe für Argumente, Optionen und Beispiele zu generieren.
  - Bietet auch manuell erstellte, detailliertere Hilfeseiten für Hauptbefehle (z.B. `help target`).

### `display_manager.py`
- **Zweck**: Kapselt die Logik für die formatierte Ausgabe von Daten.
- **Funktionen**:
  - `display_jobs_list`: Zeigt eine Tabelle aller Jobs.
  - `display_execution_summary`: Zeigt eine Zusammenfassung nach einer Befehlsausführung.
  - `do_overview`: Zeigt eine umfassende Übersicht der aktuellen Session.
  - Nutzt durchgehend `rich`-Komponenten (Panel, Table, Columns).

### `placeholders.py`
- **Zweck**: Löst dynamische Werte zur Laufzeit auf.
- **Syntax**: Platzhalter beginnen mit `$` (z.B. `$target.ip`, `$profile.lhost`, `$wordlist.path`).
- **Funktionsweise**: Manager können sich hier registrieren, um Platzhalter für ihre Entitäten bereitzustellen. Der `PlaceholderService` fragt die zuständigen Manager nach dem Wert.

### `cli_sessions.py`
- **Zweck**: Verwaltet den Zustand der Anwendung.
- **Inhalt**: Eine `CLISession` speichert, welche Entitäten (Target, Tool, Report, Wordlist) aktuell "geladen" sind.
- **Funktion**: Ermöglicht das Wechseln zwischen verschiedenen Arbeitskontexten (Sessions), ohne den Zustand zu verlieren.

## 4. Typische Arbeitsabläufe & Modifikationen

### Neuen Befehl hinzufügen (z.B. `target info <name>`)
1.  **Manager anpassen** (`target_manager.py`):
    - Eine neue Methode `_cmd_info(self, args, cli)` implementieren.
2.  **Parser anpassen** (`pwnity_cli.py`):
    - Im `target_parser` einen neuen Subparser für `info` hinzufügen.
    - Argumente definieren (z.B. `info_parser.add_argument("name", ...)`).
3.  **Hilfe anpassen** (`help_manager.py`):
    - Die automatisch generierte Hilfe sollte bereits funktionieren.
    - Für eine benutzerdefinierte Hilfeseite kann `show_help_target` erweitert werden.

### Neues Feld zu einer Entität hinzufügen (z.B. `os` zu Target)
1.  **Manager anpassen** (`target_manager.py`):
    - Keine direkten Änderungen nötig, da die Datenstrukturen flexibel sind.
2.  **Befehle anpassen**:
    - Der `update`-Befehl (`target update <name> os "Linux"`) funktioniert bereits durch die `JSONManager`-Basisklasse.
3.  **Anzeige anpassen** (`display_manager.py`):
    - Die `do_overview`-Methode oder andere `display_*`-Methoden anpassen, um das neue Feld anzuzeigen.
4.  **Platzhalter hinzufügen** (`placeholders.py`):
    - Den `TargetManager` so erweitern, dass er den Platzhalter `$target.os` auflösen kann.

### Neue Entität hinzufügen (z.B. "Vulnerability")
1.  **Neuen Manager erstellen** (`vulnerability_manager.py`):
    - Von `JSONManager` erben.
    - `_get_entity_type` implementieren.
    - Spezifische `_cmd_*`-Methoden hinzufügen.
2.  **In `pwnity_cli.py` integrieren**:
    - Den neuen Manager instanziieren.
    - Einen neuen Top-Level-Befehl (`vulnerability`) und dessen `argparse`-Parser erstellen.
    - Die `_dispatch_command`-Logik erweitern, um den neuen Befehl zu behandeln.
3.  **Session erweitern** (`cli_sessions.py`):
    - Ein Feld `self.vulnerability = None` zur `CLISession` hinzufügen, falls eine "geladen" werden kann.
4.  **Hilfe und Anzeige erweitern**:
    - Neue Methoden in `HelpManager` und `DisplayManager` hinzufügen.

## 5. WebUI (PRO Plugin) Integration

Die Anwendung kann im `--web-ui-mode` gestartet werden. In diesem Modus fungiert die CLI als Backend für eine separate Web-Oberfläche. Die Kommunikation zwischen Backend (CLI) und Frontend (WebUI) ist asynchron und dateibasiert.

### 5.1. Kommunikationsmodell

1.  **State-Serialisierung**: Das CLI-Backend schreibt bei jeder relevanten Zustandsänderung seinen kompletten aktuellen Zustand in eine zentrale JSON-Datei: `data/.session.json`.
2.  **Signalisierung**: Nachdem die JSON-Datei geschrieben wurde, sendet das Backend ein Signal an das Frontend, indem es ein spezielles, nicht druckbares Zeichen auf `stdout` ausgibt. Das WebUI-Wrapper-Skript fängt dieses Signal ab.
3.  **Datenabruf**: Nach Erhalt des Signals fordert das Frontend die aktualisierte `data/.session.json` per HTTP-Request vom Webserver an und rendert die Änderungen in der Oberfläche (oftmals mittels `htmx` oder ähnlichen Technologien).

### 5.2. Schlüsselkomponenten & Ablauf

Die gesamte Logik hierfür ist in `pwnity_cli.py` zentralisiert.

#### `_write_state_to_file()`
- **Zweck**: Sammelt alle für die UI relevanten Daten und schreibt sie atomar in `data/.session.json`.
- **Gesammelte Daten**:
  - Aktive Session-Details (`session_name`, `target`, `tool`, etc.).
  - Liste aller Sessions.
  - Liste aller laufenden und beendeten Jobs (`jobs_data`). **Wichtig**: Die Ausgabe (`output`) von Jobs wird hier auf die letzten 4KB gekürzt, um die Dateigröße gering zu halten.
  - Status von globalen Diensten wie Proxy und Heartbeat.
- **Ablauf**: Schreibt in eine `.tmp`-Datei und benennt sie dann atomar um, um Race Conditions zu vermeiden.

#### `_background_state_syncer()`
- **Zweck**: Ein Hintergrund-Thread, der nur im UI-Modus aktiv ist.
- **Funktion**: Überprüft in kurzen Intervallen (z.B. 0.5s), ob Jobs oder Heartbeats aktiv sind. Wenn ja, ruft er `_sync_session_state_for_ui()` auf, um Live-Updates (z.B. Job-Output) an die UI zu senden.

#### `_sync_session_state_for_ui(signal_command_completion=False)`
- **Zweck**: Die zentrale Methode, um die UI zu benachrichtigen.
- **Funktion**:
  1. Ruft `_write_state_to_file()` auf.
  2. Gibt ein Signal auf `stdout` aus:
     - `\x1f` (Unit Separator): Für stille Hintergrund-Updates (z.B. Job-Output).
     - `\x1e` (Record Separator): Für Updates, die einen vollen UI-Refresh auslösen sollen (z.B. nach Abschluss eines Befehls).

#### `postcmd()` Hook
- **Zweck**: Wird nach jedem Befehl ausgeführt.
- **Funktion im UI-Modus**: Ruft nach fast jedem Befehl `_sync_session_state_for_ui(signal_command_completion=True)` auf, um sicherzustellen, dass die UI den neuesten Zustand nach der Aktion des Benutzers widerspiegelt.

Dieses Dokument sollte eine solide Grundlage bieten, um sich im Code zurechtzufinden.

## 6. Testing-Strategie

Das Projekt verwendet `pytest` als Test-Framework. Die Tests sind eine entscheidende Ressource, um das exakte Verhalten der einzelnen Komponenten zu verstehen.

### 6.1. Grundprinzipien

- **Struktur**: Jeder Manager oder jedes wichtige Modul hat eine eigene Testdatei im `tests/`-Verzeichnis (z.B. `test_job_manager.py` für `job_manager.py`).
- **Isolation**: Tests werden durch den massiven Einsatz von Fixtures und Mocks voneinander isoliert.
- **Fixtures (`@pytest.fixture`)**: Werden verwendet, um saubere Instanzen von Managern oder gemockten Objekten für jeden Testfall bereitzustellen. Eine typische Fixture (`target_manager`) erstellt ein temporäres Verzeichnis und konfiguriert den Manager so, dass er nur in diesem Verzeichnis arbeitet.
- **Mocking (`mocker`, `monkeypatch`)**:
  - `mocker` (von `pytest-mock`) wird verwendet, um Abhängigkeiten (z.B. andere Manager, die `log`-Instanz) durch `MagicMock`-Objekte zu ersetzen. Dies ermöglicht die Überprüfung von Methodenaufrufen (`.assert_called_once()`).
  - `monkeypatch` wird verwendet, um globale Funktionen oder Klassenattribute zur Laufzeit zu ersetzen, insbesondere um Netzwerkaufrufe (`socket.gethostbyname`, `http.client.HTTPConnection`) und Dateisystem-Interaktionen zu verhindern.

### 6.2. Typischer Testaufbau (`test_target_manager.py`)

1.  **Fixture `target_manager`**:
    - Erstellt ein temporäres Verzeichnis (`tmp_path`).
    - `monkeypatch`t die `config.get_parameter`-Funktion, sodass der `TargetManager` sein Arbeitsverzeichnis in `tmp_path` hat.
    - Schaltet den Logger stumm.
    - Gibt eine saubere `TargetManager`-Instanz zurück.
2.  **Testfall `test_update_from_url_parsing`**:
    - Nutzt die `target_manager`-Fixture.
    - `monkeypatch`t `socket.gethostbyname` und `tldextract.extract`, um vorhersagbare Ergebnisse ohne echte Netzwerk- oder CPU-intensive Operationen zu erhalten.
    - Ruft die zu testende Methode auf (`_parse_and_update_from_url`).
    - Lädt die resultierende JSON-Datei und `assert`et, dass alle Felder korrekt gesetzt wurden.

## 7. Frontend (JavaScript) & Workflow-Editor

Das Frontend ist eine separate Webanwendung (siehe `README.md`), die mit dem Python-Backend über das in Abschnitt 5 beschriebene Kommunikationsmodell (`data/.session.json` und Signale) interagiert.

### 7.1. JavaScript-Module (Konzept)

Obwohl der Code nicht direkt vorliegt, lässt sich die Struktur aus den Backend-Komponenten ableiten:
- **UI-Komponenten**: Es gibt wahrscheinlich JS-Komponenten, die für die Darstellung der verschiedenen Entitäten (Targets, Tools, Jobs, etc.) zuständig sind.
- **State-Management**: Ein zentrales JS-Modul ist dafür verantwortlich, die `data/.session.json` vom Server abzurufen und den lokalen Zustand der Anwendung zu aktualisieren.
- **Interaktivität**: Technologien wie `htmx` (oder ein ähnliches Konzept) werden wahrscheinlich verwendet, um auf die Signale des Backends zu reagieren und nur die Teile der UI neu zu rendern, die sich geändert haben. Dies sorgt für die "Real-time Updates".
- **Terminal-Integration**: Das `xterm.js`-Modul wird eingebettet, um ein voll funktionsfähiges Terminal im Browser bereitzustellen, das über einen WebSocket (oder eine ähnliche Technologie wie `ptyprocess` im Backend) mit der `pwnity_cli.py`-Instanz verbunden ist.

### 7.2. Workflow-Editor & `WorkflowManager`

- **Zweck**: Workflows dienen dazu, eine Abfolge von `pwnity`-Befehlen zu automatisieren. Dies ist nützlich für wiederkehrende Aufgaben wie Reconnaissance-Scans.
- **Backend (`WorkflowManager`)**:
  - Verwaltet JSON-Dateien, die Workflows definieren.
  - Ein Workflow ist im Wesentlichen eine Liste von Befehls-Strings.
  - Der Manager ist dafür zuständig, diese Befehle nacheinander auszuführen, ähnlich wie ein Benutzer sie in die CLI eingeben würde.
- **Frontend (Workflow-Editor)**:
  - Ist eine grafische Oberfläche innerhalb der WebUI.
  - Ermöglicht es dem Benutzer, Workflows per Drag-and-Drop oder über Formulare zu erstellen und zu bearbeiten.
  - Anstatt `workflow update my-scan add "target load server-1"` manuell einzugeben, kann der Benutzer Aktionen aus einer Liste auswählen und anordnen.
  - Der erstellte Workflow wird dann als JSON-Objekt an das Backend gesendet und vom `WorkflowManager` gespeichert.

## 8. Frontend-Architektur (WebUI)

Das Frontend ist eine moderne Single-Page-Application (SPA), die mit `Vite` als Build-Tool entwickelt wird. Die Kommunikation mit dem Python-Backend erfolgt asynchron (siehe Abschnitt 5). Die `README.md` und `vite.config.js` geben Aufschluss über die Struktur.

### 8.1. HTML (`plugins/web_ui/templates/index.html`)

- **Zweck**: Dies ist die einzige HTML-Datei und dient als Einstiegspunkt für die gesamte Webanwendung.
- **Struktur**:
  - Definiert die grundlegende Seitenstruktur (Layout-Container für Header, Sidebar, Hauptinhalt, Terminal).
  - Enthält Platzhalter für die dynamische Darstellung von Inhalten (z.B. `<div id="job-list"></div>`).
  - Lädt die primären CSS- und JavaScript-Bundles, die von Vite erstellt werden.
  - Lädt möglicherweise eine separate Lade-Animation (`_loader.css`), die sofort angezeigt wird, während die Hauptanwendung im Hintergrund lädt.
- **Integration**: Wird vom Flask-Webserver (`web_ui/app.py`) ausgeliefert. Es ist wahrscheinlich eine Jinja2-Vorlage, auch wenn sie nur minimale serverseitige Logik enthält.

### 8.2. CSS (`plugins/web_ui/static/css/`)

- **Zweck**: Styling der gesamten Web-Oberfläche.
- **Struktur (vermutet)**:
  - `main.css` / `style.css`: Globale Stile, CSS-Variablen (für Farben, Schriftgrößen), Layout-Definitionen und Stile für die Haupt-UI-Elemente.
  - `_loader.css`: Ein kleines, separates Stylesheet für die initiale Ladeanimation. Es wird aus dem Haupt-Bundle ausgeschlossen (`vite.config.js`), um sofortiges Rendering zu gewährleisten.
  - `components/*.css`: Modulare Stylesheets, die jeweils nur für eine bestimmte UI-Komponente zuständig sind (z.B. `job-card.css`, `modal.css`).

### 8.3. JavaScript (`plugins/web_ui/static/js/` - gebündelt nach `dist/`)

- **Zweck**: Die gesamte Anwendungslogik und Interaktivität des Frontends.
- **Struktur (vermutet)**:
  - **`main.js`**: Der Haupteinstiegspunkt. Initialisiert die App, richtet globale Event-Listener ein und startet die Verbindung zum Backend (wahrscheinlich via Socket.IO, wie in `vite.config.js` konfiguriert).
  - **`state.js` / `store.js`**: Das "Gehirn" des Frontends.
    - Holt die `data/.session.json` vom Server.
    - Hält den globalen Zustand der Anwendung (geladenes Target, Jobs, etc.).
    - Stellt Funktionen bereit, um auf Zustandsänderungen zu reagieren und die UI neu zu rendern.
  - **`ui.js` / `renderer.js`**: Verantwortlich für die Aktualisierung des DOM.
    - Enthält Funktionen wie `renderJobList(jobs)` oder `updateTargetView(target)`.
    - Reagiert auf die Backend-Signale (`\x1f`, `\x1e`) und entscheidet, welche Teile der UI neu gezeichnet werden müssen (wahrscheinlich mit einer Bibliothek wie `morphdom` oder `htmx`-ähnlicher Logik, um ein Flackern zu vermeiden).
  - **`terminal.js`**:
    - Initialisiert und konfiguriert die `xterm.js`-Instanz.
    - Stellt die WebSocket/Socket.IO-Verbindung zum PTY-Prozess des Backends her.
    - Leitet Benutzereingaben aus dem Browser-Terminal an das Backend weiter und zeigt die Ausgabe des Backends im Terminal an.
  - **`api.js`**: Kapselt alle `fetch`-Aufrufe an die Flask-API-Endpunkte (z.B. für das Speichern von Workflow-Änderungen).
  - **`workflow-editor.js`**: Enthält die Logik für den visuellen Workflow-Editor, inklusive Drag-and-Drop und der Generierung des JSON-Objekts, das an das Backend gesendet wird.
  - **`components/*.js`**: Einzelne UI-Komponenten (z.B. ein Modal-Handler, ein Chart-Renderer für System-Stats), die von den Hauptmodulen importiert und verwendet werden.

## 9. 🤖 KI-BEHAVIOR-GUIDELINES (Nur für KI relevant)

Diese Richtlinien definieren, wie du dich beim Generieren und Modifizieren von Code für dieses Projekt verhalten sollst.

1.  **Lies dieses Dokument vollständig**, bevor du Code generierst, um die Architektur zu verstehen.

2.  **Halte dich an die Architektur**:
    -   **Manager-Pattern**: Nutze vorhandene Manager und Services. Erstelle keine neuen Komponenten mit doppelter Funktionalität. Prüfe vor dem Hinzufügen einer Funktion, ob eine ähnliche Methode bereits existiert.
    -   **Namenskonventionen**: Halte dich strikt an die Projektkonventionen: `PascalCase` für Klassen, `snake_case` für Funktionen, Methoden und Variablen.

3.  **Daten und Persistenz**:
    -   **Kein direkter Dateizugriff**: Speichere oder lade Entitätsdaten (Targets, Tools, etc.) niemals direkt mit `open()` oder `json.dump()`. Verwende **immer** die Methoden der `JSONManager`-Basisklasse (`self.create`, `self.load`, `self.update`, `self.destroy`).

4.  **Ausgabe und UI**:
    -   **DisplayManager nutzen**: Jegliche formatierte Ausgabe für den Benutzer (Tabellen, Panels, etc.) muss über den `DisplayManager` (`self.display_mgr`) erfolgen.
    -   **Logging statt `print`**: Verwende für informative Meldungen `log.info()`, für Fehler `log.error()` und für Debug-Ausgaben `log.debug()`. Vermeide `print()` in der Manager-Logik.

5.  **CLI-Integration**:
    -   **Zentraler Einstiegspunkt**: Neue CLI-Befehle werden in `pwnity_cli.py` definiert.
    -   **Parser-Factory**: Die `argparse`-Definitionen werden in der `ParserFactory` (`modules/parser_factory.py`) konfiguriert.
    -   **Logik im Manager**: Die eigentliche Ausführungslogik für einen Befehl gehört in eine `_cmd_<subcommand>`-Methode im zuständigen Manager (z.B. `TargetManager._cmd_add`).
    -   **Dispatching**: Der Aufruf vom CLI-Befehl zum Manager erfolgt über die `_dispatch_command`-Methode in `pwnity_cli.py`.

6.  **Web-UI-Synchronisation**:
    -   Wenn eine Aktion den Zustand der Anwendung ändert (z.B. ein Job wird gestartet, ein Target wird geladen), stelle sicher, dass die `postcmd`-Methode in `pwnity_cli.py` am Ende `_sync_session_state_for_ui()` aufruft, damit die Web-Oberfläche die Änderungen erhält.

7.  **Testing**:
    -   **Tests sind Pflicht**: Für neue Funktionen oder Bugfixes müssen entsprechende Tests im `tests/`-Verzeichnis hinzugefügt oder angepasst werden.
    -   **Isolation durch Mocks**: Verwende `pytest`-Fixtures für das Setup und `mocker`/`monkeypatch`, um externe Abhängigkeiten (Netzwerk, Dateisystem, andere Manager) konsequent zu isolieren.

8.  **Dokumentation**:
    -   **Docstrings**: Füge allen neuen öffentlichen Methoden und Klassen aussagekräftige Python-Docstrings hinzu. Erkläre den Zweck, die Parameter (`Args:`) und die Rückgabewerte (`Returns:`).
    -   **Hilfetexte**: Aktualisiere die Hilfetexte im `HelpManager` und die `argparse`-Beschreibungen, wenn sich die Funktionalität eines Befehls ändert.

9.  **Im Zweifel...**:
    -   ... schau dir einen existierenden Manager an (z.B. `LibraryManager` oder `ToolManager`) und orientiere dich an dessen Struktur und Integration in `pwnity_cli.py`.