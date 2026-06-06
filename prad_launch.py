#!/usr/bin/env python3

"""
PRad2 Replay Launcher - SWIF2 workflow submission
Adapted from launch.py for PRad2 replay workflow

Usage: prad_launch.py config_file minrun maxrun [options]
"""

from optparse import OptionParser
import os
import sys
import time
import glob
import re
import subprocess
from subprocess import Popen, PIPE

VERBOSE = False

####################################################### TRY COMMAND ######################################################

def try_command(command, sleeptime=5):
    """Try an os command and if the exit code is non-zero then retry"""
    return_code = -999
    max_retries = 3
    retries = 0
    
    while return_code != 0 and retries < max_retries:
        process = Popen(command.split(), stdout=PIPE, stderr=PIPE)
        output, error = process.communicate()
        if output:
            print(output.decode())
        if error and VERBOSE:
            print(error.decode())
        return_code = process.returncode

        if return_code == 0:
            return True

        # sleep for a few seconds between tries
        retries += 1
        if retries < max_retries:
            print(f'Command failed (attempt {retries}/{max_retries}), sleeping for {sleeptime} sec...')
            time.sleep(sleeptime)
    
    if return_code != 0:
        print(f"ERROR: Command failed after {max_retries} attempts")
        print(f"Command: {command}")
        return False
    
    return True

####################################################### READ CONFIG ######################################################

def read_config(CONFIG_FILENAME):
    """Read in user config file"""
    config_dict = {}

    with open(CONFIG_FILENAME, 'r') as infile_config:
        for line in infile_config:
            # Ignore empty lines, and lines that begin with #
            if (len(line.split()) == 0) or (line.split()[0][0] == '#'):
                continue

            # Add new key/value pair into config_dict
            key = str(line.split()[0])
            value = line.split()[1]
            
            config_dict[key] = value
            if VERBOSE:
                print(f"CONFIG: {key} = {value}")

    return config_dict

##################################################### VALIDATE CONFIG ####################################################

def validate_config(config_dict):
    """Validate that all required config parameters are present"""

    # JOB ACCOUNTING
    if ("PROJECT" not in config_dict) or ("TRACK" not in config_dict) or ("OS" not in config_dict):
        print("ERROR: JOB ACCOUNTING NOT FULLY SPECIFIED IN CONFIG FILE. ABORTING")
        sys.exit(1)

    # JOB RESOURCES
    if ("NCORES" not in config_dict) or ("DISK" not in config_dict) or ("RAM" not in config_dict) or ("TIMELIMIT" not in config_dict):
        print("ERROR: JOB RESOURCES NOT FULLY SPECIFIED IN CONFIG FILE. ABORTING")
        sys.exit(1)

    # WORKFLOW DEFINITION
    if ("WORKFLOW" not in config_dict):
        print("ERROR: WORKFLOW DEFINITION NOT FULLY SPECIFIED IN CONFIG FILE. ABORTING")
        sys.exit(1)

    # ENVIRONMENT AND EXECUTABLES
    if ("ENVFILE" not in config_dict) or ("REPLAY_EXEC" not in config_dict):
        print("ERROR: ENVIRONMENT/EXECUTABLES NOT FULLY SPECIFIED IN CONFIG FILE. ABORTING")
        sys.exit(1)

    # FILE INPUT, OUTPUT BASE DIRECTORIES
    if ("INDATA_TOPDIR" not in config_dict) or \
       ("OUTDIR_LARGE" not in config_dict) or ("OUTDIR_SMALL" not in config_dict):
        print("ERROR: FILE INPUT, OUTPUT BASE DIRECTORIES NOT FULLY SPECIFIED IN CONFIG FILE. ABORTING")
        sys.exit(1)

    # CHECK FILE EXISTENCE
    if not os.path.isfile(config_dict["ENVFILE"]):
        print(f"ERROR: ENVFILE does not exist: {config_dict['ENVFILE']}")
        sys.exit(1)
    
    if not os.path.isfile(config_dict["REPLAY_EXEC"]):
        print(f"ERROR: REPLAY_EXEC does not exist: {config_dict['REPLAY_EXEC']}")
        sys.exit(1)

    # CHECK OUTPUT (SMALL) FOLDER EXISTENCE - create if needed
    if not os.path.isdir(config_dict["OUTDIR_SMALL"]):
        LOG_DIR = config_dict["OUTDIR_SMALL"] + "/log"
        make_log_dir = "mkdir -p " + LOG_DIR
        os.makedirs(LOG_DIR, exist_ok=True)
        if VERBOSE:
            print(f"Created log directory: {LOG_DIR}")

####################################################### FIND FILES #######################################################

