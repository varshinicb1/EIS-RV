from __future__ import annotations

import json
import uuid
from pathlib import Path

from flask import Flask, abort, redirect, render_template_string, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from electrochem_suite import FORMULA_ROWS as GENERIC_FORMULAS, STYLE_PRESETS
from make_plots_workbook import FORMULAS
from rvce_pipeline import APP_OUTPUT, run_job


BASE_DIR = Path(__file__).resolve().parent
APP_OUTPUT_ABS = (BASE_DIR / APP_OUTPUT).resolve()
UPLOAD_ROOT = APP_OUTPUT_ABS / "uploads"


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024


CSS = """
:root {
  color-scheme: light;
  --ink: #111827;
  --muted: #5f6673;
  --line: #dfe4ec;
  --soft: #f7f9fc;
  --accent: #1d4ed8;
  --accent-soft: #e8f0ff;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Arial, Helvetica, sans-serif;
  color: var(--ink);
  background: #ffffff;
  line-height: 1.45;
}
.shell { max-width: 1180px; margin: 0 auto; padding: 28px 24px 56px; }
header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--line);
}
h1 { margin: 0; font-size: 28px; letter-spacing: 0; font-weight: 700; }
.subtitle { margin: 6px 0 0; color: var(--muted); max-width: 760px; }
.badge {
  border: 1px solid var(--line);
  background: var(--soft);
  padding: 8px 10px;
  border-radius: 6px;
  color: #273142;
  white-space: nowrap;
  font-size: 13px;
}
.panel {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  margin-top: 22px;
  background: #ffffff;
}
.panel h2 { margin: 0 0 14px; font-size: 18px; }
.upload-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
}
input[type=file] {
  width: 100%;
  padding: 18px;
  border: 1px dashed #aeb8c8;
  border-radius: 8px;
  background: var(--soft);
}
select, input[type=number], input[type=text], input[type=password] {
  width: 100%;
  margin-top: 6px;
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: white;
  color: var(--ink);
}
label { color: #273142; font-size: 13px; font-weight: 700; }
.control-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}
.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 64px;
}
.check-row input { width: auto; margin: 0; }
button, .button {
  border: 1px solid var(--accent);
  background: var(--accent);
  color: white;
  border-radius: 6px;
  padding: 11px 15px;
  min-height: 42px;
  text-decoration: none;
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.button.secondary {
  color: var(--accent);
  background: white;
  border-color: #b7c8ef;
}
.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.sample-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.sample h3 { margin: 0 0 8px; font-size: 16px; }
.metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin: 12px 0;
}
.metric { background: var(--soft); border: 1px solid var(--line); border-radius: 6px; padding: 10px; }
.metric span { display: block; color: var(--muted); font-size: 12px; }
.metric strong { display: block; margin-top: 3px; font-size: 15px; }
.plot-pair { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
figure { margin: 0; border: 1px solid var(--line); border-radius: 8px; padding: 8px; background: #ffffff; }
figure img { display: block; width: 100%; height: auto; }
figcaption { color: var(--muted); font-size: 12px; margin-top: 6px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { border-bottom: 1px solid var(--line); text-align: left; padding: 8px 7px; vertical-align: top; }
th { background: var(--soft); font-weight: 700; }
code { font-family: Consolas, Monaco, monospace; font-size: 12px; }
.downloads { columns: 2; column-gap: 28px; }
.downloads a {
  display: block;
  break-inside: avoid;
  color: var(--accent);
  text-decoration: none;
  padding: 5px 0;
}
.error {
  border: 1px solid #f0b7b7;
  background: #fff7f7;
  color: #7f1d1d;
  border-radius: 6px;
  padding: 10px 12px;
  margin-top: 18px;
}
.actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
.small { color: var(--muted); font-size: 13px; }
@media (max-width: 850px) {
  header, .upload-grid { display: block; }
  .badge { display: inline-block; margin-top: 14px; }
  button { margin-top: 12px; width: 100%; }
  .grid, .sample-grid, .plot-pair, .metrics, .control-grid { grid-template-columns: 1fr; }
  .downloads { columns: 1; }
}
"""


