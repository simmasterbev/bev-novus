"""Minimal local GUI for parallel Bev Novus parameter experiments."""

from __future__ import annotations

import json
import threading
import tkinter as tk
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from broad_sweep import latin_hypercube
from experiments import run_condition, run_particle_condition
from gpu_sweep import screen_and_replay
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
        self.images: list[tk.PhotoImage] = []
        self.gpu_report: dict | None = None
        self.gpu_screen_total = 0
        self.fields: dict[str, tk.StringVar] = {}
        self.engine = tk.StringVar(value="Field")
        self.help_text = tk.StringVar(value="Select or hover over a control to see what it changes.")
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

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(8, 10))
        table_frame = ttk.Frame(notebook)
        notebook.add(table_frame, text="Results")
        columns = ("label", "seed", "live", "births", "viable", "compactness", "boundary", "diversity", "groups")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", height=21)
        headings = {"label": "Condition", "seed": "Seed", "live": "Live", "births": "Births", "viable": "Viable",
                    "compactness": "Compact", "boundary": "Boundary", "diversity": "Trait diversity", "groups": "Groups"}
        for column in columns:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=110 if column == "label" else 85, anchor="center")
        self.table.pack(fill="both", expand=True)

        visual_frame = ttk.Frame(notebook)
        notebook.add(visual_frame, text="Visualizations")
        visual_frame.rowconfigure(0, weight=1)
        visual_frame.columnconfigure(0, weight=1)
        self.visual_canvas = tk.Canvas(visual_frame, background="black", highlightthickness=0)
        scrollbar = ttk.Scrollbar(visual_frame, orient="vertical", command=self.visual_canvas.yview)
        self.visual_canvas.configure(yscrollcommand=scrollbar.set)
        self.visual_canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.visual_inner = ttk.Frame(self.visual_canvas)
        self.visual_window = self.visual_canvas.create_window((8, 8), window=self.visual_inner, anchor="nw")
        self.visual_inner.bind("<Configure>", lambda _: self.visual_canvas.configure(scrollregion=self.visual_canvas.bbox("all")))

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
        self.table.delete(*self.table.get_children())
        for child in self.visual_inner.winfo_children():
            child.destroy()
        self.images.clear()
        snapshot_dir = Path(__file__).with_name("Results") / "gui-snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        for index, job in enumerate(jobs, 1):
            job["snapshot_path"] = str(snapshot_dir / f"run-{index:04d}.ppm")
        self.stop_event.clear()
        self.total_jobs = len(jobs)
        self.completed_jobs = 0
        self.progress.configure(maximum=self.total_jobs, value=0)
        self.start_button.configure(state="disabled")
        self.broad_button.configure(state="disabled")
        self.gpu_button.configure(state="disabled")
        self.overnight_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set(f"Running 0/{len(jobs)} — {workers} parallel workers — generating results")
        self.worker = threading.Thread(target=self._run, args=(jobs, workers), daemon=True)
        self.worker.start()

    def start_gpu(self) -> None:
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
        self.results.clear(); self.gpu_report = None; self.images.clear()
        self.table.delete(*self.table.get_children())
        for child in self.visual_inner.winfo_children():
            child.destroy()
        self.stop_event.clear()
        self.gpu_screen_total = config_count * len(seeds)
        self.total_jobs = self.gpu_screen_total + replay_top * len(seeds)
        self.progress.configure(maximum=self.total_jobs, value=0)
        self.start_button.configure(state="disabled"); self.broad_button.configure(state="disabled")
        self.gpu_button.configure(state="disabled"); self.overnight_button.configure(state="disabled"); self.stop_button.configure(state="normal")
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
                result["_snapshot_path"] = job["snapshot_path"]
                self.results.append(result)
                completed += 1
                self.after(0, self.add_result, result, completed, len(jobs))
        self.after(0, self.finished, completed, len(jobs))

    def add_result(self, result: dict, completed: int, total: int) -> None:
        values = (result["label"], result["seed"], result["live"], result["births"], result["viable"],
                  f'{result["compactness"]:.3f}', f'{result["boundary_ratio"]:.3f}',
                  f'{result["trait_diversity"]:.3g}', result["groups"])
        self.table.insert("", "end", values=values)
        snapshot = result.get("_snapshot_path")
        if snapshot and Path(snapshot).exists():
            image = tk.PhotoImage(file=snapshot).zoom(2, 2)
            self.images.append(image)
            card = ttk.Frame(self.visual_inner, padding=6, relief="ridge")
            card.grid(row=(len(self.images) - 1) // 4, column=(len(self.images) - 1) % 4, padx=6, pady=6, sticky="n")
            ttk.Label(card, image=image).pack()
            ttk.Label(card, text=f'{result["label"]}\nseed {result["seed"]} — live {result["live"]}').pack()
        self.progress.configure(value=completed)
        self.status.set(f"Results generated: {completed}/{total} — {total - completed} remaining")

    def finished(self, completed: int, total: int) -> None:
        self.start_button.configure(state="normal")
        self.broad_button.configure(state="normal")
        self.gpu_button.configure(state="normal")
        self.overnight_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.progress.configure(value=completed)
        self.status.set("Stopped" if self.stop_event.is_set() else f"Finished — {completed}/{total} results generated")

    def stop(self) -> None:
        self.stop_event.set()
        self.status.set("Stopping…")

    def export(self) -> None:
        if not self.results:
            messagebox.showinfo("No results", "Run an experiment grid first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=(("JSON", "*.json"), ("All files", "*.*")))
        if path:
            exportable = self.gpu_report or [{key: value for key, value in result.items() if not key.startswith("_")} for result in self.results]
            Path(path).write_text(json.dumps(exportable, indent=2), encoding="utf-8")
            self.status.set(f"Saved {Path(path).name}")


if __name__ == "__main__":
    ExperimentApp().mainloop()
