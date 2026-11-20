+++
title = "The JuliaFMI ecosystem"
acronym = "JuliaFMI"
funding = "internal"                     # public | internal
start = 2021
summary = "Open-source Julia packages for the Functional Mock-up Interface: load, simulate, differentiate and export FMUs, and combine them with machine learning."
members = ["tobias-thummerer", "josef-jouaux", "julian-trommer", "valentin-hoepfner"]
website = "https://github.com/JuliaFMI"
weight = 4
+++

The [Functional Mock-up Interface (FMI)](https://fmi-standard.org/) is the open standard for
exchanging simulation models between tools: a model is exported as a *Functional Mock-up Unit*
(FMU) and can then be simulated in any tool that supports FMI. The
[JuliaFMI](https://github.com/JuliaFMI) packages make FMUs a first-class part of the Julia
programming language, and with it of Julia's ecosystem for differential equations and machine learning.

## FMI.jl

[FMI.jl](https://github.com/JuliaFMI/FMI.jl) is the main package: it loads or creates,
parameterizes, differentiates, linearizes, simulates and plots FMUs directly in Julia. It supports
the full FMI 2.0.3 and FMI 3.0 command sets, co-simulation and model-exchange FMUs, and event handling
for discontinuous models. Simulating an FMU takes a few lines:

```julia
using FMI, Plots
fmu = loadFMU("model.fmu")
simData = simulate(fmu, (0.0, 10.0); recordValues=["mass.s"])
plot(simData)
```

## The other packages

- [FMIImport.jl](https://github.com/JuliaFMI/FMIImport.jl) – importing FMUs, the foundation of FMI.jl and FMIFlux.jl
- [FMIExport.jl](https://github.com/JuliaFMI/FMIExport.jl) – exporting models written in Julia as FMUs
- [FMIFlux.jl](https://github.com/JuliaFMI/FMIFlux.jl) – NeuralFMUs: FMUs combined with neural networks and trained end-to-end (hybrid modeling)
- [FMISensitivity.jl](https://github.com/JuliaFMI/FMISensitivity.jl) – gradients and sensitivities through FMUs with automatic differentiation
- [FMIZoo.jl](https://github.com/JuliaFMI/FMIZoo.jl) – ready-to-use FMUs for testing and examples
- [FMIBase.jl](https://github.com/JuliaFMI/FMIBase.jl), [FMICore.jl](https://github.com/JuliaFMI/FMICore.jl) and [FMIBuild.jl](https://github.com/JuliaFMI/FMIBuild.jl) – common foundations and build tooling

Documentation, examples and tutorials: [juliafmi.github.io/FMI.jl](https://juliafmi.github.io/FMI.jl/dev/)
