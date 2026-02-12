# pwnity Reporting - Lastenheft (Entwurf v2)

## 1. Vision
Ein integrierter Report-Editor innerhalb der PWNity Web UI, der es ermöglicht, aus gesammelten Daten (Findings, Loot, Notizen, Job-Outputs) per Drag & Drop professionelle Pentest-Reports zu erstellen.

## 2. Aktueller Status (Ist-Zustand)
- **Report Entity**: Existiert im Backend (`ReportManager`). Sammelt Findings, Loot, History und Notes.
- **Aktuelle Ansicht**: `ReportView` und `ReportDetails` zeigen diese Daten als Listen/Tabellen an.
- **Export**: Generiert Markdown per CLI (`report render`) oder Replay-Skripte (`report export`).

## 3. Soll-Zustand (Geplante Features)

### 3.1. Der Editor (Composition Interface)
- **Layout**: Split-View
    - **Links (Quelle)**: "Asset Library" - Alle Findings, Loot-Einträge, Notizen und **Job-Outputs** aus dem aktuellen Report-Objekt.
    - **Rechts (Ziel)**: "Document Canvas" - Der eigentliche Report.
- **Funktionen**:
    - **Drag & Drop**: Ziehen von Elementen aus der linken Leiste in das Dokument.
    - **Automatisches Rendering**: Ein Element wird beim Droppen automatisch in einen definierten Block umgewandelt (z.B. Finding -> formatierte Box).
    - **WYSIWYG / Markdown Hybrid**: Bearbeitung von Texten direkt im Dokument.

### 3.2. Templating & Branding (Corporate Identity)
- **PDF-Import**: Import von PDFs als Hintergründe ("Briefpapier") für Deckblätter oder Seitenränder.
- **Logo-Upload**: Einfaches Hochladen von Firmenlogos für Header/Deckblatt.
- **Header/Footer**: Editor für Kopf- und Fußzeilen (Text, Seitenzahlen, Logos).
- **Vorlagen-Verwaltung**: Speichern von Layout-Einstellungen (Farben, Logos, PDF-Hintergrund) als wiederverwendbare Templates.
- **Wegfall**: Kein Import von .docx-Layouts notwendig.

### 3.3. Inhaltliche Elemente & Styling
- **Finding-Blöcke**: Findings werden als geschlossene "Items" behandelt, die visuell ansprechend gestaltet sind ("Cooles Styling").
- **Job-Referenzen**: Drag & Drop von Job-IDs aus dem Logbook. Dies rendert den Konsolen-Output (ganz oder teilweise) direkt in den Report (Code-Block Style).
    - *Vorteil*: Spart Screenshots von Text-Ausgaben.
    - *Hinweis*: Screenshots (Bilder) bleiben als separates Feature erhalten.
- **Style-Editor**: Das Aussehen der Blöcke (z.B. wie eine "Critical"-Box aussieht) soll editierbar und in Vorlagen speicherbar sein.

### 3.4. Export Formate
- **PDF**: Hochwertiger PDF-Export (unter Berücksichtigung des PDF-Hintergrunds).
- **HTML**: Interaktiver Report (Self-contained).

## 4. Technische Umsetzungsideen
- **Frontend Editor**: Nutzung eines Block-basierten Editors (z.B. TipTap mit Custom Nodes für Findings/Jobs).
- **Datenstruktur**: Der Report im Editor ist eine Liste von Blöcken (Text, Finding-Block, Job-Output-Block, Image-Block).
- **Backend**: Speicherung der Template-Konfigurationen (CSS-Variablen, Base64-Assets).

## 5. Nächste Schritte
1. **Prototyping**: Bauen der Split-View (`ReportEditor.vue`) und erste Drag & Drop Versuche.
2. **Template-Engine**: Implementierung des PDF-Hintergrund-Renderings.

---
*Status: Entwurf v2 - 12.02.2026*
