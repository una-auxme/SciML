+++
title = "Hyperparameter Optimization in Julia"
acronym = "Optuna.jl"
funding = "internal"                     # public | internal
start = 2026
summary = "Optuna.jl brings the open-source hyperparameter optimization framework Optuna to the Julia programming language."
members = ["julian-trommer", "tobias-thummerer", "andreas-hofmann", "josef-jouaux", "valentin-hoepfner"]
website = "https://github.com/una-auxme/Optuna.jl"
weight = 5
+++

Machine-learning models, including those used in scientific machine learning such as neural ODEs and
hybrid models, depend on hyperparameters like learning rates, network sizes or training settings.
Tuning them by hand is tedious and hard to reproduce.

[Optuna.jl](https://github.com/una-auxme/Optuna.jl) is a Julia interface to
[Optuna](https://optuna.org/), the open-source hyperparameter optimization framework. It lets you
define the search space directly in a Julia objective function, run studies with many trials (also
multithreaded), store studies and artifacts in a database and query the best parameters afterwards.

- Source code and examples: [github.com/una-auxme/Optuna.jl](https://github.com/una-auxme/Optuna.jl)
- Documentation: [una-auxme.github.io/Optuna.jl](https://una-auxme.github.io/Optuna.jl/)
- Install in Julia: `] add Optuna`

*Optuna and the Optuna logo are trademarks of Preferred Networks, Inc.*
