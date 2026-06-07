#!/bin/tcsh
# define apps root dir

# load gcc first
module use /group/halla/modulefiles
module load root/6.30.04

# set these to make sure cmake is using the correct C/C++ compilers
setenv CC `which gcc`
setenv CXX `which g++`