def find_files(input_dir):
    """Find .evio files in input directory (works for both MSS and disk)"""
    
    # MSS is a filesystem representation of tape, so ls/glob work fine
    if not os.path.isdir(input_dir):
        if VERBOSE:
            print(f"  Directory does not exist: {input_dir}")
        return []
    
    pathstring = f"{input_dir}/prad_*.evio.*"
    files = sorted(glob.glob(pathstring))
    
    if VERBOSE and len(files) > 0:
        print(f"  File listing sample (first 3):")
        for f in files[:3]:
            print(f"    {os.path.basename(f)}")
    
    return files

######################################################## ADD JOB #########################################################

def add_job(WORKFLOW, filepath, input_dir, config_dict):
    """Add a single replay job to the workflow"""
    
    # Extract run number and file number from filepath
    # Expected format: /path/prad_RUNNUMBER.evio.FILENUMBER
    match = re.search(r"prad_(\d{6})\.evio\.(\d{5})", filepath)
    if not match:
        print(f"  Warning: Could not parse filename {filepath}")
        return False
    
    RUNNO = match.group(1)
    FILENO = match.group(2)
    FILENAME = os.path.basename(filepath)
    
    # Job name
    DATE = time.strftime("%Y-%m-%d")
    JOBNAME = f"{WORKFLOW}_run{RUNNO}_file{FILENO}"
    
    # Determine input type (mss or file)
    input_type = "mss" if input_dir.startswith("/mss/") else "file"
    
    # Setup output directory for this run
    OUTDIR_RUN = os.path.join(config_dict["OUTDIR_LARGE"], RUNNO)
    
    # Setup log directory
    LOG_DIR = os.path.join(config_dict["OUTDIR_SMALL"], "log", RUNNO)
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # Create the add-job command
    add_command = f"swif2 add-job -workflow {WORKFLOW} -name {JOBNAME}"
    
    # Job accounting
    add_command += f" -account {config_dict['PROJECT']}"
    add_command += f" -partition {config_dict['TRACK']}"
    add_command += f" -os {config_dict['OS']}"
    
    # Resources
    add_command += f" -cores {config_dict['NCORES']}"
    add_command += f" -disk {config_dict['DISK']}"
    add_command += f" -ram {config_dict['RAM']}"
    add_command += f" -time {config_dict['TIMELIMIT']}"
    
    # Input file (SWIF2 handles jcache automatically for MSS)
    add_command += f" -input {FILENAME} {input_type}:{filepath}"
    
    # Stdout, stderr
    add_command += f" -stdout {LOG_DIR}/stdout_{RUNNO}_{FILENO}.out"
    add_command += f" -stderr {LOG_DIR}/stderr_{RUNNO}_{FILENO}.err"
    
    # Tags
    add_command += f" -tag run_number {RUNNO} -tag file_number {FILENO}"
    
    # The command to run: handle environment setup based on file type
    # Note: SWIF2 stages the input file in the local scratch directory
    # We need to make sure the output directory exists
    
    # Check if environment file is csh/tcsh
    if config_dict['ENVFILE'].endswith('.csh'):
        # Use tcsh to source csh files
        command = f"tcsh -c 'source {config_dict['ENVFILE']} && "
        command += f"mkdir -p {OUTDIR_RUN} && "
        command += f"{config_dict['REPLAY_EXEC']} {FILENAME} "
        command += f"-j {config_dict['NCORES']} "
        command += f"-z {config_dict['ZVERTEX_CUT']} "
        command += f"-o {OUTDIR_RUN}/'"
    else:
        # Assume bash/sh syntax
        command = f"source {config_dict['ENVFILE']} && "
        command += f"mkdir -p {OUTDIR_RUN} && "
        command += f"{config_dict['REPLAY_EXEC']} {FILENAME} "
        command += f"-j {config_dict['NCORES']} "
        command += f"-z {config_dict['ZVERTEX_CUT']} "
        command += f"-o {OUTDIR_RUN}/"
    
    add_command += f" {command}"
    
    if VERBOSE:
        print(f"  Job add command:\n  {add_command}")
    
    # ADD JOB
    success = try_command(add_command)
    if success:
        print(f"  Added job: {JOBNAME}")
    return success

########################################################## MAIN ##########################################################

