+++
title = "SciML Classroom Arm for Research, AI & Benchmarking"
acronym = "SCARAB"
funding = "internal"                     # public | internal
summary = "A small SCARA robot arm that writes on paper: a source of benchmark data and a training system for students to explore traditional and machine-learning-based modeling and control."
members = ["tobias-thummerer", "yi-zhang", "andreas-hofmann"]   # folder names in content/members/
website = "https://github.com/SCARAB-robot/docu"
weight = 6
+++

**SCARAB** (*SciML Classroom Arm for Research, AI & Benchmarking*) is a robot arm of the SCARA
type (*Selective Compliance Assembly Robot Arm*) that writes on a sheet of paper. Two rotational
axes move the pen across the paper; a third axis lifts the pen and pushes it down onto the paper.

SCARAB serves two purposes: it generates benchmark data for scientific machine learning, and it is
a training system on which students explore traditional and machine-learning-based modeling and
control.

The project consists of four parts:

- **docu**: the project documentation, available on GitHub at
  [SCARAB-robot/docu](https://github.com/SCARAB-robot/docu)
- **system**: CAD files and PCB design files of the physical robot
- **model**: simulation models of the robot
- **data**: a dataset recorded from the real robot
