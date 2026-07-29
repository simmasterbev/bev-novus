# Artificial Life Reading Notes

> Status: source reading record. The design inferences here are deliberately broader than the current implementation; use [PROJECT_BRIEF.md](PROJECT_BRIEF.md) for the current build and [ROADMAP.md](ROADMAP.md) for the active evidence gates.

## Scope and reading status

These notes separate what each source *actually establishes* from the design inferences we may later make from it. “Full text” means the paper or supplied excerpt was read; “abstract/repository” means the note is intentionally limited to the abstract, project documentation, or accessible excerpts.

| Source | Status | Central question |
| --- | --- | --- |
| Langton, *Artificial Life* | Full supplied PDF | What should ALife study and how should it be built? |
| Chan, *Lenia* | Paper and interactive project | What continuous CA rules support organism-like patterns? |
| Kumar et al., *ASAL* | Full arXiv HTML | Can foundation-model embeddings automate discovery of ALife? |
| von Neumann, lectures 4-5 | Full supplied excerpt | What architecture makes self-reproduction and evolution possible? |
| Stepney, *Origins of Virtual ALife* | Review text/abstract | What would count as virtual life rather than a simulation with life-like features? |
| Plantec et al., *Flow-Lenia* (2022) | Full PDF | How can Lenia host localized, resource-constrained organisms? |
| Plantec et al., *Flow-Lenia* (2025) | Abstract | What evolutionary dynamics become possible in mass-conservative Lenia? |
| Chan, *Large-Scale Evolution of Lenia* | Full PDF | Can localized genetic information and selection produce continued Lenia evolution? |
| Mathis et al., *Leniabreeder* | Full arXiv HTML | Can quality-diversity search build a useful Lenia atlas? |
| Ofria & Wilke, *Avida* | Accessible project/paper excerpts | How can executable digital organisms support controlled evolutionary experiments? |
| Beer, *Origin of Autopoiesis* | Full PDF | Can the onset of persistent individuals be analyzed statistically? |
| Hintze, *Open-Endedness for the Sake of Open-Endedness* | Paper/abstract excerpts | Why are prevailing OEE definitions too weak? |
| Dolson et al., *MODES Toolbox* | Abstract/tool documentation | How can OEE-relevant dynamics be measured? |
| Huizinga, Stanley & Clune, *Canalization and Evolvability* | Full PDF | How can evolution acquire the ability to make useful future variation? |

## 1. Christopher G. Langton - *Artificial Life*

Source: provided `F:/Downloads/Langton_al.pdf`.

### Claim and theory

Langton frames artificial life as the study of **life-as-it-could-be**, not merely the imitation of terrestrial organisms. The methodological shift is from asking “how does this biological part work?” to constructing alternative media in which life-like organization might occur.

His core theory is that life is best understood as a hierarchy of **nonlinear, distributed, locally interacting processes**. A system-level behavior may be real and stable even when no component contains a representation of that behavior. This is the reason to favor bottom-up construction over an externally scripted global controller.

### Structural ideas

- **GTYPE**: the generative machinery - local rules, components, encodings, and update relations.
- **PTYPE**: the realized phenotype - the organized behavior that appears when GTYPE runs in an environment.
- **Emergence gap**: GTYPE constrains PTYPE but does not, in general, make PTYPE easy to predict. The gap is where design search and evolution matter.
- **Evolution as a constructor/search process**: replication plus heritable variation plus differential persistence can discover organized forms that a designer cannot directly specify.

### Examples used as a research program

Cellular automata, L-systems, flocking/Boids, genetic algorithms, coevolution, Tierra, behavior-based robotics, and wet artificial chemistry are not one unified model. They are alternative substrates for testing the same premise: local interactions can support higher-level organization.

### Limits and implication

Langton gives a founding methodology rather than a sufficient checklist for life. Local rules and emergence can generate striking patterns without yielding individuals, heredity, ecology, or open-ended evolution. In a combined system, Langton supplies the **construction philosophy**, while later work must supply the missing mechanisms.

## 2. Bert Wang-Chak Chan - *Lenia: Biology of Artificial Life*