def main(argv):
    global VERBOSE
    
    # PARSER
    parser_usage = "prad_launch.py config_file minrun maxrun\n"
    parser_usage += "       OR\n"
    parser_usage += "       prad_launch.py config_file --runfile runs.txt\n\n"
    parser_usage += "Create SWIF2 workflow for PRad2 replay jobs\n\n"
    parser_usage += "optional: -v: verbose output\n"
    parser_usage += "optional: --create-only: create workflow but don't submit\n"
    parser_usage += "optional: --runfile FILE: process runs listed in FILE (one per line)\n"
    parser = OptionParser(usage=parser_usage)
    
    # PARSER OPTIONS
    parser.add_option("-v", "--verbose", dest="verbose", action="store_true", help="verbose output")
    parser.add_option("--create-only", dest="create_only", action="store_true", 
                     help="create workflow but don't submit")
    parser.add_option("--runfile", dest="runfile", help="text file with run numbers (one per line)")
    
    # GET ARGUMENTS
    (options, args) = parser.parse_args(argv)
    
    # Determine run list - either from file or from range
    run_list = []
    CONFIG_FILE = None
    
    if options.runfile:
        # Using runfile - need at least config file
        if len(args) < 1:
            parser.print_help()
            return
        
        CONFIG_FILE = args[0]
        
        # Read run numbers from file
        try:
            with open(options.runfile, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        try:
                            run_list.append(int(line))
                        except ValueError:
                            print(f"Warning: Skipping invalid run number: {line}")
            
            if len(run_list) == 0:
                print(f"ERROR: No valid run numbers found in {options.runfile}")
                return
            
            print(f"Loaded {len(run_list)} runs from {options.runfile}")
        
        except IOError as e:
            print(f"ERROR: Could not read runfile {options.runfile}: {e}")
            return
    else:
        # Using run range - need config, minrun, maxrun
        if len(args) < 3:
            parser.print_help()
            return
        
        CONFIG_FILE = args[0]
        MINRUN = int(args[1])
        MAXRUN = int(args[2])
        run_list = list(range(MINRUN, MAXRUN + 1))
    
    VERBOSE = options.verbose if options.verbose else False
    
    print(f"PRad2 Replay Launcher")
    print(f"Config file: {CONFIG_FILE}")
    if options.runfile:
        print(f"Run list from file: {options.runfile} ({len(run_list)} runs)")
        if VERBOSE and len(run_list) <= 20:
            print(f"  Runs: {sorted(run_list)}")
    else:
        print(f"Run range: {min(run_list)} - {max(run_list)}")
    
    # READ CONFIG
    config_dict = read_config(CONFIG_FILE)
    validate_config(config_dict)
    
    # SET CONTROL VARIABLES
    WORKFLOW = config_dict["WORKFLOW"]
    INDATA_TOPDIR = config_dict["INDATA_TOPDIR"]
    
    # CREATE WORKFLOW
    print(f"\nCreating SWIF2 workflow: {WORKFLOW}")
    create_workflow_cmd = f"swif2 create -workflow {WORKFLOW}"
    if not try_command(create_workflow_cmd):
        print("ERROR: Failed to create workflow")
        sys.exit(1)
    
    # FIND & ADD JOBS
    total_jobs = 0
    for RUN in run_list:
        FORMATTED_RUN = f"{RUN:06d}"
        
        print(f"\nProcessing run {FORMATTED_RUN}")
        
        # Input directory path
        input_dir = f"{INDATA_TOPDIR}/prad_{FORMATTED_RUN}"
        print(f"  Input directory: {input_dir}")
        
        # Determine if this is MSS (tape) or disk
        is_mss = input_dir.startswith("/mss/")
        input_type = "mss" if is_mss else "file"
        print(f"  Input type: {input_type}")
        
        # Find files
        file_list = find_files(input_dir)
        print(f"  Found {len(file_list)} files")
        
        if len(file_list) == 0:
            print(f"  WARNING: No files found for run {FORMATTED_RUN}")
            continue
        
        # Add a job for each file
        for filepath in file_list:
            if add_job(WORKFLOW, filepath, input_dir, config_dict):
                total_jobs += 1
    
    print(f"\n{'='*60}")
    print(f"Total jobs added to workflow: {total_jobs}")
    print(f"Workflow name: {WORKFLOW}")
    
    if total_jobs == 0:
        print("\nWARNING: No jobs were added to the workflow!")
        print("Check that the input directory contains data files.")
        return
    
    if not options.create_only:
        print(f"\nSubmitting workflow...")
        submit_cmd = f"swif2 run -workflow {WORKFLOW}"
        if try_command(submit_cmd):
            print(f"Workflow submitted!")
        else:
            print(f"ERROR: Failed to submit workflow")
            return
    else:
        print(f"\nWorkflow created but not submitted (--create-only)")
        print(f"To submit later: swif2 run -workflow {WORKFLOW}")
    
    print(f"\nTo check status: swif2 status -workflow {WORKFLOW}")

if __name__ == "__main__":
    main(sys.argv[1:])
