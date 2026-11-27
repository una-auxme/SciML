+++
title = "Proper Hybrid Models for Smarter Vehicles"
acronym = "PHyMoS"
funding = "public"                       # public | internal
funder = "BMWK"                          # German Federal Ministry for Economic Affairs and Climate Action
grant = "19I20022H"
start = "2021-03"
end = "2024-08"
summary = "Hybrid models that combine physical knowledge with machine learning, to build fast and data-efficient \"proper models\" of vehicles and their surroundings."
members = ["yi-zhang", "julian-trommer", "tobias-thummerer"]   # folder names in content/members/
partners = ["ESI Germany GmbH", "Hochschule Bielefeld", "LTX Simulation GmbH", "Modelon Deutschland GmbH", "Robert Bosch GmbH", "TLK-Thermo GmbH", "Technische Universität Braunschweig", "XRG Simulation GmbH"]
website = "https://phymos.de/en/"
publications = [                         # DOIs of project publications shown on this page
  "10.3390/s22145408",
  "10.1186/s40323-023-00246-y",
  "10.1109/AIM46323.2023.10196190",
  "10.3384/ecp204141",
]
weight = 5
+++

**PHyMoS** (*Proper Hybrid Models for Smarter Vehicles*) was a research project funded by the German
Federal Ministry for Economic Affairs and Climate Action (BMWK), running from March 2021 to
August 2024.

The vehicle of the future is "smart": it adapts flexibly to changes in its surroundings and makes
decisions on its own. For this, it needs models of itself and of its environment that predict the
effects of its own behavior, and these models must be built quickly and at low cost, with the right
balance between fidelity and computational speed. Classical model-based approaches take a lot of
development effort, while machine learning needs a lot of data and brings other risks. PHyMoS
therefore evaluated hybrid approaches, which combine physics and data, in concrete applications, to
generate scalable "proper models" data-efficiently from existing physical knowledge. Nine partners
from industry and academia showed the results on eight demonstrators. Open questions on
standardization are carried on in the ITEA 4 project [OpenSCALING](/projects/openscaling/).

Our group worked on AI-supported simulation, in particular on hybrid models and AI-based
extrapolation for AI-enriched digital twins:

- [Yi Zhang](/members/yi-zhang/) developed Bayesian methods for parameter identification and model
  calibration with uncertainty quantification, based on BayesFlow and normalizing flows, applied for
  example to the thermal model of a vehicle cabin and to the final testing of MEMS sensors.
- [Julian Trommer](/members/julian-trommer/) used MeshGraphNets as neural ODEs to simulate physical
  systems in industrial applications and developed the Julia package
  [MeshGraphNets.jl](https://github.com/una-auxme/MeshGraphNets.jl).
- [Tobias Thummerer](/members/tobias-thummerer/) worked on neural FMUs for hybrid digital twins.

More information: [phymos.de](https://phymos.de/en/)
