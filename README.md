# Morrow

Morrow is a small, inspectable artificial-life world inspired by Lenia, Flow-Lenia, Avida, and artificial chemistry research.

Version 0.1 implements only the physical substrate:

- body matter moves through a local affinity field;
- resource is converted to body matter and waste;
- body matter decays into waste;
- all three fields conserve total mass under periodic boundaries;
- frames are written as portable PPM images with waste in red, body in green, and resource in blue.

It deliberately does **not** yet claim to contain organisms, genomes, reproduction, or evolution. Those layers follow only after the conservation and behavior of the substrate are verified.

## Run

```powershell
python -m pip install -r requirements.txt
python morrow.py --steps 500 --every 100
```

The run prints mass drift and writes frames to `output/`. Most image viewers can open PPM files; they can also be converted later if needed.

## Check

```powershell
python -m unittest -v
```

## Next milestone

Detect and track localized persistent structures, then test whether their persistence depends on resource conversion rather than a globally stable field pattern.
