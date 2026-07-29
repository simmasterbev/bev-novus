# Bev Novus - Design 1.0

> Status: historical design specification. It records an aspirational architecture and must not be read as proof that every listed mechanism exists. Compare it with [PROJECT_BRIEF.md](PROJECT_BRIEF.md) before treating a section as implemented.

## Working name

**Bev Novus** - a continuous spatial world in which organized matter can maintain itself, move, divide, mutate, and alter the conditions available to future organisms.

## Design goal

Bev Novus is not intended to imitate Earth biology directly. Its first goal is narrower and testable:

> Can a continuous local world produce bounded, persistent entities whose inherited differences affect survival and reproduction through resource-coupled spatial interactions?

Open-ended evolution is a later test, not an assumption.

## The architectural stack

```text
Layer 0  continuous spatial field and local update rule
Layer 1  conserved matter, energy/resource flow, decay, waste
Layer 2  localized organism parameters and dynamic boundaries
Layer 3  self-maintenance, motion, repair, division
Layer 4  inherited descriptions and mutation
Layer 5  competition, cooperation, niches, and ecological succession
Layer 6  lineage/evolvability/open-endedness measurement
```

The first implementation should begin with Layers 0-2 and add the others incrementally.

## World state

At each location `x`, the world stores:

```text
A[x, c]       matter concentration for channel c
E[x]          usable environmental energy/resource
W[x]          waste or inhibitory by-products
P[x]          localized rule/genome parameters carried by matter
```

The first version can use two matter channels:

```text
body matter       structural mass that forms organisms
resource matter   food or usable environmental substrate
```

Later versions can add pigment, signaling, waste, reproductive seeds, and multiple chemical types.

## Local physics

The initial update should be Flow-Lenia-like:

1. Compute a local affinity map from convolution kernels and growth functions.
2. Convert affinity gradients into matter flow.
3. Add diffusion to prevent singular concentration spikes.
4. Transport matter using conservative reintegration.
5. Apply local energy/resource conversion and waste production.
6. Apply decay and environmental replenishment.

Conceptually:

```text
affinity = local_kernel(A, P)
flow     = attraction_to_affinity + diffusion
A_next   = conservative_transport(A, flow)
(A_next, W_next, E_next) = local_metabolism(A_next, W, E, P)
```

The important constraint is conservation. Matter should move, transform, or leave through an explicitly modeled sink; it should not silently appear because a pattern needs it.

## Organisms

An organism is initially an automatically detected localized region, not a hard-coded object. A candidate entity must satisfy:

- bounded spatial support;
- minimum mass;
- persistence over a time window;
- coherent ancestry through transport;
- a localized parameter/genome field;
- measurable interaction with matter or energy.

The detector should be treated as an instrument, not as the source of life. We should store the detector’s decisions and test how robust results are to threshold changes.

### Proposed organism identity record

```text
organism_id
parent_id
birth_time
death_time
mass_history
centroid_history
parameter_history
resource_intake
waste_output
neighbors and interactions
division events
```

## Localized genotype

Each organism carries a small parameter vector rather than a full symbolic genome in Version 0.1:

```text
P = [kernel weights, growth center, growth width,
     diffusion tendency, attraction tendency,
     decay resistance, division threshold]
```

The parameter vector moves with matter during transport. When matter with different parameters meets, parameters are mixed or sampled according to local mass. This produces a simple genotype-like field without immediately introducing a separate interpreter.

Version 0.2 can replace or supplement this vector with a symbolic hereditary description:

```text
genome -> developmental parameters -> local dynamics -> phenotype
genome -> copied into offspring
```

That later version should explicitly separate copying from interpretation in the von Neumann sense.

## Metabolism and resource coupling

An organism gains usable matter by transforming local resource into body matter. A minimal reaction is:

```text
resource + energy -> body matter + waste
```

The conversion rate depends on local affinity and organism parameters. Body matter decays unless continuously maintained. This means persistence is not free.

Initial resource models:

1. uniform replenishment - debugging baseline;
2. static spatial patches - tests niche differentiation;
3. moving or pulsed resource sources - tests behavior and adaptation;
4. organism-produced resources or toxins - tests niche construction.

## Movement and behavior

Movement should not be scripted as an agent action. It should emerge from asymmetric local flow. A genotype can alter how strongly matter moves toward affinity gradients versus diffuses away from concentration peaks.

