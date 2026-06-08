# PRad Launch Usage

This directory contains a small launcher for creating SWIF2 workflows for PRad2 replay and filter jobs.

The main reason to use this launcher is to run many replay jobs in parallel across the farm instead of processing runs by hand on one machine. It also lets SWIF2 handle MSS input staging for replay jobs: if `INDATA_TOPDIR` points to `/mss/...`, the launcher declares those EVIO files as `mss:` inputs, and SWIF2 handles pulling them from tape/cache before the job runs. You do not need to run separate `jcache` commands first.

Before running, edit the config file you want to use:

```bash
prad_replay.config
prad_filter.config
```

The main fields to check are the executable path, input directory, output directories, workflow name, and job resources. `ENVFILE` and `CUTS_JSON` may be relative paths; `prad_launch.py` resolves them relative to the config file.

Run replay jobs with a run range:

```bash
python prad_launch.py prad_replay.config 24554 24666
```

Run filter jobs with a run range:

```bash
python prad_launch.py prad_filter.config 24554 24666
```

To use a run list instead of a range, put one run number per line in a text file:

```bash
python prad_launch.py prad_replay.config --runfile runs.txt
python prad_launch.py prad_filter.config --runfile runs.txt
```

To create the workflow and add jobs without submitting it:

```bash
python prad_launch.py prad_replay.config 24554 24666 --create-only
```

Submit a created workflow later with:

```bash
swif2 run -workflow prad2_workflow_name
```

Check workflow status with:

```bash
swif2 status -workflow prad2_replay_workflowName
swif2 status -workflow prad2_filter_workflowName
```

Replay mode reads EVIO files from `INDATA_TOPDIR/prad_RUNNUMBER`. Filter mode reads replay ROOT files from `INDATA_TOPDIR/RUNNUMBER`.

If the workflow already exists, the launcher will continue and add jobs to it. If a job name already exists in that workflow, SWIF2 may reject that duplicate job.
