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
from experiments import run_condition, run_particle_condition
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
        self.geometry("1080x680")
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
        self._build()

    def _help(self, widget: tk.Widget, text: str) -> None:
        widget.bind("<Enter>", lambda _event: self.help_text.set(text))
        widget.bind("<FocusIn>", lambda _event: self.help_text.set(text))

    def _build(self) -> None:
        controls = ttk.LabelFrame(self, text="Experiment grid")
        controls.pack(fill="x", padx=10, pady=10)
        specs = [
            ("Seeds", "1,2,3"), ("Steps", "200000"),
            ("Body yield", "0.30,0.40,0.50"), ("Decay", "0.02,0.03,0.04"),
            ("Particle decay", "0.0005,0.001,0.002"),
            ("Sample every", "1000"), ("Workers", "3"), ("Broad configs", "256"),
            ("GPU screen steps", "20000"), ("GPU batch", "64"), ("Replay top", "8"),
        ]
        explanations = {
            "Seeds": "Comma-separated random seeds. Reusing a seed makes conditions reproducible.",
            "Steps": "Number of simulation steps for each run. Larger values reveal longer-term persistence but take longer.",
            "Body yield": "Fraction of consumed resource converted into body mass. The remainder becomes waste.",
            "Decay": "Per-step body-mass decay for field-engine runs. Higher values make persistence harder.",
            "Particle decay": "Per-step body-mass decay for Particle hybrid runs. These lower values are tuned for particle-scale dynamics.",
            "Sample every": "How often the run records metrics and refreshes checkpoint data.",
            "Workers": "Number of parallel worker processes. More workers can finish grids faster but use more CPU and memory.",
            "Broad configs": "Number of Latin-hypercube parameter configurations used by Broad sweep or GPU screening.",
            "GPU screen steps": "Short screening horizon for GPU runs before the strongest configurations are replayed on CPU.",
            "GPU batch": "Number of GPU worlds advanced together. Larger batches can improve throughput if GPU memory allows.",
            "Replay top": "Number of top GPU-screened configurations replayed for the full Steps duration.",
        }
        for index, (label, default) in enumerate(specs):
            row, column = divmod(index, 3)
            ttk.Label(controls, text=label).grid(row=row * 2, column=column, sticky="w", padx=8, pady=(8, 0))
            variable = tk.StringVar(value=default)
            self.fields[label] = variable
            entry = ttk.Entry(controls, textvariable=variable, width=22)
            entry.grid(row=row * 2 + 1, column=column, sticky="ew", padx=8, pady=(0, 8))
            self._help(entry, explanations[label])
        for column in range(3):
            controls.columnconfigure(column, weight=1)

        options = ttk.Frame(self)
        options.pack(fill="x", padx=10)
        ttk.Label(options, text="Engine").pack(side="left", padx=(0, 4))
        engine_box = ttk.Combobox(options, textvariable=self.engine, values=("Field", "Particle hybrid"), state="readonly", width=16)
        engine_box.pack(side="left", padx=(0, 12))
        self._help(engine_box, "Simulation engine. Field runs use the established grid model; Particle hybrid runs use force-bearing particles coupled to resource and waste fields.")
        self.reproduce = tk.BooleanVar(value=True)
        self.mutate = tk.BooleanVar(value=True)
        self.recycle = tk.BooleanVar(value=True)
        self.spatial = tk.BooleanVar(value=True)
        for label, variable in (("Seed emission", self.reproduce), ("Mutation", self.mutate),
                                ("Recycling", self.recycle), ("Spatial resources", self.spatial)):
            checkbox = ttk.Checkbutton(options, text=label, variable=variable)
            checkbox.pack(side="left", padx=(0, 14))
            self._help(checkbox, {
                "Seed emission": "Allow the field engine to emit new seed bodies. Particle hybrid reproduction is not implemented yet.",
                "Mutation": "Allow inherited trait variation in field-engine births.",
                "Recycling": "Return recyclable waste to the resource pool instead of leaving it unavailable.",
                "Spatial resources": "Keep resource patches spatially localized. Turning this off creates a well-mixed resource control.",
            }[label])
        live_check = ttk.Checkbutton(options, text="Live previews", variable=self.live_previews, command=self._toggle_live_previews)
        live_check.pack(side="left", padx=(0, 8))
        self._help(live_check, "Show periodically refreshed images for active runs. This adds disk and GUI work; many simultaneous previews can cause extreme lag.")
        ttk.Label(options, textvariable=self.live_warning).pack(side="left", padx=(0, 8))
        self.start_button = ttk.Button(options, text="Run grid", command=self.start)
        self.start_button.pack(side="left", padx=8)
        self._help(self.start_button, "Run the Cartesian product of the selected seeds and parameter values in parallel.")
        self.broad_button = ttk.Button(options, text="Broad sweep", command=lambda: self.start(broad=True))
        self.broad_button.pack(side="left")
        self._help(self.broad_button, "Generate a broad Latin-hypercube sample across the major rules and run it in parallel.")
        self.gpu_button = ttk.Button(options, text="GPU screen + replay", command=self.start_gpu)
        self.gpu_button.pack(side="left", padx=8)
        self._help(self.gpu_button, "Screen many configurations on the GPU, then replay the strongest candidates with the full experiment settings.")
        self.overnight_button = ttk.Button(options, text="Overnight campaign", command=self.start_overnight)
        self.overnight_button.pack(side="left")
        self._help(self.overnight_button, "Load the long-running campaign preset and start GPU screening plus replay.")
        self.particle_campaign_button = ttk.Button(options, text="Particle persistence", command=self.start_particle_campaign)
        self.particle_campaign_button.pack(side="left", padx=8)
        self._help(self.particle_campaign_button, "Run 96 particle-hybrid persistence conditions: 8 seeds, 3 body yields, and 4 low-decay values for 200,000 steps.")
        self.stop_button = ttk.Button(options, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left")
        self._help(self.stop_button, "Request a safe stop after the current worker results finish reporting.")
        export_button = ttk.Button(options, text="Export results", command=self.export)
        export_button.pack(side="left", padx=8)
        self._help(export_button, "Save the currently displayed results or GPU report as a JSON file.")
        ttk.Label(self, textvariable=self.help_text, relief="groove", anchor="w", justify="left", wraplength=1040).pack(fill="x", padx=10, pady=(4, 6))
        self.status = tk.StringVar(value="Ready")
        ttk.Label(options, textvariable=self.status).pack(side="right")
        self.progress = ttk.Progressbar(self, mode="determinate", maximum=1, value=0)
        self.progress.pack(fill="x", padx=10, pady=(0, 6))

        self.workspace = ttk.Notebook(self)
        self.workspace.pack(fill="both", expand=True, padx=10, pady=(8, 10))

        runs_frame = ttk.Frame(self.workspace)
        self.workspace.add(runs_frame, text="Runs")
        columns = ("run", "condition", "seed", "state", "live", "births", "viable")
        self.run_table = ttk.Treeview(runs_frame, columns=columns, show="headings", selectmode="extended")
        headings = {"run": "Run", "condition": "Condition", "seed": "Seed", "state": "State", "live": "Live", "births": "Births", "viable": "Viable"}
        for column in columns:
            self.run_table.heading(column, text=headings[column])
            self.run_table.column(column, width=240 if column == "condition" else 75, anchor="center")
        self.run_table.column("state", width=110)
        self.run_table.pack(fill="both", expand=True)
        self.run_table.bind("<<TreeviewSelect>>", self._on_run_selection)
        self.run_table.bind("<Double-1>", lambda _event: self.focus_selected())

        visual_frame = ttk.Frame(self.workspace)
        self.visual_frame = visual_frame
        self.workspace.add(visual_frame, text="Visual explorer")
        visual_tools = ttk.Frame(visual_frame)
        visual_tools.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(6, 2))
        ttk.Button(visual_tools, text="All visuals", command=self.show_all_visuals).pack(side="left")
        ttk.Button(visual_tools, text="Focus selected", command=self.focus_selected).pack(side="left", padx=6)
        ttk.Button(visual_tools, text="Compare selected", command=self.compare_selected).pack(side="left")
        ttk.Label(visual_tools, text="Select one run to focus or 2-4 runs to compare.").pack(side="left", padx=10)
        self.view_status = tk.StringVar(value="No runs yet")
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
        snapshot_dir = Path(__file__).with_name("Results") / "gui-snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
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
        self.total_jobs = len(jobs)
        self.completed_jobs = 0
        self.view_status.set(f"{len(jobs)} simulations loaded • waiting for first frames")
        self.progress.configure(maximum=self.total_jobs, value=0)
        self.start_button.configure(state="disabled")
        self.broad_button.configure(state="disabled")
        self.gpu_button.configure(state="disabled")
        self.overnight_button.configure(state="disabled")
        self.particle_campaign_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set(f"Running 0/{len(jobs)} — {workers} parallel workers — generating results")
        self.worker = threading.Thread(target=self._run, args=(jobs, workers), daemon=True)
        self.worker.start()
        if self.live_previews.get():
            self._refresh_live_previews()

    def _toggle_live_previews(self) -> None:
        self.live_warning.set("WARNING: live previews add rendering and file I/O; many runs at once can cause extreme lag." if self.live_previews.get() else "Live previews off - lowest overhead mode.")

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

    def _selected_paths(self) -> list[str]:
        return [self.row_paths[iid] for iid in self.run_table.selection() if iid in self.row_paths]

    def _on_run_selection(self, _event=None) -> None:
        selected = self._selected_paths()
        for path, card in self.live_cards.items():
            card["card"].configure(relief="sunken" if path in selected else "ridge")

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
        self.gpu_screen_total = config_count * len(seeds)
        self.total_jobs = self.gpu_screen_total + replay_top * len(seeds)
        self.progress.configure(maximum=self.total_jobs, value=0)
        self.start_button.configure(state="disabled"); self.broad_button.configure(state="disabled")
        self.gpu_button.configure(state="disabled"); self.overnight_button.configure(state="disabled"); self.particle_campaign_button.configure(state="disabled"); self.stop_button.configure(state="normal")
        self.status.set(f"Preparing {self.gpu_screen_total} GPU screens")
        configs = latin_hypercube(config_count, seed=7)
        output = Path(__file__).with_name("Results") / "gpu-snapshots"
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
        output = Path(__file__).with_name("Results") / "gpu-particle-snapshots"
        output.mkdir(parents=True, exist_ok=True)
        for index, job in enumerate(jobs, 1):
            snapshot = output / f"particle-gpu-{index:04d}.ppm"
            snapshot.unlink(missing_ok=True)
            job["snapshot_path"] = str(snapshot)
            self._add_run_row(str(snapshot), index, job["label"], job["seed"])
        self.stop_event.clear()
        self.total_jobs = len(jobs)
        self.progress.configure(maximum=self.total_jobs, value=0)
        self.start_button.configure(state="disabled"); self.broad_button.configure(state="disabled")
        self.gpu_button.configure(state="disabled"); self.overnight_button.configure(state="disabled")
        self.particle_campaign_button.configure(state="disabled"); self.stop_button.configure(state="normal")
        self.status.set(f"GPU particle campaign: {len(jobs)} worlds in batches of {batch_size}")
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
        self.after(0, lambda: (self.progress.configure(value=done), self.status.set(f"{message}: {done}/{total}")))

    def add_gpu_particle_report(self, report: dict) -> None:
        self.particle_gpu_report = report
        report_path = Path(__file__).with_name("Results") / "gui-particle-gpu-latest.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        self.results = report["results"]
        for completed, result in enumerate(self.results, 1):
            self.add_result(result, completed, self.total_jobs)
        self.finished(len(self.results), self.total_jobs)

    def gpu_particle_failed(self, error: str) -> None:
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
                               self.status.set(f"{message}: {done}/{total}")))

    def add_gpu_report(self, report: dict) -> None:
        self.gpu_report = report
        report_path = Path(__file__).with_name("Results") / "gui-gpu-latest.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
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
        self.status.set(f"Results generated: {completed}/{total} — {total - completed} remaining")

    def finished(self, completed: int, total: int) -> None:
        self.start_button.configure(state="normal")
        self.broad_button.configure(state="normal")
        self.gpu_button.configure(state="normal")
        self.overnight_button.configure(state="normal")
        self.particle_campaign_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.progress.configure(value=completed)
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