Candidate behavioral traits:

- directed movement;
- rotation or orbiting;
- chemotaxis toward resource;
- avoidance of waste or competitors;
- temporary aggregation;
- division near favorable resource conditions.

The first movement test is not “does it look animal-like?” It is whether movement changes resource intake and persistence.

## Reproduction

Version 0.1 uses a controlled bridge mechanism:

```text
if organism mass > division threshold
and local resource conditions are favorable:
    split a localized region or emit a seed
    copy the parent parameter field
    apply a small mutation to the offspring field
    separate parent and offspring if possible
```

This is initially an experimental scaffold, not yet fully endogenous reproduction. The scaffold lets us test viability and selection while we develop a more intrinsic division process.

The transition to stronger reproduction requires the organism’s own local dynamics to create the division event, rather than an external observer checking a mass threshold.

## Death and recycling

Death occurs when:

- mass falls below a viability threshold;
- the organism loses coherent localization;
- decay outruns maintenance;
- it is displaced or consumed;
- its internal parameters become nonviable.

Dead matter should become resource, waste, or inert substrate according to explicit rules. This prevents the world from filling with invisible or permanently blocking corpses.

## Ecology

The first ecological interactions should be simple:

```text
competition       organisms consume the same limited resource
interference      waste inhibits nearby organisms
coexistence       organisms use different resource conditions
facilitation      one organism changes the environment beneficially
predation/merger  one organism absorbs another’s matter
```

We should vary diffusion and resource transport because spatial structure can produce coexistence that disappears in a well-mixed world.

## Evolutionary loop

The world itself should determine reproductive success through the following chain:

```text
genotype
   -> local dynamics and development
   -> resource intake / repair / movement / division
   -> survival and offspring production
   -> inherited variation
   -> lineage competition and ecological change
```

No global fitness score should be needed for the primary experiment. External scores may be used for diagnostic experiments and search, but must be labeled as external intervention.

## Measurements

### Individual-level

- persistence time;
- mass balance;
- resource intake and waste output;
- boundary stability;
- repair after perturbation;
- movement and behavioral state;
- division success;
- parent-offspring similarity.

### Population-level

- population size and turnover;
- genotype and phenotype diversity;
- lineage depth and branching;
- extinction and replacement;
- coexistence duration;
- spatial patch structure;
- interaction network;
- resource and waste gradients.

### Open-endedness-level

- new viable phenotypes over time;
- new ecological interactions;
- change in genotype-phenotype map;
- complexity and modularity of hereditary descriptions;
- emergence of new niches;
- evolutionary activity after initial transients;
- whether innovation continues after the original search space is saturated.

## Falsification tests

Morrow should fail its own life-like claims if any of the following occur:

1. Organisms persist without consuming or transforming resources.
2. Reproduction is entirely performed by an external evaluator.
3. Mutations are inherited but nearly all are lethal or phenotypically neutral forever.
4. One expansion strategy eliminates all diversity under every environment.
5. Novelty is only visual noise or parameter drift without viable lineage continuity.
6. Organism boundaries disappear when detection thresholds change slightly.
7. Resource flow, ecology, or spatial structure has no effect on evolutionary outcomes.

## Build sequence

### Milestone 1 - physical substrate

Implement continuous field dynamics, conservative transport, resource, waste, and decay. Verify mass accounting numerically.

### Milestone 2 - pattern census

Detect and track localized persistent structures. Reproduce creation, persistence, and destruction statistics.

### Milestone 3 - resource-coupled bodies

Add metabolism and perturbation tests. Measure whether persistence requires internal maintenance.

### Milestone 4 - reproduction scaffold

Add localized parameter inheritance and mutation. Measure parent-offspring resemblance and viability.

### Milestone 5 - intrinsic reproduction

Replace the external division scaffold with an emergent division or seed-emission mechanism.

### Milestone 6 - ecology

Add spatially varying resources, waste, interactions, and environmental change. Test coexistence and succession.

### Milestone 7 - evolvability

Allow genome structure, mutation rate, duplication, and developmental mapping to vary. Test whether evolvability itself evolves.

## Initial implementation choice

Use Python and NumPy for the first transparent prototype. Move to JAX only when the world’s state transitions and measurements are stable enough to justify large-scale experiments. The first success criterion is inspectability, not speed.
