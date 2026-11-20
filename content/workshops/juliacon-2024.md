+++
title = "Scientific Machine Learning using Functional Mock-Up Units"
event = "JuliaCon 2024"
format = "Hands-on workshop"
start = 2024-07-09
location = "Eindhoven University of Technology, Netherlands"
role = "Given by"
people = ["tobias-thummerer", "lars-mikelsons"]
youtube = "sQ2MXSswrSo"

[[links]]
  label = "Workshop notebook (Pluto)"
  url = "https://github.com/JuliaFMI/FMIFlux.jl/tree/main/examples/pluto-src/SciMLUsingFMUs"
[[links]]
  label = "JuliaCon program"
  url = "https://pretalx.com/juliacon2024/talk/9KQJFS/"
+++

If you know something about a physical system, machine learning should not have to learn it again.
This hands-on workshop shows how to bring such system knowledge into machine learning by combining
Functional Mock-up Units (FMUs) with neural networks, so-called neural FMUs. The use case is a SCARA
robot arm that writes words with a pen. Its physical simulation model misses the stick-slip friction
between pen and paper, which the neural FMU learns from measurements. Participants build and train
their own hybrid model in a Pluto notebook with [FMI.jl](https://github.com/JuliaFMI/FMI.jl) and
[FMIFlux.jl](https://github.com/JuliaFMI/FMIFlux.jl).
