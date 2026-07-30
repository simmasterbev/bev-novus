"""Reusable field definitions and dynamics-rule parsing for the GUI."""

from __future__ import annotations


FIELD_SPECS = {
    "Core": [("Seeds", "1,2,3"), ("Steps", "200000"), ("Body yield", "0.30,0.40,0.50"),
             ("Decay", "0.02,0.03,0.04"), ("Particle decay", "0.0005,0.001,0.002"), ("Sample every", "1000")],
    "Performance": [("Workers", "3"), ("Broad configs", "256"), ("GPU screen steps", "20000"),
                    ("GPU batch", "64"), ("Replay top", "8")],
    "Adaptive": [("Adaptive generations", "1"), ("Adaptive configs", "24"), ("Adaptive elites", "6")],
    "Dynamics": [("Metabolism", "0.035"), ("Diffusion", "0.5"),
                 ("Waste inhibition", "0.1"), ("Recycle rate", "0.1"),
                 ("Seed interval", "20"), ("Source scale", "0.5"),
                 ("Steering", "5.0"), ("Seed fraction", "0.05"),
                 ("Mutation scale", "0.02"), ("Resource patches", "5"),
                 ("Body patches", "5"), ("Resource strength", "1.15"),
                 ("Body strength", "1.5"), ("Resource regrowth", "0.01"),
                 ("Resource capacity", "1.0"), ("Waste decay", "0.02"),
                 ("Waste diffusion", "0.02"), ("Dormancy threshold", "0.06"),
                 ("Dormancy cost", "0.15"), ("Complexity pressure", "0.65")],
}

EXPLANATIONS = {
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
    "Metabolism": "Resource intake rate used by standard field and particle jobs.",
    "Diffusion": "Resource and body-field transport strength used by the field engine.",
    "Waste inhibition": "How strongly local waste suppresses resource intake.",
    "Recycle rate": "Fraction of recyclable waste returned to the resource field.",
    "Seed interval": "Minimum interval between field-engine seed emissions.",
    "Source scale": "Spatial scale of resource-source patches in standard jobs.",
    "Steering": "Strength of field-body movement toward resource and away from waste.",
    "Seed fraction": "Fraction of body mass used when a field seed is emitted.",
    "Mutation scale": "Magnitude of inherited trait mutation in field births.",
    "Resource patches": "Number of spatial resource patches in standard worlds.",
    "Body patches": "Number of starting body patches or particle groups.",
    "Resource strength": "Initial strength of resource patches.",
    "Body strength": "Initial body mass or strength of starting patches.",
    "Resource regrowth": "Rate at which depleted resources regrow.",
    "Resource capacity": "Maximum local resource capacity.",
    "Waste decay": "Per-step decay rate for waste in standard field worlds.",
    "Waste diffusion": "Transport strength for waste in standard field worlds.",
    "Dormancy threshold": "Body-mass threshold below which dormancy cost applies.",
    "Dormancy cost": "Additional decay multiplier for dormant bodies.",
    "Complexity pressure": "Selection pressure favoring more complex field patterns.",
}

DYNAMIC_RULES = (
    ("Metabolism", "metabolism"), ("Diffusion", "diffusion"),
    ("Waste inhibition", "waste_inhibition"), ("Recycle rate", "recycle_rate"),
    ("Seed interval", "seed_interval"), ("Source scale", "source_scale"),
    ("Steering", "steering"), ("Seed fraction", "seed_fraction"),
    ("Mutation scale", "mutation_scale"), ("Resource patches", "resource_patches"),
    ("Body patches", "body_patches"), ("Resource strength", "resource_strength"),
    ("Body strength", "body_strength"), ("Resource regrowth", "resource_regrowth"),
    ("Resource capacity", "resource_capacity"), ("Waste decay", "waste_decay"),
    ("Waste diffusion", "waste_diffusion"), ("Dormancy threshold", "dormancy_threshold"),
    ("Dormancy cost", "dormancy_cost"), ("Complexity pressure", "complexity_pressure"),
)
INTEGER_RULES = {"Seed interval", "Resource patches", "Body patches"}


def _values(text: str, cast) -> list:
    values = [cast(part.strip()) for part in str(text).split(",") if part.strip()]
    if not values:
        raise ValueError("Enter at least one value.")
    return values


def dynamic_rules(fields: dict) -> dict:
    """Return one validated backend value for every configurable dynamics rule."""
    rules = {}
    for label, name in DYNAMIC_RULES:
        values = _values(fields[label].get(), int if label in INTEGER_RULES else float)
        if len(values) != 1:
            raise ValueError(f"{label} accepts one value; use Broad sweep for sampled ranges.")
        rules[name] = values[0]
    return rules