INDEX_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RVCE CND Lab CV Analysis</title>
  <style>{{ css }}</style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <h1>RVCE CND Lab Electrochemistry Analysis</h1>
        <p class="subtitle">Research-grade CV, EIS, GCD, DPV, and Raman analysis with branch-safe CV parsing, automated technique detection, formula audit, workbook export, and publishable figures.</p>
      </div>
      <div class="badge">Local Python app</div>
    </header>

    {% if error %}<div class="error">{{ error }}</div>{% endif %}

    <section class="panel">
      <h2>Upload Data Files</h2>
      <form method="post" action="{{ url_for('analyze') }}" enctype="multipart/form-data">
        <div class="upload-grid">
          <input type="file" name="files" accept=".csv,.xlsx,.xls,.txt,text/csv" multiple required>
          <button type="submit">Run analysis</button>
        </div>
        <div class="control-grid">
          <label>Technique
            <select name="technique">
              <option value="auto" selected>Auto detect</option>
              <option value="cv">CV</option>
              <option value="eis">EIS</option>
              <option value="gcd">GCD</option>
              <option value="dpv">DPV</option>
              <option value="raman">Raman</option>
            </select>
          </label>
          <label>DPI
            <input type="number" name="dpi" min="150" max="1200" step="50" value="900">
          </label>
          <label>Style
            <select name="style">
              {% for name in styles %}
              <option value="{{ name }}" {% if name == "reference" %}selected{% endif %}>{{ name }}</option>
              {% endfor %}
            </select>
          </label>
          <label>Material query
            <input type="text" name="material_query" placeholder="Fe2O3, CoCr2O4, rGO">
          </label>
        </div>
        <div class="control-grid">
          <label>Materials Project API key
            <input type="password" name="mp_api_key" autocomplete="off">
          </label>
          <label>NVIDIA NIM API key
            <input type="password" name="nvidia_api_key" autocomplete="off">
          </label>
          <label class="check-row">
            <input type="checkbox" name="enable_ai" value="1"> Generate AI comments
          </label>
        </div>
      </form>
      <p class="small">CV remains the default high-detail workflow. Upload two or more CV files for ML diagnostics, and three or more distinct CV files for composition-style comparison layouts.</p>
    </section>

    <section class="panel">
      <h2>Formulas Shown In Output</h2>
      <table>
        <thead><tr><th>Analysis</th><th>Formula</th></tr></thead>
        <tbody>
        {% for row in formulas[1:] %}
          <tr><td>{{ row[0] }}</td><td><code>{{ row[1] }}</code></td></tr>
        {% endfor %}
        {% for row in generic_formulas[1:] %}
          <tr><td>{{ row[0] }}: {{ row[1] }}</td><td><code>{{ row[2] }}</code></td></tr>
        {% endfor %}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


JOB_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RVCE CND Lab CV Analysis Results</title>
  <style>{{ css }}</style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <h1>Analysis Results</h1>
        <p class="subtitle">Job <code>{{ summary.job_id }}</code>. All files below are generated from the uploaded CSV data in this run.</p>
      </div>
      <div class="actions">
        <a class="button secondary" href="{{ url_for('index') }}">New analysis</a>
        {% if zip_path %}<a class="button" href="{{ url_for('download', job_id=summary.job_id, filename=zip_path) }}">Download complete ZIP</a>{% endif %}
      </div>
    </header>

    <section class="panel">
      <h2>Samples</h2>
      <div class="sample-grid">
      {% for sample in summary.samples %}
        <article class="panel sample">
          <h3>{{ sample.sample_id }}</h3>
          <div class="small">{{ sample.source_name }}</div>
          <div class="metrics">
            <div class="metric"><span>Technique</span><strong>{{ sample.technique }}</strong></div>
            {% if sample.mean_b is not none %}
            <div class="metric"><span>Mean b</span><strong>{{ "%.6f"|format(sample.mean_b) }}</strong></div>
            <div class="metric"><span>Mean capacitive fraction</span><strong>{{ "%.6f"|format(sample.mean_cap_fraction) }}</strong></div>
            {% else %}
            <div class="metric"><span>Points or series</span><strong>{{ sample.metrics.points or sample.metrics.series_count or "n/a" }}</strong></div>
            <div class="metric"><span>DPI</span><strong>{{ sample.metrics.dpi }}</strong></div>
            {% endif %}
          </div>
          <div class="actions">
            <a class="button secondary" href="{{ url_for('download', job_id=summary.job_id, filename=sample.output_dir ~ '/' ~ sample.workbook) }}">Excel workbook</a>
            {% if sample.technique == "CV" %}
              <a class="button secondary" href="{{ url_for('download', job_id=summary.job_id, filename=sample.output_dir ~ '/CV_Analysis_Formulas_and_References.pdf') }}">Formulas PDF</a>
            {% endif %}
            <a class="button secondary" href="{{ url_for('download', job_id=summary.job_id, filename=sample.output_dir ~ '/' ~ sample.download_zip) }}">Sample ZIP</a>
          </div>
          {% if sample.metrics.materials_project %}
            <p class="small">{{ sample.metrics.materials_project.message }}</p>
          {% endif %}
          {% if sample.metrics.ai_commentary and sample.metrics.ai_commentary.ok %}
            <div class="actions"><a class="button secondary" href="{{ url_for('download', job_id=summary.job_id, filename=sample.output_dir ~ '/ai_commentary.md') }}">AI commentary</a></div>
          {% endif %}
          <div class="plot-pair">
            {% if sample.technique == "CV" %}
            <figure>
              <img src="{{ url_for('download', job_id=summary.job_id, filename=sample.output_dir ~ '/fig4_style_cv_suite.png') }}" alt="Fig4 style CV suite">
              <figcaption>Fig. 4 style CV suite</figcaption>
            </figure>
            <figure>
              <img src="{{ url_for('download', job_id=summary.job_id, filename=sample.output_dir ~ '/fig5_style_kinetic_suite.png') }}" alt="Fig5 style kinetic suite">
              <figcaption>Fig. 5 style kinetic suite</figcaption>
            </figure>
            {% else %}
              {% for plot in sample.plots[:4] %}
              <figure>
                <img src="{{ url_for('download', job_id=summary.job_id, filename=sample.output_dir ~ '/' ~ plot) }}" alt="{{ plot }}">
                <figcaption>{{ plot }}</figcaption>
              </figure>
              {% endfor %}
            {% endif %}
          </div>
        </article>
      {% endfor %}
      </div>
    </section>

    {% if summary.comparison %}
    <section class="panel">
      <h2>Multi-file Outputs</h2>
      <div class="actions">
        {% if summary.comparison.ml_summary %}
          <a class="button secondary" href="{{ url_for('download', job_id=summary.job_id, filename='ml/ml_model_assignments.csv') }}">ML assignments CSV</a>
          <a class="button secondary" href="{{ url_for('download', job_id=summary.job_id, filename='ml/ml_embedding.png') }}">ML embedding PNG</a>
          <a class="button secondary" href="{{ url_for('download', job_id=summary.job_id, filename='ml/ml_model_summary.json') }}">ML summary JSON</a>
        {% endif %}
        {% if summary.comparison.fig4_comparison %}
          <a class="button secondary" href="{{ url_for('download', job_id=summary.job_id, filename=summary.comparison.fig4_comparison) }}">Comparison Fig. 4 PNG</a>
          <a class="button secondary" href="{{ url_for('download', job_id=summary.job_id, filename=summary.comparison.fig5_comparison) }}">Comparison Fig. 5 PNG</a>
        {% endif %}
      </div>
    </section>
    {% endif %}

    <section class="panel">
      <h2>All Downloads</h2>
      <div class="downloads">
      {% for item in manifest %}
        <a href="{{ url_for('download', job_id=summary.job_id, filename=item.relative_path) }}">{{ item.relative_path }}</a>
      {% endfor %}
      </div>
    </section>
  </main>
