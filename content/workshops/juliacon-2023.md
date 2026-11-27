+++
title = "Using NeuralODEs in real life applications"
event = "JuliaCon 2023"
format = "Hands-on workshop"
start = 2023-07-25
location = "Massachusetts Institute of Technology, Cambridge, USA"
role = "Given by"
people = ["tobias-thummerer", "lars-mikelsons"]
youtube = "X_u0KlZizD4"

[[links]]
  label = "Workshop notebook"
  url = "https://juliafmi.github.io/FMIFlux.jl/dev/examples/juliacon_2023/"
[[links]]
  label = "JuliaCon program"
  url = "https://pretalx.com/juliacon2023/talk/EWL3LC/"
+++

Neural ODEs give impressive results on academic examples, but often disappoint on real applications:
poor convergence, discontinuities and instabilities are some of the stumbling blocks. This workshop
shows how to integrate industrial simulation models into neural ODEs through the FMI standard, and
presents training strategies that make such hybrid models work in practice, including distributed
hyperparameter optimization, using [FMI.jl](https://github.com/JuliaFMI/FMI.jl) and
[FMIFlux.jl](https://github.com/JuliaFMI/FMIFlux.jl).
