"""Minimal local GUI for parallel Bev Novus parameter experiments."""

from __future__ import annotations

import json
import threading
import time
import tkinter as tk
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from broad_sweep import latin_hypercube
from adaptive_config import build_next_config
from experiments import run_condition, run_particle_condition
from gui_config import delete_preset, list_presets, load_preset, save_preset
from gpu_sweep import run_gpu_particle_campaign, screen_and_replay
from morrow import reproduction_preflight


def numbers(text: str, cast=float) -> list:
    values = [cast(part.strip()) for part in text.split(",") if part.strip()]
    if not values:
        raise ValueError("Enter at least one value.")
    return values


def run_one(job: dict):
    engine = job.pop("engine", "field")
    return (run_particle_condition if engine == "particle" else run_condition)(**job)


class ExperimentApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Bev Novus experiment runner")
        self.geometry("1180x760")
        self.results: list[dict] = []
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.total_jobs = 0
        self.completed_jobs = 0
        self.gpu_report: dict | None = None
        self.particle_gpu_report: dict | None = None
        self.gpu_screen_total = 0
        self.fields: dict[str, tk.StringVar] = {}
        self.engine = tk.StringVar(value="Field")
        self.help_text = tk.StringVar(value="Select or hover over a control to see what it changes.")
        self.live_previews = tk.BooleanVar(value=False)
        self.live_warning = tk.StringVar(value="Live previews off - lowest overhead mode.")
        self.live_cards: dict[str, dict] = {}
        self.live_images: dict[str, tk.PhotoImage] = {}
        self.run_rows: dict[str, str] = {}
        self.row_paths: dict[str, str] = {}
        self.visual_filter: set[str] | None = None
        self.visual_scale = 2
        self.adaptive_configs: list[dict] | None = None
        self.adaptive_campaign_active = False
        self.adaptive_generation = 0
        self.adaptive_generation_total = 0
        self.adaptive_config_count = 24
        self.adaptive_elite_count = 6
        self.adaptive_source_path: Path | None = None
        self.run_started_at = 0.0
        self.eta_text = tk.StringVar(value="ETA: -")
        self.preset_name = tk.StringVar()
        self.preset_choice = tk.StringVar()
        self.report_choice = tk.StringVar()
        self.report_paths: dict[str, Path] = {}
        self.summary_vars: dict[str, tk.StringVar] = {}
        self.sort_column = "run"
        self.sort_reverse = False
        self.detail_text = tk.StringVar(value="Select a run to inspect its metrics and saved frame.")
        self._build()
        self._load_initial_adaptive()

    def _help(self, widget: tk.Widget, text: str) -> None:
        widget.bind("<Enter>", lambda _event: self.help_text.set(text))
        widget.bind("<FocusIn>", lambda _event: self.help_text.set(text))

    def _config_snapshot(self) -> dict:
        return {
            "schema": "bev-novus-gui-config-v1",
            "fields": {name: variable.get() for name, variable in self.fields.items()},
            "engine": self.engine.get(),
            "controls": {"reproduce": self.reproduce.get(), "mutate": self.mutate.get(),
                          "recycle": self.recycle.get(), "spatial": self.spatial.get()},
            "live_previews": self.live_previews.get(),
        }

    def _apply_config(self, config: dict) -> None:
        for name, value in config.get("fields", {}).items():
            if name in self.fields:
                self.fields[name].set(str(value))
        if config.get("engine") in ("Field", "Particle hybrid"):
            self.engine.set(config["engine"])
        controls = config.get("controls", {})
        for name, variable in (("reproduce", self.reproduce), ("mutate", self.mutate),
                               ("recycle", self.recycle), ("spatial", self.spatial)):
            if name in controls:
                variable.set(bool(controls[name]))
        self.live_previews.set(bool(config.get("live_previews", False)))
        self._toggle_live_previews()

    def _refresh_presets(self) -> None:
        self.preset_box.configure(values=list_presets())

    def _refresh_reports(self) -> None:
        results_dir = Path(__file__).with_name("Results")
        paths = sorted(results_dir.glob("*.json")) + sorted((results_dir / "adaptive-campaign").glob("*.json"))
        self.report_paths = {}
        labels = []
        for path in paths:
            label = str(path.relative_to(results_dir))
            self.report_paths[label] = path
            labels.append(label)
        self.report_box.configure(values=labels)
        if self.report_choice.get() not in self.report_paths:
            preferred = next((name for name in ("gui-particle-gpu-latest.json", "gui-gpu-latest.json") if name in self.report_paths), "")
            self.report_choice.set(preferred or (labels[0] if labels else ""))

    def _preferred_report(self) -> Path | None:
        selected = self.report_paths.get(self.report_choice.get().strip())
        if selected and selected.name != "adaptive-next.json":
            return selected
        for name in ("gui-particle-gpu-latest.json", "gui-gpu-latest.json"):
            if name in self.report_paths:
                return self.report_paths[name]
        return None

    @staticmethod
    def _new_output_dir(name: str) -> Path:
        root = Path(__file__).with_name("Results") / name
        path = root / f"run-{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1000000:06d}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _archive_report(prefix: str, report: dict) -> Path:
        root = Path(__file__).with_name("Results")
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1000000:06d}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return path

    def _clear_run_view(self) -> None:
        self.results.clear()
        self.gpu_report = None
        self.particle_gpu_report = None
        for child in self.visual_inner.winfo_children():
            child.destroy()
        self.live_cards.clear(); self.live_images.clear(); self.run_rows.clear(); self.row_paths.clear()
        self.run_table.delete(*self.run_table.get_children())
        self.visual_filter = None
        self.visual_scale = 2
        self._update_summary()

    def _update_summary(self, completed: int | None = None, total: int | None = None) -> None:
        rows = self.results

        def number(row: dict, key: str) -> float:
            try:
                return float(row.get(key, 0) or 0)
            except (TypeError, ValueError):
                return 0.0

        finished = len(rows) if completed is None else completed
        expected = len(rows) if total is None else total
        live = sum(number(row, "live") > 0 for row in rows)
        births = sum(number(row, "births") for row in rows)
        if self.summary_vars:
            self.summary_vars["finished"].set(f"{finished}/{expected}")
            self.summary_vars["live"].set(str(live))
            self.summary_vars["births"].set(f"{births:,.0f}")

    def load_report(self) -> None:
        if self.stop_button["state"] == "normal" and not messagebox.askyesno(
                "Load report", "A run is active. Replace its live dashboard with a saved report?"):
            return
        label = self.report_choice.get().strip()
        path = self.report_paths.get(label)
        if not path:
            messagebox.showinfo("Report history", "Choose a saved report first.")
            return
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                raise ValueError("That JSON file is not a report object.")
            rows = report.get("replays") or report.get("results") or report.get("screening") or []
            if not isinstance(rows, list) or not rows:
                raise ValueError("That JSON file does not contain report rows.")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            messagebox.showerror("Report history", str(error))
            return
        self._clear_run_view()
        self.results = [row for row in rows if isinstance(row, dict)]
        if "replays" in report:
            self.gpu_report = report
        if report.get("backend", "").startswith("gpu-particle"):
            self.particle_gpu_report = report
        for index, result in enumerate(self.results, 1):
            snapshot = result.get("_snapshot_path") or result.get("snapshot_path") or f"report:{index}"
            label_text = result.get("label", f"row-{index:04d}")
            state = "ERROR" if result.get("error") or result.get("_error") else "COMPLETE"
            self._add_run_row(snapshot, index, label_text, result.get("seed", ""), state)
            self._set_run_row(snapshot, state, result)
            if Path(snapshot).exists():
                self._add_live_card(snapshot, index, label_text, result.get("seed", ""))
                try:
                    image = tk.PhotoImage(file=snapshot).zoom(self.visual_scale, self.visual_scale)
                    self.live_images[snapshot] = image
                    self.live_cards[snapshot]["image"].configure(image=image)
                    self.live_cards[snapshot]["state"] = "complete"
                    meta = f'RUN {index:04d} • {label_text} • seed {result.get("seed", "")}\nCOMPLETE • {result.get("live", "")} live'
                    self.live_cards[snapshot]["meta"].configure(text=meta)
                except (tk.TclError, OSError):
                    pass
        self.progress.configure(maximum=max(1, len(self.results)), value=len(self.results))
        self._update_summary(len(self.results), len(self.results))
        self.eta_text.set("ETA: historical")
        self.status.set(f"Loaded report: {label}")
        self.view_status.set(f"Historical report • {len(self.results)} rows loaded")
        self.workspace.select(self.runs_frame)

    def save_preset(self) -> None:
        name = self.preset_name.get().strip() or self.preset_choice.get().strip()
        try:
            path = save_preset(name, self._config_snapshot())
        except (OSError, ValueError) as error:
            messagebox.showerror("Configuration", str(error))
            return
        self.preset_choice.set(path.stem)
        self._refresh_presets()
        self.status.set(f"Saved configuration: {path.stem}")

    def load_preset(self) -> None:
        name = self.preset_choice.get().strip()
        if not name:
            messagebox.showinfo("Configuration", "Choose a saved configuration first.")
            return
        try:
            self._apply_config(load_preset(name))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            messagebox.showerror("Configuration", str(error))
            return
        self.preset_name.set(name)
        self.status.set(f"Loaded configuration: {name}")

    def delete_preset(self) -> None:
        name = self.preset_choice.get().strip()
        if not name:
            return
        if not messagebox.askyesno("Delete configuration", f"Delete saved configuration '{name}'?"):
            return
        try:
            delete_preset(name)
        except OSError as error:
            messagebox.showerror("Configuration", str(error))
            return
        self.preset_choice.set("")
        self.preset_name.set("")
        self._refresh_presets()
        self.status.set(f"Deleted configuration: {name}")

    def _build(self) -> None:
        try:
            ttk.Style(self).theme_use("clam")
        except tk.TclError:
            pass
        self.geometry("1380x900")
        self.minsize(1080, 720)
        self.status = tk.StringVar(value="Ready")
        self.view_status = tk.StringVar(value="No runs yet")

        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 10))
        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text="BEV NOVUS", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(title_box, text="Experiment studio  /  configure, run, observe, iterate", foreground="#667085").pack(anchor="w")
        status_box = ttk.Frame(header, padding=(12, 6))
        status_box.pack(side="right")
        ttk.Label(status_box, textvariable=self.status, font=("Segoe UI", 10, "bold"), anchor="e").pack(anchor="e")
        ttk.Label(status_box, textvariable=self.eta_text, foreground="#667085", anchor="e").pack(anchor="e")

        shell = ttk.PanedWindow(outer, orient="horizontal")
        shell.pack(fill="both", expand=True)
        config_panel = ttk.Frame(shell, padding=(0, 0, 10, 0))
        dashboard = ttk.Frame(shell, padding=(10, 0, 0, 0))
        shell.add(config_panel, weight=0)
        shell.add(dashboard, weight=1)

        ttk.Label(config_panel, text="SETUP", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        settings = ttk.Notebook(config_panel)
        settings.pack(fill="x", pady=(0, 8))
        field_specs = {
            "Core": [("Seeds", "1,2,3"), ("Steps", "200000"), ("Body yield", "0.30,0.40,0.50"),
                     ("Decay", "0.02,0.03,0.04"), ("Particle decay", "0.0005,0.001,0.002"), ("Sample every", "1000")],
            "Performance": [("Workers", "3"), ("Broad configs", "256"), ("GPU screen steps", "20000"),
                            ("GPU batch", "64"), ("Replay top", "8")],
            "Adaptive": [("Adaptive generations", "1"), ("Adaptive configs", "24"), ("Adaptive elites", "6")],
        }
        explanations = {
            "Seeds": "Comma-separated random seeds. Reusing a seed makes conditions reproducible.",
            "Steps": "Number of simulation steps for each run. Larger values reveal longer-term persistence but take longer.",
            "Body yield": "Fraction of consumed resource converted into body mass. The remainder becomes waste.",
            "Decay": "Per-step body-mass decay for field-engine runs. Higher values make persistence harder.",
            "Particle decay": "Per-step body-mass decay for Particle hybrid runs. Lower values match particle-scale dynamics.",
            "Sample every": "How often a run records metrics and refreshes checkpoint data.",
            "Workers": "Number of parallel CPU worker processes. More workers use more CPU and memory.",
            "Broad configs": "Number of sampled parameter configurations used by broad or GPU screening.",
            "GPU screen steps": "Short GPU screening horizon before selected configurations are replayed.",
            "GPU batch": "Number of GPU worlds advanced together. Larger batches need more GPU memory.",
            "Replay top": "Number of top GPU-screened configurations replayed for the full Steps duration.",
            "Adaptive generations": "Number of automatic result-to-next-run iterations.",
            "Adaptive configs": "Number of configurations generated per adaptive generation.",
            "Adaptive elites": "Number of top configurations copied unchanged into the next generation.",
        }
        for tab_name, specs in field_specs.items():
            tab = ttk.Frame(settings, padding=6)
            settings.add(tab, text=tab_name)
            for index, (label, default) in enumerate(specs):
                row, column = divmod(index, 2)
                ttk.Label(tab, text=label).grid(row=row * 2, column=column, sticky="w", padx=4, pady=(3, 0))
                variable = tk.StringVar(value=default)
                self.fields[label] = variable
                entry = ttk.Entry(tab, textvariable=variable, width=16)
                entry.grid(row=row * 2 + 1, column=column, sticky="ew", padx=4, pady=(0, 3))
                self._help(entry, explanations[label])
            for column in range(2):
                tab.columnconfigure(column, weight=1)

        library = ttk.LabelFrame(config_panel, text="Saved configurations")
        library.pack(fill="x", pady=(0, 8))
        ttk.Label(library, text="Choose").grid(row=0, column=0, sticky="w", padx=6, pady=5)
        self.preset_box = ttk.Combobox(library, textvariable=self.preset_choice, state="readonly", width=22)
        self.preset_box.grid(row=0, column=1, columnspan=2, sticky="ew", padx=6, pady=5)
        ttk.Label(library, text="Name").grid(row=1, column=0, sticky="w", padx=6, pady=5)
        preset_name = ttk.Entry(library, textvariable=self.preset_name)
        preset_name.grid(row=1, column=1, columnspan=2, sticky="ew", padx=6, pady=5)
        load_button = ttk.Button(library, text="Load", command=self.load_preset)
        load_button.grid(row=2, column=0, sticky="ew", padx=6, pady=5)
        save_button = ttk.Button(library, text="Save", command=self.save_preset)
        save_button.grid(row=2, column=1, sticky="ew", padx=6, pady=5)
        delete_button = ttk.Button(library, text="Delete", command=self.delete_preset)
        delete_button.grid(row=2, column=2, sticky="ew", padx=6, pady=5)
        for column in range(3):
            library.columnconfigure(column, weight=1)
        for widget, text in ((self.preset_box, "Choose a saved configuration managed by the GUI."),
                             (preset_name, "Name used when saving the current setup as a reusable configuration."),
                             (load_button, "Apply the selected saved setup to the visible controls."),
                             (save_button, "Save the current controls as a reusable setup in the GUI library."),
                             (delete_button, "Delete the selected saved setup from the GUI library.")):
            self._help(widget, text)
        self._refresh_presets()

        rules = ttk.LabelFrame(config_panel, text="Engine and rules")
        rules.pack(fill="x", pady=(0, 8))
        ttk.Label(rules, text="Engine").grid(row=0, column=0, sticky="w", padx=6, pady=5)
        engine_box = ttk.Combobox(rules, textvariable=self.engine, values=("Field", "Particle hybrid"), state="readonly", width=17)
        engine_box.grid(row=0, column=1, columnspan=2, sticky="ew", padx=6, pady=5)
        self._help(engine_box, "Field uses the established grid model. Particle hybrid uses force-bearing particles coupled to resource and waste fields.")
        self.reproduce = tk.BooleanVar(value=True)
        self.mutate = tk.BooleanVar(value=True)
        self.recycle = tk.BooleanVar(value=True)
        self.spatial = tk.BooleanVar(value=True)
        rule_help = {
            "Seed emission": "Allow the field engine to emit new seed bodies. Particle reproduction is not implemented yet.",
            "Mutation": "Allow inherited trait variation in field-engine births.",
            "Recycling": "Return recyclable waste to the resource pool.",
            "Spatial resources": "Keep resource patches localized; off creates a well-mixed control.",
        }
        for index, (label, variable) in enumerate((("Seed emission", self.reproduce), ("Mutation", self.mutate),
                                                    ("Recycling", self.recycle), ("Spatial resources", self.spatial))):
            checkbox = ttk.Checkbutton(rules, text=label, variable=variable)
            checkbox.grid(row=1 + index // 2, column=index % 2, sticky="w", padx=6, pady=4)
            self._help(checkbox, rule_help[label])
        live_check = ttk.Checkbutton(rules, text="Live previews", variable=self.live_previews, command=self._toggle_live_previews)
        live_check.grid(row=3, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        self._help(live_check, "Show refreshed images for active runs. This adds disk and GUI work; many previews can cause lag.")
        ttk.Label(rules, textvariable=self.live_warning, foreground="#996c00", wraplength=280).grid(row=4, column=0, columnspan=3, sticky="w", padx=6, pady=(2, 6))
        for column in range(3):
            rules.columnconfigure(column, weight=1)

        actions = ttk.LabelFrame(config_panel, text="Actions")
        actions.pack(fill="x", pady=(0, 8))
        action_specs = (("start_button", "Run grid", self.start, "Run the Cartesian product of the selected values."),
                        ("broad_button", "Broad sweep", lambda: self.start(broad=True), "Sample a broad parameter space."),
                        ("gpu_button", "GPU screen + replay", self.start_gpu, "Screen many worlds on GPU, then replay selected candidates."),
                        ("overnight_button", "Overnight", self.start_overnight, "Load and start the long campaign preset."),
                        ("particle_campaign_button", "Particle persistence", self.start_particle_campaign, "Run the standard particle persistence panel."),
                        ("adaptive_campaign_button", "Adaptive campaign", self.start_adaptive_campaign, "Run automatic result-to-next-generation iterations."),
                        ("stop_button", "Stop", self.stop, "Request a safe stop after current workers report."),
                        ("export_button", "Export results", self.export, "Save the current report as JSON."),
                        ("adaptive_button", "Load adaptive file", self.load_adaptive_config, "Generate and load a next configuration from a chosen report."))
        for index, (attribute, label, command, explanation) in enumerate(action_specs):
            button = ttk.Button(actions, text=label, command=command)
            button.grid(row=index // 2, column=index % 2, sticky="ew", padx=5, pady=4)
            setattr(self, attribute, button)
            self._help(button, explanation)
        self.stop_button.configure(state="disabled")
        for column in range(2):
            actions.columnconfigure(column, weight=1)
        ttk.Label(config_panel, textvariable=self.help_text, relief="groove", anchor="w", justify="left", wraplength=330).pack(fill="x", pady=(0, 6))

        dashboard_status = ttk.Frame(dashboard)
        dashboard_status.pack(fill="x", pady=(0, 6))
        ttk.Label(dashboard_status, text="LIVE DASHBOARD", font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Label(dashboard_status, textvariable=self.view_status, foreground="#667085").pack(side="left", padx=12)
        summary = ttk.Frame(dashboard)
        summary.pack(fill="x", pady=(0, 8))
        for title in ("finished", "live", "births"):
            self.summary_vars[title] = tk.StringVar(value="0")
        for title, label in (("finished", "FINISHED"), ("live", "LIVE WORLDS"), ("births", "BIRTHS")):
            card = ttk.LabelFrame(summary, text=label)
            card.pack(side="left", fill="x", expand=True, padx=(0, 6))
            ttk.Label(card, textvariable=self.summary_vars[title], font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=8, pady=5)
        self.progress = ttk.Progressbar(dashboard, mode="determinate", maximum=1, value=0)
        self.progress.pack(fill="x", pady=(0, 8))
        history = ttk.LabelFrame(dashboard, text="Report history")
        history.pack(fill="x", pady=(0, 8))
        ttk.Label(history, text="Saved report").pack(side="left", padx=6, pady=5)
        self.report_box = ttk.Combobox(history, textvariable=self.report_choice, state="readonly", width=42)
        self.report_box.pack(side="left", fill="x", expand=True, padx=6, pady=5)
        report_load = ttk.Button(history, text="Load report", command=self.load_report)
        report_load.pack(side="left", padx=3, pady=5)
        report_refresh = ttk.Button(history, text="Refresh", command=self._refresh_reports)
        report_refresh.pack(side="left", padx=3, pady=5)
        self._help(self.report_box, "Choose a saved report discovered in Results or Results/adaptive-campaign.")
        self._help(report_load, "Load historical rows and matching saved frames into the dashboard without opening the filesystem.")
        self._help(report_refresh, "Rescan the GUI-managed Results report list.")
        self._refresh_reports()

        self.workspace = ttk.Notebook(dashboard)
        self.workspace.pack(fill="both", expand=True)
        runs_frame = ttk.Frame(self.workspace, padding=4)
        self.runs_frame = runs_frame
        self.workspace.add(runs_frame, text="Runs & results")
        columns = ("run", "condition", "seed", "state", "live", "births", "viable")
        self.run_table = ttk.Treeview(runs_frame, columns=columns, show="headings", selectmode="extended")
        headings = {"run": "Run", "condition": "Condition", "seed": "Seed", "state": "State", "live": "Live", "births": "Births", "viable": "Viable"}
        for column in columns:
            self.run_table.heading(column, text=headings[column], command=lambda name=column: self._sort_runs(name))
            self.run_table.column(column, width=230 if column == "condition" else 78, anchor="center")
        self.run_table.column("state", width=110)
        run_scroll = ttk.Scrollbar(runs_frame, orient="vertical", command=self.run_table.yview)
        self.run_table.configure(yscrollcommand=run_scroll.set)
        self.run_table.grid(row=0, column=0, sticky="nsew")
        run_scroll.grid(row=0, column=1, sticky="ns")
        details = ttk.LabelFrame(runs_frame, text="Selected run")
        details.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Label(details, textvariable=self.detail_text, justify="left", anchor="w", wraplength=900).pack(fill="x", padx=8, pady=7)
        runs_frame.rowconfigure(0, weight=1)
        runs_frame.columnconfigure(0, weight=1)
        self.run_table.bind("<<TreeviewSelect>>", self._on_run_selection)
        self.run_table.bind("<Double-1>", lambda _event: self.focus_selected())

        visual_frame = ttk.Frame(self.workspace)
        self.visual_frame = visual_frame
        self.workspace.add(visual_frame, text="Visual explorer")
        visual_tools = ttk.Frame(visual_frame)
        visual_tools.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(6, 2))
        ttk.Button(visual_tools, text="Show all", command=self.show_all_visuals).pack(side="left")
        ttk.Button(visual_tools, text="Focus selected", command=self.focus_selected).pack(side="left", padx=6)
        ttk.Button(visual_tools, text="Compare 2-4", command=self.compare_selected).pack(side="left")
        ttk.Label(visual_tools, text="Select runs in Runs & results, then focus or compare.", foreground="#667085").pack(side="left", padx=10)
        ttk.Label(visual_frame, textvariable=self.view_status, anchor="w").grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(2, 2))
        visual_frame.rowconfigure(2, weight=1)
        visual_frame.columnconfigure(0, weight=1)
        self.visual_canvas = tk.Canvas(visual_frame, background="black", highlightthickness=0)
        scrollbar = ttk.Scrollbar(visual_frame, orient="vertical", command=self.visual_canvas.yview)
        self.visual_canvas.configure(yscrollcommand=scrollbar.set)
        self.visual_canvas.grid(row=2, column=0, sticky="nsew")
        scrollbar.grid(row=2, column=1, sticky="ns")
        self.visual_inner = ttk.Frame(self.visual_canvas)
        self.visual_window = self.visual_canvas.create_window((8, 8), window=self.visual_inner, anchor="nw")
        self.visual_inner.bind("<Configure>", lambda _: self.visual_canvas.configure(scrollregion=self.visual_canvas.bbox("all")))
        self.visual_canvas.bind("<Configure>", lambda event: self._relayout_live_cards(event.width))

    def jobs(self, broad: bool = False) -> list[dict]:
        seeds = numbers(self.fields["Seeds"].get(), int)
        engine = "particle" if self.engine.get() == "Particle hybrid" else "field"
        steps = int(self.fields["Steps"].get())
        sample_every = int(self.fields["Sample every"].get())
        if steps < 1 or sample_every < 1:
            raise ValueError("Steps and sample interval must be positive.")
        if broad:
            config_count = int(self.fields["Broad configs"].get())
            if config_count < 1:
                raise ValueError("Broad configs must be positive.")
            configs = latin_hypercube(config_count, seed=7)
            return [{"label": f"lhs-{index:04d}", "seed": seed, "steps": steps,
                     "sample_every": sample_every, "reproduce": self.reproduce.get(),
                     "mutate": self.mutate.get(), "recycle": self.recycle.get(),
                     "spatial": self.spatial.get(), "engine": engine, **config}
                    for index, config in enumerate(configs, 1) for seed in seeds]
        if engine == "particle" and self.adaptive_configs:
            jobs = []
            for index, config in enumerate(self.adaptive_configs, 1):
                for seed in seeds:
                    jobs.append({
                        "label": f"adaptive-{index:04d}", "seed": seed, "steps": steps,
                        "body_yield": config["body_yield"], "decay_rate": config["decay_rate"],
                        "sample_every": sample_every, "reproduce": self.reproduce.get(),
                        "mutate": self.mutate.get(), "recycle": self.recycle.get(),
                        "spatial": self.spatial.get(), **config, "engine": engine,
                    })
            return jobs
        yields = numbers(self.fields["Body yield"].get())
        decays = numbers(self.fields["Particle decay"].get() if engine == "particle" else self.fields["Decay"].get())
        jobs = []
        for body_yield in yields:
            for decay_rate in decays:
                for seed in seeds:
                    jobs.append({
                        "label": f"yield={body_yield:g}, decay={decay_rate:g}",
                        "seed": seed, "steps": steps, "body_yield": body_yield,
                        "decay_rate": decay_rate, "sample_every": sample_every,
                        "reproduce": self.reproduce.get(), "mutate": self.mutate.get(),
                        "recycle": self.recycle.get(), "spatial": self.spatial.get(),
                     "metabolism": 0.035, "diffusion": 0.5, "waste_inhibition": 0.1,
                        "recycle_rate": 0.1, "seed_interval": 20, "source_scale": 0.5,
                        "steering": 5.0, "seed_fraction": 0.05, "mutation_scale": 0.02,
                        "resource_patches": 5, "body_patches": 5, "resource_strength": 1.15,
                        "body_strength": 1.5, "resource_regrowth": 0.01, "resource_capacity": 1.0,
                        "waste_decay": 0.02, "waste_diffusion": 0.02,
                        "dormancy_threshold": 0.06, "dormancy_cost": 0.15,
                        "complexity_pressure": 0.65,
                        "engine": engine,
                    })
        return jobs

    def start(self, broad: bool = False) -> None:
        if self.adaptive_configs and not broad and self.engine.get() == "Particle hybrid":
            self.start_gpu_particle()
            return
        try:
            jobs = self.jobs(broad)
            workers = max(1, int(self.fields["Workers"].get()))
        except (TypeError, ValueError) as error:
            messagebox.showerror("Invalid setup", str(error))
            return
        self.results.clear()
        self.gpu_report = None
        for child in self.visual_inner.winfo_children():
            child.destroy()
        self.live_cards.clear(); self.live_images.clear(); self.run_rows.clear(); self.row_paths.clear()
        self.run_table.delete(*self.run_table.get_children())
        self.visual_filter = None; self.visual_scale = 2
        snapshot_dir = self._new_output_dir("gui-snapshots")
        for index, job in enumerate(jobs, 1):
            snapshot_path = snapshot_dir / f"run-{index:04d}.ppm"
            snapshot_path.unlink(missing_ok=True)
            job["snapshot_path"] = str(snapshot_path)
            self._add_run_row(str(snapshot_path), index, job["label"], job["seed"])
            if self.live_previews.get():
                job["live_snapshot_path"] = str(snapshot_path)
                job["live_snapshot_every"] = max(25, min(250, int(self.fields["Sample every"].get())))
                self._add_live_card(str(snapshot_path), index, job["label"], job["seed"], job["live_snapshot_every"])
        self.stop_event.clear()
        self.adaptive_campaign_active = False
        self.run_started_at = time.perf_counter()
        self.total_jobs = len(jobs)
        self.completed_jobs = 0
        self._update_summary(0, self.total_jobs)
        self.view_status.set(f"{len(jobs)} simulations loaded • waiting for first frames")
        self.progress.configure(maximum=self.total_jobs, value=0)
        self.start_button.configure(state="disabled")
        self.broad_button.configure(state="disabled")
        self.gpu_button.configure(state="disabled")
        self.overnight_button.configure(state="disabled")
        self.particle_campaign_button.configure(state="disabled")
        self.adaptive_campaign_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set(f"Running 0/{len(jobs)} — {workers} parallel workers — generating results")
        self.worker = threading.Thread(target=self._run, args=(jobs, workers), daemon=True)
        self.worker.start()

    def load_adaptive_config(self) -> None:
        default = Path(__file__).with_name("Results") / "adaptive-next.json"
        chosen = filedialog.askopenfilename(
            title="Choose result report", filetypes=(("JSON", "*.json"), ("All files", "*.*")))
        if not chosen:
            return
        path = Path(chosen)
        try:
            output = default
            build_next_config(path, output)
            config = json.loads(output.read_text(encoding="utf-8"))
            self.adaptive_configs = config.get("configs") or None
            self.adaptive_campaign_active = False
            defaults = config.get("gui_defaults", {})
            for name, value in defaults.items():
                if name in self.fields:
                    self.fields[name].set(str(value))
            if defaults.get("Engine"):
                self.engine.set(defaults["Engine"])
            self.status.set(f"Adaptive generation {config.get('generation', '?')} loaded: {len(config.get('configs', []))} configs")
            self.help_text.set(f"Adaptive config saved to {output}. Review it, then start the next run.")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            messagebox.showerror("Adaptive config error", str(error))
        if self.live_previews.get():
            self._refresh_live_previews()

    def _load_initial_adaptive(self) -> None:
        path = Path(__file__).with_name("Results") / "adaptive-next.json"
        if not path.exists():
            return
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                return
            configs = config.get("configs") or []
            if not isinstance(configs, list) or not configs:
                return
            self.adaptive_configs = configs
            defaults = config.get("gui_defaults") or {}
            if not isinstance(defaults, dict):
                defaults = {}
            for name, value in defaults.items():
                if name in self.fields:
                    self.fields[name].set(str(value))
            if defaults.get("Engine"):
                self.engine.set(defaults["Engine"])
            self.fields["Adaptive configs"].set(str(len(configs)))
            self.status.set(f"Adaptive generation {config.get('generation', '?')} loaded: {len(configs)} configs ready")
            self.help_text.set(f"Loaded {path.name}. Review the adaptive settings, then start the next run when ready.")
        except (OSError, ValueError, json.JSONDecodeError):
            self.status.set("Ready - adaptive-next.json could not be loaded")

    def start_adaptive_campaign(self) -> None:
        try:
            generations = int(self.fields["Adaptive generations"].get())
            count = int(self.fields["Adaptive configs"].get())
            elites = int(self.fields["Adaptive elites"].get())
            if generations < 1 or count < 1 or elites < 1 or elites > count:
                raise ValueError("Adaptive generations/configs must be positive and elites cannot exceed configs.")
        except (TypeError, ValueError) as error:
            messagebox.showerror("Invalid adaptive setup", str(error))
            return
        chosen_path = self._preferred_report()
        chosen = str(chosen_path) if chosen_path else filedialog.askopenfilename(
            title="Choose starting result report", filetypes=(("JSON", "*.json"), ("All files", "*.*")))
        if not chosen:
            return
        try:
            output = Path(__file__).with_name("Results") / "adaptive-next.json"
            config = build_next_config(Path(chosen), output, count=count, elite_count=elites, seed=7)
            self.adaptive_configs = config["configs"]
            self.adaptive_campaign_active = True
            self.adaptive_generation = int(config["generation"])
            self.adaptive_generation_total = generations
            self.adaptive_config_count = count
            self.adaptive_elite_count = elites
            self.adaptive_source_path = Path(chosen)
            self.engine.set("Particle hybrid")
            self.live_previews.set(False)
            self._toggle_live_previews()
            self.run_started_at = time.perf_counter()
            self.help_text.set(f"Adaptive campaign loaded from {Path(chosen).name}; generation {self.adaptive_generation}/{generations} is ready.")
            self.start_gpu_particle()
        except (OSError, ValueError, json.JSONDecodeError) as error:
            messagebox.showerror("Adaptive campaign error", str(error))

    def _toggle_live_previews(self) -> None:
        self.live_warning.set("WARNING: live previews add rendering and file I/O; many runs at once can cause extreme lag." if self.live_previews.get() else "Live previews off - lowest overhead mode.")

    @staticmethod
    def _duration(seconds: float) -> str:
        seconds = max(0, int(seconds))
        if seconds < 60:
            return f"{seconds}s"
        minutes, remainder = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}m {remainder:02d}s"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes:02d}m"

    def _update_eta(self, done: float, total: float) -> None:
        if not self.run_started_at or done <= 0 or total <= done:
            self.eta_text.set("ETA: calculating..." if done <= 0 else "ETA: <1s")
            return
        elapsed = time.perf_counter() - self.run_started_at
        remaining = elapsed * (total - done) / done
        self.eta_text.set(f"ETA: {self._duration(remaining)}")

    def _add_run_row(self, path: str, index: int, label: str, seed: int, state: str = "QUEUED") -> None:
        iid = f"run-{index:04d}"
        self.run_rows[path] = iid
        self.row_paths[iid] = path
        self.run_table.insert("", "end", iid=iid, values=(f"RUN {index:04d}", label, seed, state, "", "", ""))

    def _set_run_row(self, path: str, state: str, result: dict | None = None) -> None:
        iid = self.run_rows.get(path)
        if not iid:
            return
        values = list(self.run_table.item(iid, "values"))
        values[3] = state
        if result:
            values[4:7] = (result.get("live", ""), result.get("births", ""), result.get("viable", ""))
        self.run_table.item(iid, values=values)

    def _sort_runs(self, column: str) -> None:
        if column == self.sort_column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        items = [(self.run_table.set(iid, column), iid) for iid in self.run_table.get_children("")]

        def key(item: tuple[str, str]):
            try:
                return (0, float(item[0]))
            except (TypeError, ValueError):
                return (1, item[0].lower())

        for index, (_, iid) in enumerate(sorted(items, key=key, reverse=self.sort_reverse)):
            self.run_table.move(iid, "", index)

    def _selected_paths(self) -> list[str]:
        return [self.row_paths[iid] for iid in self.run_table.selection() if iid in self.row_paths]

    def _on_run_selection(self, _event=None) -> None:
        selected = self._selected_paths()
        for path, card in self.live_cards.items():
            card["card"].configure(relief="sunken" if path in selected else "ridge")
        if not selected:
            self.detail_text.set("Select a run to inspect its metrics and saved frame.")
            return
        path = selected[0]
        result = next((row for row in self.results
                       if row.get("_snapshot_path") == path or row.get("snapshot_path") == path), None)
        if not result:
            self.detail_text.set(f"{path} • no final metrics recorded yet")
            return
        self.detail_text.set(
            f'{result.get("label", "run")} • seed {result.get("seed", "")} • '
            f'live {result.get("live", "")} • births {result.get("births", "")} • '
            f'viable {result.get("viable", "")} • mass drift {result.get("mass_drift", "")} • '
            f'finite {result.get("finite", "unknown")} • frame {result.get("_snapshot_path", "not saved")}')

    def _select_path(self, path: str, focus: bool = False) -> None:
        iid = self.run_rows.get(path)
        if iid:
            self.run_table.selection_set(iid)
            self.run_table.focus(iid)
            self.run_table.see(iid)
        if focus:
            self.focus_selected()

    def show_all_visuals(self) -> None:
        self.visual_filter = None
        self.visual_scale = 2
        self.workspace.select(self.visual_frame)
        self._relayout_live_cards()

    def focus_selected(self) -> None:
        selected = self._selected_paths()
        if not selected:
            messagebox.showinfo("Choose a run", "Select one run in the Runs tab first.")
            return
        self.visual_filter = {selected[0]}
        self.visual_scale = 5
        self.workspace.select(self.visual_frame)
        self._relayout_live_cards()

    def compare_selected(self) -> None:
        selected = self._selected_paths()[:4]
        if len(selected) < 2:
            messagebox.showinfo("Choose runs", "Select 2 to 4 runs in the Runs tab to compare.")
            return
        self.visual_filter = set(selected)
        self.visual_scale = 3
        self.workspace.select(self.visual_frame)
        self._relayout_live_cards()

    def _refresh_live_previews(self) -> None:
        now = time.time()
        refreshing = 0
        for path, card in self.live_cards.items():
            if not Path(path).exists():
                self._set_run_row(path, "QUEUED")
                card["meta"].configure(text=f'{card["run"]} • {card["label"]} • seed {card["seed"]}\nQUEUED • waiting for first frame')
                continue
            try:
                mtime = Path(path).stat().st_mtime_ns
                if mtime != card["mtime"]:
                    image = tk.PhotoImage(file=path).zoom(self.visual_scale, self.visual_scale)
                    self.live_images[path] = image
                    card["image"].configure(image=image)
                    card["mtime"] = mtime
                    card["updated"] = now
                    card["frames"] += 1
                    self._set_run_row(path, "UPDATING")
                    step = card["frames"] * card["interval"]
                    card["meta"].configure(text=f'{card["run"]} • {card["label"]} • seed {card["seed"]}\nUPDATING • frame {card["frames"]} • step ~{step:,} • {time.strftime("%H:%M:%S")}')
                if now - card["updated"] < 1.5:
                    refreshing += 1
                elif card["state"] == "running":
                    age = now - card["updated"]
                    state = "STALE" if age > 3 else "LIVE"
                    self._set_run_row(path, state)
                    step = card["frames"] * card["interval"]
                    card["meta"].configure(text=f'{card["run"]} • {card["label"]} • seed {card["seed"]}\n{state} • frame {card["frames"]} • step ~{step:,} • {age:.1f}s ago')
            except (tk.TclError, OSError) as error:
                self._set_run_row(path, "READ ERROR")
                card["meta"].configure(text=f'{card["run"]} • {card["label"]} • seed {card["seed"]}\nFRAME READ ERROR • {str(error)[:90]}')
        if self.live_cards:
            self.view_status.set(f"{len(self.live_cards)} simulations • {refreshing} updating now")
        if self.live_previews.get() and self.live_cards:
            self.after(750, self._refresh_live_previews)

    def _add_live_card(self, path: str, index: int, label: str, seed: int, interval: int = 0) -> None:
        card = ttk.Frame(self.visual_inner, padding=8, relief="ridge")
        image = ttk.Label(card, text="waiting for first frame", anchor="center")
        image.pack(fill="x")
        meta = ttk.Label(card, text=f"RUN {index:04d} • {label} • seed {seed}\nQUEUED", justify="left")
        meta.pack(fill="x", pady=(6, 0))
        self.live_cards[path] = {"card": card, "image": image, "meta": meta, "run": f"RUN {index:04d}",
                                 "label": label, "seed": seed, "mtime": -1, "updated": 0.0, "frames": 0,
                                 "interval": interval, "state": "running"}
        for widget in (card, image, meta):
            widget.bind("<Button-1>", lambda _event, selected=path: self._select_path(selected, focus=True))
        self._relayout_live_cards()

    def _relayout_live_cards(self, width: int | None = None) -> None:
        if not self.live_cards:
            return
        width = width or self.visual_canvas.winfo_width()
        tile_width = 250 if self.visual_scale == 2 else 360 if self.visual_scale == 3 else 540
        columns = max(1, (max(width, 260) - 24) // tile_width)
        visible = [(path, record) for path, record in self.live_cards.items()
                   if self.visual_filter is None or path in self.visual_filter]
        for record in self.live_cards.values():
            record["card"].grid_remove()
        for index, (path, record) in enumerate(visible):
            if record["mtime"] >= 0:
                try:
                    image = tk.PhotoImage(file=path).zoom(self.visual_scale, self.visual_scale)
                    self.live_images[path] = image
                    record["image"].configure(image=image)
                except tk.TclError:
                    pass
            record["card"].grid(row=index // columns, column=index % columns, padx=6, pady=6, sticky="nsew")
        for column in range(columns):
            self.visual_inner.columnconfigure(column, weight=1)

    def start_gpu(self) -> None:
        if self.engine.get() == "Particle hybrid":
            self.start_gpu_particle()
            return
        if self.live_previews.get():
            self.live_warning.set("GPU screening does not publish live frames; use Run grid or Broad sweep for live previews. Replay images appear after screening completes.")
        try:
            config_count = int(self.fields["Broad configs"].get())
            seeds = numbers(self.fields["Seeds"].get(), int)
            screen_steps = int(self.fields["GPU screen steps"].get())
            replay_steps = int(self.fields["Steps"].get())
            sample_every = int(self.fields["Sample every"].get())
            batch_size = int(self.fields["GPU batch"].get())
            replay_top = min(int(self.fields["Replay top"].get()), config_count)
            workers = max(1, int(self.fields["Workers"].get()))
            if min(config_count, screen_steps, replay_steps, sample_every, batch_size, replay_top) < 1:
                raise ValueError("GPU sweep values must be positive.")
        except (TypeError, ValueError) as error:
            messagebox.showerror("Invalid setup", str(error))
            return
        self.status.set("Running reproduction/mutation preflight...")
        try:
            check = reproduction_preflight()
        except Exception as error:
            self.status.set("Preflight failed")
            messagebox.showerror("GPU preflight failed", str(error))
            return
        self.status.set(f"Preflight passed: {check['births']} mutation checks")
        self.results.clear(); self.gpu_report = None; self.live_cards.clear(); self.live_images.clear(); self.run_rows.clear(); self.row_paths.clear()
        self.run_table.delete(*self.run_table.get_children())
        self.visual_filter = None; self.visual_scale = 2
        for child in self.visual_inner.winfo_children():
            child.destroy()
        self.stop_event.clear()
        self.run_started_at = time.perf_counter()
        self.gpu_screen_total = config_count * len(seeds)
        self.total_jobs = self.gpu_screen_total + replay_top * len(seeds)
        self._update_summary(0, self.total_jobs)
        self.progress.configure(maximum=self.total_jobs, value=0)
        self.start_button.configure(state="disabled"); self.broad_button.configure(state="disabled")
        self.gpu_button.configure(state="disabled"); self.overnight_button.configure(state="disabled"); self.particle_campaign_button.configure(state="disabled"); self.adaptive_campaign_button.configure(state="disabled"); self.stop_button.configure(state="normal")
        self.status.set(f"Preparing {self.gpu_screen_total} GPU screens")
        configs = latin_hypercube(config_count, seed=7)
        output = self._new_output_dir("gpu-snapshots")
        controls = {"reproduce": self.reproduce.get(), "mutate": self.mutate.get(),
                    "recycle": self.recycle.get(), "spatial": self.spatial.get()}
        self.worker = threading.Thread(target=self._run_gpu,
            args=(configs, seeds, screen_steps, sample_every, batch_size, replay_top, replay_steps, workers, output, controls), daemon=True)
        self.worker.start()

    def start_overnight(self) -> None:
        preset = {
            "Seeds": "1,2,3,4,5,6,7,8", "Broad configs": "768", "GPU screen steps": "40000",
            "Steps": "500000", "Sample every": "5000", "GPU batch": "128", "Replay top": "12", "Workers": "4",
        }
        for name, value in preset.items():
            self.fields[name].set(value)
        self.start_gpu()

    def start_particle_campaign(self) -> None:
        self.adaptive_configs = None
        self.adaptive_campaign_active = False
        preset = {
            "Seeds": "1,2,3,4,5,6,7,8",
            "Steps": "200000",
            "Body yield": "0.55,0.72,0.90",
            "Particle decay": "0.0001,0.00025,0.0005,0.001",
            "GPU batch": "32",
            "Workers": "4",
        }
        for name, value in preset.items():
            self.fields[name].set(value)
        self.engine.set("Particle hybrid")
        self.live_previews.set(False)
        self._toggle_live_previews()
        self.run_started_at = time.perf_counter()
        self.start_gpu_particle()

    def start_gpu_particle(self) -> None:
        try:
            jobs = self.jobs()
            batch_size = max(1, int(self.fields["GPU batch"].get()))
        except (TypeError, ValueError) as error:
            messagebox.showerror("Invalid GPU particle setup", str(error))
            return
        self.results.clear(); self.gpu_report = None; self.particle_gpu_report = None
        self.live_cards.clear(); self.live_images.clear(); self.run_rows.clear(); self.row_paths.clear()
        self.run_table.delete(*self.run_table.get_children())
        self.visual_filter = None; self.visual_scale = 2
        for child in self.visual_inner.winfo_children():
            child.destroy()
        output = self._new_output_dir("gpu-particle-snapshots")
        for index, job in enumerate(jobs, 1):
            snapshot = output / f"particle-gpu-{index:04d}.ppm"
            snapshot.unlink(missing_ok=True)
            job["snapshot_path"] = str(snapshot)
            self._add_run_row(str(snapshot), index, job["label"], job["seed"])
        self.stop_event.clear()
        self.total_jobs = len(jobs)
        self._update_summary(0, self.total_jobs)
        self.progress.configure(maximum=self.total_jobs, value=0)
        self.start_button.configure(state="disabled"); self.broad_button.configure(state="disabled")
        self.gpu_button.configure(state="disabled"); self.overnight_button.configure(state="disabled")
        self.particle_campaign_button.configure(state="disabled"); self.adaptive_campaign_button.configure(state="disabled"); self.stop_button.configure(state="normal")
        self.status.set(f"GPU particle campaign: {len(jobs)} worlds in batches of {batch_size}")
        for job in jobs:
            self._set_run_row(job["snapshot_path"], "RUNNING")
        self.view_status.set(f"{len(jobs)} particle worlds • GPU batches active")
        self.worker = threading.Thread(target=self._run_gpu_particle, args=(jobs, int(self.fields["Steps"].get()), batch_size, output), daemon=True)
        self.worker.start()

    def _run_gpu_particle(self, jobs: list[dict], steps: int, batch_size: int, output: Path) -> None:
        try:
            report = run_gpu_particle_campaign(jobs, steps, batch_size, output,
                                               self.gpu_particle_progress, self.stop_event.is_set)
            self.after(0, self.add_gpu_particle_report, report)
        except Exception as error:
            self.after(0, self.gpu_particle_failed, str(error))

    def gpu_particle_progress(self, _stage: str, done: int, total: int, message: str) -> None:
        def update() -> None:
            self.progress.configure(value=done)
            if self.adaptive_campaign_active:
                overall_done = (self.adaptive_generation - 1) * total + done
                overall_total = self.adaptive_generation_total * total
                self.status.set(f"Adaptive generation {self.adaptive_generation}/{self.adaptive_generation_total} - {message}: {done:.0f}/{total}")
                self._update_eta(overall_done, overall_total)
            else:
                self.status.set(f"{message}: {done:.0f}/{total}")
                self._update_eta(done, total)
            self.view_status.set(f"GPU progress • {done:.0f}/{total} world checkpoints")
        self.after(0, update)

    def add_gpu_particle_report(self, report: dict) -> None:
        self.particle_gpu_report = report
        report_path = Path(__file__).with_name("Results") / "gui-particle-gpu-latest.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        self._archive_report("gui-particle-gpu", report)
        self._refresh_reports()
        self.results = report["results"]
        for completed, result in enumerate(self.results, 1):
            self.add_result(result, completed, self.total_jobs)
        if self.adaptive_campaign_active:
            campaign_dir = report_path.parent / "adaptive-campaign"
            campaign_dir.mkdir(parents=True, exist_ok=True)
            generation_path = campaign_dir / f"generation-{self.adaptive_generation:04d}.json"
            generation_report = {**report, "generation": self.adaptive_generation}
            generation_path.write_text(json.dumps(generation_report, indent=2), encoding="utf-8")
            if self.adaptive_generation < self.adaptive_generation_total and not self.stop_event.is_set():
                self.status.set(f"Generation {self.adaptive_generation}/{self.adaptive_generation_total} complete - preparing next generation")
                self.after(100, self._start_next_adaptive_generation, generation_path)
                return
            self.adaptive_campaign_active = False
        self.finished(len(self.results), self.total_jobs)

    def _start_next_adaptive_generation(self, report_path: Path) -> None:
        try:
            output = Path(__file__).with_name("Results") / "adaptive-next.json"
            config = build_next_config(report_path, output, count=self.adaptive_config_count,
                                       elite_count=self.adaptive_elite_count, seed=7 + self.adaptive_generation)
            self.adaptive_configs = config["configs"]
            self.adaptive_generation = int(config["generation"])
            self.adaptive_source_path = report_path
            self.start_gpu_particle()
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self.adaptive_campaign_active = False
            self.gpu_particle_failed(f"Could not prepare adaptive generation: {error}")

    def gpu_particle_failed(self, error: str) -> None:
        self.adaptive_campaign_active = False
        self.finished(int(self.progress["value"]), self.total_jobs)
        messagebox.showerror("GPU particle campaign failed", error)

    def _run_gpu(self, configs, seeds, screen_steps, sample_every, batch_size, replay_top, replay_steps, workers, output, controls) -> None:
        try:
            report = screen_and_replay(configs, seeds, screen_steps, sample_every, batch_size, replay_top,
                                       replay_steps, workers, output, self.gpu_progress, self.stop_event.is_set, controls)
            self.after(0, self.add_gpu_report, report)
        except Exception as error:
            self.after(0, self.gpu_failed, str(error))

    def gpu_progress(self, stage: str, done: int, total: int, message: str) -> None:
        value = done if stage == "gpu" else self.gpu_screen_total + done
        self.after(0, lambda: (self.progress.configure(value=value),
                               self.status.set(f"{message}: {done:.0f}/{total}"),
                               self._update_eta(value, self.total_jobs)))

    def add_gpu_report(self, report: dict) -> None:
        self.gpu_report = report
        report_path = Path(__file__).with_name("Results") / "gui-gpu-latest.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        self._archive_report("gui-gpu", report)
        self._refresh_reports()
        self.results = report["replays"]
        for result in self.results:
            self.add_result(result, int(self.progress["value"]), self.total_jobs)
        self.finished(self.total_jobs, self.total_jobs)

    def gpu_failed(self, error: str) -> None:
        self.finished(int(self.progress["value"]), self.total_jobs)
        messagebox.showerror("GPU sweep failed", error)

    def _run(self, jobs: list[dict], workers: int) -> None:
        completed = 0
        with ProcessPoolExecutor(max_workers=workers) as pool:
            future_jobs = {pool.submit(run_one, job): job for job in jobs}
            for future in as_completed(future_jobs):
                if self.stop_event.is_set():
                    for pending in future_jobs:
                        pending.cancel()
                    break
                job = future_jobs[future]
                try:
                    result = asdict(future.result())
                except Exception as error:  # keep one failed run from hiding all completed results
                    result = {"label": f"ERROR: {error}", "seed": "", "live": "", "births": "", "viable": "",
                              "compactness": 0, "boundary_ratio": 0, "trait_diversity": 0.0, "groups": ""}
                    result["_error"] = str(error)
                result["_snapshot_path"] = job["snapshot_path"]
                self.results.append(result)
                completed += 1
                self.after(0, self.add_result, result, completed, len(jobs))
        self.after(0, self.finished, completed, len(jobs))

    def add_result(self, result: dict, completed: int, total: int) -> None:
        snapshot = result.get("_snapshot_path")
        if snapshot and snapshot not in self.run_rows:
            self._add_run_row(snapshot, len(self.run_rows) + 1, result["label"], result["seed"])
        if result.get("_error") and snapshot in self.live_cards:
            card = self.live_cards[snapshot]
            card["state"] = "error"
            self._set_run_row(snapshot, "ERROR", result)
            card["meta"].configure(text=f'{card["run"]} • {card["label"]} • seed {card["seed"]}\nERROR • {result["_error"][:90]}')
            snapshot = None
        if snapshot in self.live_cards and snapshot and Path(snapshot).exists():
            image = tk.PhotoImage(file=snapshot).zoom(self.visual_scale, self.visual_scale)
            self.live_images[snapshot] = image
            self.live_cards[snapshot]["image"].configure(image=image)
            self.live_cards[snapshot]["state"] = "complete"
            self._set_run_row(snapshot, "COMPLETE", result)
            self.live_cards[snapshot]["meta"].configure(text=f'{self.live_cards[snapshot]["run"]} • {result["label"]} • seed {result["seed"]}\nCOMPLETE • {result["live"]} live')
            snapshot = None
        if snapshot and Path(snapshot).exists():
            image = tk.PhotoImage(file=snapshot).zoom(self.visual_scale, self.visual_scale)
            self._add_live_card(snapshot, len(self.live_cards) + 1, result["label"], result["seed"])
            card = self.live_cards[snapshot]
            self.live_images[snapshot] = image
            card["image"].configure(image=image)
            card["state"] = "complete"
            self._set_run_row(snapshot, "COMPLETE", result)
            card["meta"].configure(text=f'{card["run"]} - {result["label"]} - seed {result["seed"]}\nCOMPLETE - {result["live"]} live')
        self.progress.configure(value=completed)
        self._update_summary(completed, total)
        self._update_eta(completed, total)
        self.status.set(f"Results generated: {completed}/{total} — {total - completed} remaining")

    def finished(self, completed: int, total: int) -> None:
        self.start_button.configure(state="normal")
        self.broad_button.configure(state="normal")
        self.gpu_button.configure(state="normal")
        self.overnight_button.configure(state="normal")
        self.particle_campaign_button.configure(state="normal")
        self.adaptive_campaign_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.progress.configure(value=completed)
        self._update_summary(completed, total)
        self.eta_text.set("ETA: stopped" if self.stop_event.is_set() else "ETA: complete")
        self.status.set("Stopped" if self.stop_event.is_set() else f"Finished — {completed}/{total} results generated")
        self.view_status.set(f"{len(self.live_cards)} simulations • {completed}/{total} {'stopped' if self.stop_event.is_set() else 'complete'}")

    def stop(self) -> None:
        self.stop_event.set()
        self.status.set("Stopping…")

    def export(self) -> None:
        if not self.results:
            messagebox.showinfo("No results", "Run an experiment grid first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=(("JSON", "*.json"), ("All files", "*.*")))
        if path:
            exportable = self.particle_gpu_report or self.gpu_report or [{key: value for key, value in result.items() if not key.startswith("_")} for result in self.results]
            Path(path).write_text(json.dumps(exportable, indent=2), encoding="utf-8")
            self.status.set(f"Saved {Path(path).name}")


if __name__ == "__main__":
    ExperimentApp().mainloop()
