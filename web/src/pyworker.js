// Runs core/pipeline.py in the browser with Pyodide, so uploads use the same maths as `python -m core.run`.
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/";
const sources = import.meta.glob("../../core/*.py", { query: "?raw", import: "default", eager: true });
let ready;

async function boot() {
  postMessage({ status: "Loading Python in your browser (first time only, a few seconds)…" });
  const { loadPyodide } = await import(/* @vite-ignore */ `${PYODIDE}pyodide.mjs`);
  const py = await loadPyodide({ indexURL: PYODIDE });
  await py.loadPackage(["numpy", "scipy"]);
  py.FS.mkdirTree("/home/pyodide/core");
  for (const [path, src] of Object.entries(sources)) {
    py.FS.writeFile(`/home/pyodide/core/${path.split("/").pop()}`, src);
  }
  py.runPython("import sys; sys.path.insert(0, '/home/pyodide')");
  return py;
}

onmessage = async ({ data }) => {
  try {
    ready ??= boot();
    const py = await ready;
    postMessage({ status: "Fitting your warm-up and tuning on 600 strategies simulated from it…" });
    py.globals.set("csv_text", data.text);
    py.globals.set("csv_name", data.name);
    const out = py.runPython(
      "import json\nfrom core.pipeline import analyse_csv\njson.dumps(analyse_csv(csv_text, csv_name), allow_nan=False)",
    );
    postMessage({ result: JSON.parse(out) });
  } catch (e) {
    ready = e?.name === "PythonError" ? ready : undefined; // retry boot next time if loading failed
    postMessage({ error: String(e?.message ?? e).split("\n").slice(-2).join(" ") });
  }
};
