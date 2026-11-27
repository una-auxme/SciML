+++
title = "Modular Hybrid Digital Twins for System Design and Operational Monitoring in Production"
acronym = "MoHyProTwin"
funding = "public"                       # public | internal
funder = ""
grant = ""
# start = "2026-01"                      # year (2026) or month ("2026-07")
# end = "2028-12"
summary = "Modular hybrid models based on physics-enhanced neural ODEs that can be reused like library components, developed on a multi-axis gantry robot."
members = ["andreas-hofmann"]              # folder names in content/members/
partners = []
website = ""
publications = []                        # DOIs of project publications shown on this page
weight = 2
+++

Production systems are becoming increasingly complex due to the transition to Industry 5.0 and
increasingly ambitious sustainability goals. The tools used to design them therefore require
significantly higher accuracy in order to detect errors at an early stage.

In **MoHyProTwin**, we research modular hybrid models that combine physics-based simulation models
(e.g. Modelica) with machine learning methods. For this purpose, we use physics-enhanced neural ODEs
(PeN-ODEs) from the field of scientific machine learning. Thanks to the underlying physics, these
hybrid models are data-efficient and extrapolate significantly better than purely data-driven
machine learning models.

A key focus of the project is the modularization of PeN-ODEs. Currently, PeN-ODEs are trained for one
specific system and cannot be transferred to other systems afterwards. In the future, trained
submodels should be reusable like components of a library and combinable into new systems.

A real test bench of a multi-axis gantry robot in research hall 43 of the Center for Future Production
(CFP) serves as the experimental platform. On this test bench, we also investigate the benefits of
hybrid models for model-based controller design and for quality assurance during operation.