</body>
</html>
"""


def _job_dir(job_id: str) -> Path:
    if not job_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in job_id):
        abort(404)
    path = (APP_OUTPUT_ABS / job_id).resolve()
    if not str(path).startswith(str(APP_OUTPUT_ABS)):
        abort(404)
    return path


def _load_json(path: Path) -> dict | list:
    if not path.exists():
        abort(404)
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/")
def index():
    return render_template_string(
        INDEX_TEMPLATE,
        css=CSS,
        formulas=FORMULAS,
        generic_formulas=GENERIC_FORMULAS,
        styles=STYLE_PRESETS.keys(),
        error=request.args.get("error"),
    )


@app.post("/analyze")
def analyze():
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return redirect(url_for("index", error="Select at least one CSV file."))

    job_id = uuid.uuid4().hex[:12]
    upload_dir = UPLOAD_ROOT / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    allowed = {".csv", ".xlsx", ".xls", ".txt", ".dat"}
    for index, file_storage in enumerate(files, start=1):
        filename = secure_filename(file_storage.filename or f"sample_{index}.csv")
        if Path(filename).suffix.lower() not in allowed:
            return redirect(url_for("index", error="Only CSV, Excel, TXT, and DAT files are accepted."))
        path = upload_dir / filename
        if path.exists():
            path = upload_dir / f"{index:02d}_{filename}"
        file_storage.save(path)
        paths.append(path)

    try:
        try:
            dpi = int(request.form.get("dpi", "900"))
        except ValueError:
            dpi = 900
        dpi = max(150, min(1200, dpi))
        style = request.form.get("style", "reference")
        if style not in STYLE_PRESETS:
            style = "reference"
        run_job(
            paths,
            job_id=job_id,
            dpi=dpi,
            style=style,
            technique=request.form.get("technique", "auto"),
            material_query=request.form.get("material_query") or None,
            mp_api_key=request.form.get("mp_api_key") or None,
            nvidia_api_key=request.form.get("nvidia_api_key") or None,
            enable_ai=request.form.get("enable_ai") == "1",
        )
    except Exception as exc:
        return redirect(url_for("index", error=f"Analysis failed: {exc}"))
    return redirect(url_for("job", job_id=job_id))


@app.get("/job/<job_id>")
def job(job_id: str):
    job_dir = _job_dir(job_id)
    summary = _load_json(job_dir / "job_summary.json")
    manifest = _load_json(job_dir / "artifact_manifest.json")
    zip_name = f"rvce_cnd_lab_cv_analysis_{job_id}.zip"
    zip_path = zip_name if (job_dir / zip_name).exists() else None
    return render_template_string(
        JOB_TEMPLATE,
        css=CSS,
        summary=summary,
        manifest=manifest,
        zip_path=zip_path,
    )


@app.get("/download/<job_id>/<path:filename>")
def download(job_id: str, filename: str):
    job_dir = _job_dir(job_id)
    target = (job_dir / filename).resolve()
    if not str(target).startswith(str(job_dir.resolve())) or not target.is_file():
        abort(404)
    return send_from_directory(job_dir, filename, as_attachment=False)


@app.get("/health")
def health():
    return {"status": "ok", "app": "RVCE CND Lab Electrochemistry Analysis"}


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
