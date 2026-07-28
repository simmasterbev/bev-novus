"""Minimal local GUI for parallel Bev Novus parameter experiments."""

from __future__ import annotations

import json
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from experiments import run_condition


def numbers(text: str, cast=float) -> list:
    values = [cast(part.strip()) for part in text.split(",") if part.strip()]
    if not values:
        raise ValueError("Enter at least one value.")
    return values


def run_one(job: dict):
    return run_condition(**job)


class ExperimentApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Bev Novus experiment runner")
        self.geometry("1080x680")
        self.results: list[dict] = []
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.fields: dict[str, tk.StringVar] = {}
        self._build()

    def _build(self) -> None:
        controls = ttk.LabelFrame(self, text="Experiment grid")
        controls.pack(fill="x", padx=10, pady=10)
        specs = [
            ("Seeds", "1,2,3"), ("Steps", "200000"),
            ("Body yield", "0.30,0.40,0.50"), ("Decay", "0.02,0.03,0.04"),
            ("Sample every", "1000"), ("Workers", "4"),
        ]
        for index, (label, default) in enumerate(specs):
            row, column = divmod(index, 3)
            ttk.Label(controls, text=label).grid(row=row * 2, column=column, sticky="w", padx=8, pady=(8, 0))
            variable = tk.StringVar(value=default)
            self.fields[label] = variable
            ttk.Entry(controls, textvariable=variable, width=22).grid(row=row * 2 + 1, column=column, sticky="ew", padx=8, pady=(0, 8))
        for column in range(3):
            controls.columnconfigure(column, weight=1)

        options = ttk.Frame(self)
        options.pack(fill="x", padx=10)
        self.reproduce = tk.BooleanVar(value=True)
        self.mutate = tk.BooleanVar(value=True)
        self.recycle = tk.BooleanVar(value=True)
        self.spatial = tk.BooleanVar(value=True)
        for label, variable in (("Seed emission", self.reproduce), ("Mutation", self.mutate),
                                ("Recycling", self.recycle), ("Spatial resources", self.spatial)):
            ttk.Checkbutton(options, text=label, variable=variable).pack(side="left", padx=(0, 14))
        self.start_button = ttk.Button(options, text="Run grid", command=self.start)
        self.start_button.pack(side="left", padx=8)
        self.stop_button = ttk.Button(options, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left")
        ttk.Button(options, text="Export results", command=self.export).pack(side="left", padx=8)
        self.status = tk.StringVar(value="Ready")
        ttk.Label(options, textvariable=self.status).pack(side="right")

        columns = ("label", "seed", "live", "births", "viable", "compactness", "boundary", "diversity", "groups")
        self.table = ttk.Treeview(self, columns=columns, show="headings", height=21)
        headings = {"label": "Condition", "seed": "Seed", "live": "Live", "births": "Births", "viable": "Viable",
                    "compactness": "Compact", "boundary": "Boundary", "diversity": "Trait diversity", "groups": "Groups"}
        for column in columns:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=110 if column == "label" else 85, anchor="center")
        self.table.pack(fill="both", expand=True, padx=10, pady=(8, 10))

    def jobs(self) -> list[dict]:
        seeds = numbers(self.fields["Seeds"].get(), int)
        steps = int(self.fields["Steps"].get())
        sample_every = int(self.fields["Sample every"].get())
        yields = numbers(self.fields["Body yield"])
        decays = numbers(self.fields["Decay"])
        if steps < 1 or sample_every < 1:
            raise ValueError("Steps and sample interval must be positive.")
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
                    })
        return jobs

    def start(self) -> None:
        try:
            jobs = self.jobs()
            workers = max(1, int(self.fields["Workers"].get()))
        except (TypeError, ValueError) as error:
            messagebox.showerror("Invalid setup", str(error))
            return
        self.results.clear()
        self.table.delete(*self.table.get_children())
        self.stop_event.clear()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set(f"Running 0/{len(jobs)}")
        self.worker = threading.Thread(target=self._run, args=(jobs, workers), daemon=True)
        self.worker.start()

    def _run(self, jobs: list[dict], workers: int) -> None:
        completed = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(run_one, job) for job in jobs]
            for future in as_completed(futures):
                if self.stop_event.is_set():
                    for pending in futures:
                        pending.cancel()
                    break
                result = asdict(future.result())
                self.results.append(result)
                completed += 1
                self.after(0, self.add_result, result, completed, len(jobs))
        self.after(0, self.finished, completed, len(jobs))

    def add_result(self, result: dict, completed: int, total: int) -> None:
        values = (result["label"], result["seed"], result["live"], result["births"], result["viable"],
                  f'{result["compactness"]:.3f}', f'{result["boundary_ratio"]:.3f}',
                  f'{result["trait_diversity"]:.3g}', result["groups"])
        self.table.insert("", "end", values=values)
        self.status.set(f"Running {completed}/{total}")

    def finished(self, completed: int, total: int) -> None:
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status.set("Stopped" if self.stop_event.is_set() else f"Finished {completed}/{total}")

    def stop(self) -> None:
        self.stop_event.set()
        self.status.set("Stopping…")

    def export(self) -> None:
        if not self.results:
            messagebox.showinfo("No results", "Run an experiment grid first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=(("JSON", "*.json"), ("All files", "*.*")))
        if path:
            Path(path).write_text(json.dumps(self.results, indent=2), encoding="utf-8")
            self.status.set(f"Saved {Path(path).name}")


if __name__ == "__main__":
    ExperimentApp().mainloop()