Sources: [paper](https://arxiv.org/abs/1812.05433), [interactive implementation](https://chakazul.github.io/Lenia/JavaScript/Lenia.html).

### Model

Lenia is a continuous cellular automaton. The world is a scalar field `A(x)` with values in `[0, 1]`; an update evaluates a neighborhood potential and applies a smooth growth response:

```text
U(x) = (K * A)(x)                 neighborhood potential
A(x, t + dt) = clip(A + dt G(U), 0, 1)
```

`K` is a radial convolution kernel and `G` is commonly a bell-shaped growth function. In the browser controls, radius `R`, temporal step `T`, kernel-ring weights `beta`, and growth center/width (`mu`, `sigma`) parameterize this local physics.

### Algorithmic structure

1. Sample the current field around every location through convolution.
2. Convert the local potential to growth/decay via `G`.
3. Integrate all sites simultaneously and clip the field into the valid range.
4. Repeat; moving, rotating, oscillating, or stationary coherent patterns may emerge.

The “organism” is not a stored object. It is a self-maintaining trajectory of the whole field under the rule.

### Findings

The original project catalogued hundreds of species-like patterns in multiple families. Lenia patterns can be resilient to perturbation, motile, and sometimes adaptive in a loose dynamical sense. Extended Lenia adds multiple channels/kernels and higher-dimensional variants, making the update closer to a recurrent convolutional network and enabling phenomena such as emission, ingestion, division, and differentiation.

### Limits and implication

Ordinary Lenia normally uses a **single global rule**, carries no explicit heritable genome, and has no intrinsic resource economy. Its rich morphology is therefore a strong substrate for bodies and dynamics, not yet a complete evolutionary world. A later design needs to localize parameters, create a genotype-to-phenotype relation, and make persistence/reproduction consequential.

## 3. Kumar et al. - *Automating the Search for Artificial Life with Foundation Models* (ASAL)

Source: [arXiv paper](https://arxiv.org/abs/2412.17799).

### Claim

ASAL treats an ALife simulator as a parameterized image generator and uses pretrained vision or vision-language embeddings to search it. Its contribution is not a new life substrate; it is an external **discovery layer** for scanning large spaces of rules and initial conditions.

### System pipeline

```text
candidate parameters theta
       -> initialize / simulate / render frames
       -> CLIP or DINO embedding
       -> target, novelty, or diversity score
       -> evolutionary optimizer or gradient update
       -> new candidate parameters
```

The candidate is represented as `theta = {Init_theta, Step_theta, Render_theta}`. The approach is applied to Boids, Particle Life, life-like CA, Lenia, and neural CA.

### Search modes and algorithms

- **Targeted search**: maximize similarity between rendered frames and a text prompt or target image. The study uses Sep-CMA-ES for non-differentiable Lenia, Boids, and Particle Life, and Adam with backpropagation through time for temporal neural CA.
- **Open-endedness proxy**: score a frame by novelty relative to a history of foundation-model embeddings. For the small life-like CA rule space, it exhaustively evaluates all 262,144 rules.
- **Illumination**: maintain a diverse archive, rather than one optimum. Its genetic algorithm keeps a population (reported as 8,192), mutates candidates, and removes the least novel to fill out a behavioral atlas.

### Findings and limits

The paper finds visually novel Lenia patterns, Boids configurations, and diverse CA behaviors that would be difficult to locate manually. But an embedding score is a **proxy for perceived novelty or prompt similarity**, not evidence that a pattern has self-maintenance, heredity, ecological function, or adaptive significance. ASAL should therefore sit outside the world as a scientist/designer tool, not be confused with the endogenous evolutionary process.

## 4. John von Neumann - *Theory of Self-Reproducing Automata*, lectures 4-5

Source: [supplied excerpt](https://cba.mit.edu/events/03.11.ASE/docs/VonNeumann.pdf), book pages 64-87.

### Core architecture

Von Neumann separates a self-reproducing machine into functions rather than treating copying as a single opaque operation:

```text
description phi(X)
     | interpreted                         | copied uninterpreted
     v                                     v
universal constructor A: phi(X) -> X    copier B: phi(X) -> phi(X)'
     \                                   /
      -------- controller C -------------
                    |
       construct offspring, attach copied description, release it
```

If `X = A + B + C`, then a description of `X` can be copied and interpreted to build another `X` carrying its own description. The same symbolic object serves two roles: an instruction when read by `A`, and passive data when copied by `B`.

### Why this is deeper than “make a copy”

The interpret/copy distinction prevents the usual regress: the description is not required to contain a direct physical miniature of the machine. It is a code that can be copied blindly, then interpreted by a pre-existing constructor. This anticipates the logical role of a genetic description.

### Hierarchy and evolution

Von Neumann argues that highly complicated automata need architectural hierarchy and fault-handling rather than one fragile monolith. The excerpt distinguishes continuing operation, detection, bypass, localization, and reorganization of failures.

For evolution, he adds an optional inherited component `D`: `X = A + B + C + D`. Random alterations to the core construction/copy/control machinery are often fatal, but variation in a separable inherited part can change phenotype while preserving the reproduction architecture. This is the opening for a viable mutation neighborhood.

### Limit and implication

The construction is a logical design, not an ecological world. It explains what inheritance architecture must accomplish, but does not create resource competition or guarantee innovation. In a field-based ALife system, “constructor” and “description” might be distributed rather than spatially separate machinery; the two information roles must nevertheless remain distinct.

## 5. Susan Stepney - *Towards Origins of Virtual Artificial Life: An Overview*

Source: [PMC review](https://pmc.ncbi.nlm.nih.gov/articles/PMC12489504/).

### Theory of what is missing

Stepney organizes the question in three layers:

```text
requirements -> generic design -> particular implementation
```

Her strongest proposed requirements for full life are:

1. **Autopoiesis** - a system produces and maintains its own organization and boundary.
2. **Agency** - an individual can act in ways grounded in its own continuing organization.
3. **Open-ended adaptation** - novelty continues through internal evolutionary/ecological dynamics.

The review stresses **endogenous** mechanism: the mechanisms that make an organism viable should arise and operate inside the modeled world, not be supplied by an outside script that silently performs essential work.

### Systems view

Stepney distinguishes top-down and bottom-up approaches and chemical, mechanical, and computational media. These are not mutually exclusive. The central warning is compositional: successful demonstrations of metabolism, replication, movement, or selection may rely on incompatible substrate assumptions, so combining their labels does not automatically combine their mechanisms.

### Limits and implication

The review concludes that virtual ALife has compelling partial systems but no settled full realization meeting all requirements. Virtual worlds are unusually observable, repeatable, and manipulable, but hard-coded shortcuts, poor embodiment, and restricted environments may undermine claims of autonomy. Stepney is the main **evaluation framework** for the combined project.

## 6. Plantec et al. - *Flow-Lenia* (2022)

Source: [arXiv paper](https://arxiv.org/abs/2212.07906).

### Problem addressed

Conventional Lenia organisms are found under globally fixed parameters. Distinct creatures cannot normally carry different local rules in the same world, and unconstrained mass makes interactions less biologically meaningful.

### Mechanism

Flow-Lenia modifies continuous-CA dynamics to introduce:

- **mass conservation**, making matter a limited quantity that can move and be redistributed; and
- **parameter localization**, embedding model parameters locally so organisms can carry different rule settings or genetic-like values.

This changes the interpretation of a creature from “a pattern under one universal global rule” to “a localized dynamical organization with locally maintained parameters inside a shared physics.”

### Structural significance

Mass conservation makes contact, merger, competition, and transfer consequential. Localized parameters enable multispecies coexistence and a route to heritable, mutable organism-specific properties. The paper also identifies food maps, matter decay, digestion, and intrinsic selection as forward directions - evidence that the authors view the current system as a necessary substrate improvement rather than a complete evolutionary solution.

## 7. Plantec et al. - *Flow-Lenia: Emergent Evolutionary Dynamics in Mass-Conservative Cellular Automata* (2025)

Source: [arXiv abstract](https://arxiv.org/abs/2506.08569); [journal version](https://direct.mit.edu/artl/article/31/2/228/130572/Flow-Lenia-Emergent-Evolutionary-Dynamics-in-Mass).

### Read cautiously: abstract-level note

The follow-up reports mass-conservative continuous CA with locally embedded model parameters, focusing on analysis of resulting multispecies and evolutionary dynamics. Its central continuity with 2022 is important: localized parameters are treated as a prerequisite for a population of different organism-like systems to inhabit one world. Full methodological and result claims should be checked against the paper text before relying on them for quantitative design decisions.

## 8. Bert Wang-Chak Chan - *Large-Scale Evolution of Lenia* (2023)

Source: [arXiv paper](https://arxiv.org/abs/2304.05639).

### Objective

This is a concrete attempt to convert Lenia from a morphology playground into an evolutionary system. It uses JAX to scale experiments and emphasizes three conditions:

- implicit genetic operations through self-replication and differential existential success;
- localized genetic information; and
- a dynamic genotype-maintenance and phenotype-translation process.

### Lessons from the experiments

The experiments seek traits such as locomotion, repair/defense, attraction/repulsion, self-replication, differentiation, and swarming. A central negative result is as informative as the positive behaviors: without suitable penalties/constraints, mutation can cause the world to saturate or evolution to lose future room for change. High mutation may generate diversity yet destabilize organized lineages.

### Design inference

Variation must be both **expressible and survivable**. The paper proposes directions including more channels/kernels/dimensions, organism-level units of selection, sexual reproduction or gene duplication, differential reproductive/existential success, and food/energy constraints. These are a blueprint for connecting Lenia to von Neumann’s hereditary-description layer and Stepney’s ecological requirements.

## 9. Mathis et al. - *Leniabreeder* (2024)

Source: [arXiv paper](https://arxiv.org/abs/2406.04235), [full HTML](https://arxiv.org/html/2406.04235).

### Purpose

Leniabreeder is an automated catalogue builder, not a claim of autonomous evolution. It applies **quality-diversity (QD)** optimization to multi-channel Lenia to retain many different persistent outcomes.

### Algorithm

- A genotype includes the initial seed and rule parameters. The reported setup uses three channels, 15 kernels, and 45 mutable parameters.
- Candidates that evaporate, explode, or spread beyond a constraint are removed.
- **MAP-Elites** assigns solutions to hand-selected behavioral-descriptor niches and keeps the best per niche.
- **AURORA** learns descriptors from data: a VAE encodes center-of-mass-cropped observations into an 8D latent space; a trajectory statistic becomes a dynamic behavioral descriptor; niches are then redefined from the discovered phenotypes.
- The persistence/homeostasis proxy is negative temporal dispersion of the latent trajectory: a stable individual keeps a compact latent trajectory.

### Findings and limits

The search produces a growing atlas of diverse persistent forms and shows why learned behavioral descriptors can reveal categories humans did not predefine. Its limitation is explicit: stable latent embeddings are not a theory of life or OEE, and the VAE representation may not be invariant to irrelevant changes. This is best used as an **offline exploration/curation instrument**, complementary to ASAL.

## 10. Ofria & Wilke - *Avida: A Software Platform for Research in Computational Evolutionary Biology*

Sources: [paper](https://direct.mit.edu/artl/article/10/2/191/2455/Avida-A-Software-Platform-for-Research-in), [project material](https://avida.devosoft.org/).

### Substrate and organism

An Avida organism is an executable program on a virtual CPU, placed in a spatial population. Its genome is an instruction sequence. The same sequence is interpreted to execute behavior, including moving read/write heads and copying instructions into an offspring genome.

### Population mechanics

- Organisms reproduce by executing their own copy loop.
- Instruction-copy errors create heritable variation.
- CPU time, task rewards, and spatial placement make reproductive success conditional on the environment.
- Offspring placement can replace an occupant, producing direct population turnover.
- The experimenter can vary instruction sets, resource/task landscapes, mutation rates, and population geometry while logging complete lineages.

### Why it matters

Avida is a mature realization of a **von Neumann-like description/interpretation loop**: a genome is executed and copied, and copying errors become inherited mutations. It is ideal for controlled evolution experiments, but the digital CPU semantics and externally specified tasks are strong substrate assumptions. It demonstrates Darwinian evolution much more directly than ordinary Lenia, while providing much less embodied continuous morphology.

## 11. Randall D. Beer - *An Investigation into the Origin of Autopoiesis* (2020)

Source: [paper](https://direct.mit.edu/artl/article/26/1/5/93263/An-Investigation-into-the-Origin-of-Autopoiesis).

### Definition used

Beer takes autopoiesis in the Maturana-Varela sense:

- **self-production**: a network produces components whose interactions regenerate that same network; and
- **self-individuation**: the system constructs and maintains its own boundary as part of its operation.

Reproduction is deliberately not the starting criterion. The question is first whether an individual can persist as an organization.

### Toy world and method

Game of Life is treated as a physics from which an artificial chemistry is derived. A glider is a bounded, persistent spatiotemporal organization with 16 structural instantiations (two forms, two chiralities, four orientations). Beer examines glider origin, proliferation, and extinction in random 100 x 100 periodic GoL worlds.

The paper separates mean glider-density change into three operators:

```text
g(t) = persistence(t-1) + creation(t-1)
g(t) - g(t-1) = creation(t-1) - destruction(t-1)
```

It derives/estimates these from precursor basins - local configurations that will become or continue a glider - then uses combinatorics for early times and Monte Carlo at larger scales.

### Findings

From broad random initial densities, gliders rapidly rise to a peak near time 60, then mostly decline; narrow density regions retain long-term glider presence. The important contribution is not that GoL gliders are biological organisms. It is a disciplined way to measure the **creation, persistence, and destruction balance** behind the origin of candidate individuals.

### Limit and implication

A GoL glider does not have rich metabolism, heredity, or self-directed action. But this work gives the unified project a practical test: track an entity’s boundary and lineage, then account for the processes that regenerate, damage, or erase it instead of merely labeling persistent pictures as organisms.

## 12. Arend Hintze - *Open-Endedness for the Sake of Open-Endedness* (2019)

Source: [paper](https://direct.mit.edu/artl/article/25/2/198/2923/Open-Endedness-for-the-Sake-of-Open-Endedness).

### Argument

Hintze challenges definitions of open-ended evolution (OEE) that are so permissive a trivial system can satisfy them. “Can run indefinitely” and “sometimes produces novelty” are not enough. A useful definition must capture the biological target: continued generation of consequential complexity and diversity.

### Criteria landscape discussed

The paper reviews common desired properties: unbounded diversity, selection, continuing adaptive novelty, endogenous niches, nontrivial reproduction, innovations that create further opportunities, individual control over interactions, viable mutational pathways, and potential for unbounded phenotype size/complexity.

### Implication

OEE is an empirical claim requiring a battery of tests, not a score produced by a one-off visual search. The design target should be “continued production of new viable ways to live in the world,” and the evaluation must separately inspect novelty, complexity, ecological coupling, and lineage viability.

## 13. Dolson et al. - *The MODES Toolbox* (2019)

Sources: [paper](https://direct.mit.edu/artl/article/25/1/50/2915/The-MODES-Toolbox-Measurements-of-Open-Ended), [tool documentation](https://emilydolson.github.io/MODES-toolbox-paper/).

### Contribution

MODES makes OEE assessment operational by recording genealogy and evolutionary activity. It is instrumentation, not a definition of life.

### Measurement families

- **Change potential**: whether evolution continues to generate modifications.
- **Novelty potential**: whether new phenotypic/behavioral forms appear.
- **Complexity potential**: whether some complexity measure can increase.
- **Ecological potential**: whether the system develops changing ecological relations and niches.

The toolbox depends on a systematics manager that records parent-child relationships and a tracker that computes the metrics. It was applied to systems including NK landscapes and Avida.

### Implication

For a Lenia-based world, first define what counts as an organism, a genotype, a phenotype, a lineage, an interaction, and a niche. Only then can MODES-style metrics avoid measuring pixel noise or search-algorithm churn as evolutionary novelty.

## 14. Huizinga, Stanley & Clune - *The Emergence of Canalization and Evolvability in an Open-Ended, Interactive Evolutionary System* (2018)

Source: [arXiv paper](https://arxiv.org/abs/1704.05143).

### Key concepts

**Canalization** means that variation becomes biased along useful, coherent dimensions: some features are robust while other meaningful features can vary together. **Evolvability** is the evolved ability to produce useful heritable variation.

### Evidence from Picbreeder

The authors analyze Picbreeder, a goal-free interactive evolutionary image system. In lineages that produced many descendants, they find modular and hierarchical encoding structure and mutations that change meaningful image dimensions while preserving other organization. Examples include coordinated changes to paired structures rather than arbitrary pixel-level degradation.

### Design lesson

A fixed objective often selects a narrow optimum and can make exploratory change destructive. Divergent search, branching lineages, modular developmental encodings, and protected substructures can instead create a landscape in which future innovation is easier. This supplies a design requirement for the genotype-to-phenotype map: mutations need not all be safe, but a substantial neighborhood of mutations must remain viable and meaningfully variable.

## Cross-source architecture

The readings form a dependency hierarchy rather than a list of interchangeable ideas:

```text
Langton: local emergent construction philosophy
    |
    +-- Lenia / Flow-Lenia: world physics, bodies, local matter and parameters
    |       |
    |       +-- Beer: individual persistence and boundary accounting
    |
    +-- von Neumann / Avida: inherited description, interpretation, copying, mutation
    |       |
    |       +-- Chan: attempt to embed those evolutionary requirements in Lenia
    |
    +-- ecology / selection: resource dependence, interaction, differential success
            |
            +-- Hintze + MODES: criteria and instrumentation for OEE
            +-- Huizinga: conditions that preserve evolvability

ASAL and Leniabreeder sit outside this stack as discovery instruments:
they search and map the space; they do not themselves supply endogenous life.
```

### Minimum research questions for a combined system

1. What field quantity is conserved, transformed, or depleted, and how does an organism gain access to it?
2. What is the material boundary of an individual, and which internal processes regenerate that boundary?
3. Where is the hereditary description located, how is it copied, and how is it interpreted into phenotype?
4. Which mutations preserve a viable organism often enough for lineages to explore?
5. What makes reproduction and persistence differentially successful without an external fitness function doing the biological work?
6. Can niches and interactions change the future opportunity landscape?
7. Do lineage-aware measurements show continuing adaptive novelty rather than visual novelty, noise, or saturation?
