#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division, print_function, unicode_literals)
from builtins import *

import paramiko, getpass
import time, ntpath, platform
import os, json, sys
from datetime import datetime
import tempfile
import shutil
import tarfile
from . import version, status_manager
from distutils.dir_util import copy_tree, remove_tree

_print_header="--SShAgent:"

def get_supported_sites():
    siteFile = os.path.dirname(os.path.abspath(__file__)) + "/resources/site_dict.json"

    f = open(siteFile)
    site_dict = json.load(f)["ssh_agent"]["sites"]
    f.close()
    return [ x.encode('UTF8') for x in site_dict.keys() ]

class LaunchAgent(object):
    """A class/agent to connect to cluster


    local input files will be saved in C:/temp/cyberwater-staging-ssh/YYYMMDD-HHMM (Or ~/temp/cyberwater-staging-ssh/YYYMMDD-HHMM),
    local files will then be uploaded to HPC, and being processed, 
    the remote working directory will be first downloaded as a tarball at at: C:/temp/cyberwater-staging-ssh/YYYYMMDD-HHMM,
    then extract to the user-defined download-folder.

    Attributes:
        site_name: name of cluster resource. (gcp, bigred3, jetstream) 
        username: ask input of user name to log on to cluster
        port: ssh default port is 22
        prjDir: create a directory under /home/username/project_name on cluster
        is_started: whether the ssh session is started or not
        check_pend_feq: check the job whether has been submitted to 
            cluster every @check_pend_feq seconds
        check_run_feq: check the job whether is running on cluster 
            every @check_run_feq seconds
        check_cg_feq: when job completed, check the job whether is in 'CG' 
            state on cluster every @check_run_feq seconds
    
    """
    
    def __init__(self, site_name='bigred3', project_name='cyberwater', login_url=None, username = None, passwd= None, sched_env='slurm'):
        """Inits a cluster object
        
        Create an ssh agent to connect to cluster
        Users can connect to a remote site through ssh, his/her public key is copied to HPC(with the help of system admin), 
        Or, the user can choose to provide a passwd if the server doesn't have his/her public key.
        
        Args:
            site_name (str): HPC site can be (currently supports 'bigred3') 
            project_name (str, optional): create a directory under /home/username/project_name on cluster
            login_url (str): For cloud VM whose IP address can change overtime, provide a most recent ip (not needed currently for either GCP or JetStream) 
            username (str): ask input of user name to log on to cluster
            passwd (str, optional): password to login to cluster
            sched_env (str, optional): which scheduler to use, can be either 'slurm' or 'bash'

        Returns:
            None
            
        Raises:
            KeyError if site not supported
            If public-key authentication failed, raise authentication fail error and ask you retry with password
            If 3-times retries on password is still wrong, abort
            
        Examples:
            Launch job to JetStream, given that the login node has users'public key.

            >>> LaunchAgent(site_name = 'jetstream', project_name = 'cyberwater', username = 'fli5')

            Launch job to Bridges 2 with user-provided password.

            >>> LaunchAgent(site_name = 'bridges-LM', project_name = 'cyberwater', username = 'fli5', passwd =  'somepassword')

            Launch job to a tesla.cs.iupui.edu, which doesn't have Slurm.
            >>> LaunchAgent(site_name = 'tesla', project_name = 'cyberwater', username = 'lifen', passwd =  'somepassword')
        """
        
        self.is_started = False
        self.site_name = site_name

        siteFile = os.path.dirname(os.path.abspath(__file__)) + "/resources/site_dict.json"


        with open(siteFile) as f:
            self.site_dict = json.load(f)["ssh_agent"]["sites"]
        
        if login_url:
            self._login_url = login_url 
        else:
            try:
                self._login_url = self.site_dict[site_name]['login_url'] 
            except KeyError:
                print('Using site file' + siteFile)
                print('site name (' + site_name + ') is not supported, supported options are:')
                print(list(self.site_dict.keys()))
                quit()

        if sched_env != self.site_dict[site_name]["sched_env"]:
            raise RuntimeError("site %s has incompatible sched_env %s" %(site_name, sched_env))

        print("Initializing ssh-agent, version=" +  version.__version__)
        print("Prepare connecting to " + self.site_name + "(" + self._login_url + ")")

        if(username):
            self.username = username
            print("Using username (" + username + ') for ssh session')
        else:
            self.username = self.site_dict[site_name]['username']

        self.port = 22
        self.project_name = project_name

        self.key_filename = os.path.abspath(os.path.expanduser('~/.ssh/id_rsa'))
        self.password = passwd

        self.check_pend_feq = 10 
        self.check_run_feq = 10
        self.check_cg_feq = 5 

        self._ssh_connect()

        # fall back to password if publick key failed
        
        # mkdir results to store job logs
        # Non-blocking call
        command = 'printenv HOME'
        #print(command)
        stdin, stdout, stderr = self._ssh.exec_command(command)
        ret = stdout.channel.recv_exit_status() # Blocking call

        remoteHome=''
        if(ret != 0):
            raise RuntimeError('Cannot get HOME from HPC')

        remoteHome = stdout.read().splitlines()[0]


        self.experiment_time_str = datetime.now().strftime("%Y%m%d-%H%M")


        if('workdir' not in self.site_dict[self.site_name]):
            self.prjDir = remoteHome + '/' + self.project_name + '/' + self.experiment_time_str  + '/'
        else:
            self.prjDir = self.site_dict[self.site_name]['workdir']  + '/' + self.project_name + '/' + self.experiment_time_str  + '/'

        print("Remote workdir is" + self.prjDir)

        if sched_env == 'slurm':
            self.defaultqueue = self.site_dict[site_name]['defaultqueue'] 
            command = 'rm -rf ' + self.prjDir +';mkdir -p ' + self.prjDir + 'slurm_logs/;' + 'sinfo -O "partition,nodes,cpus,memory,time,available"'
            #raise RuntimeError('Tried to execute command:'+ command)

        else:
            command = 'rm -rf ' + self.prjDir +';mkdir -p ' + self.prjDir + 'slurm_logs/;'

        print("\n******Remote info (start)*******:")
        stdin, stdout, stderr = self._ssh.exec_command(command)
        ret = stdout.channel.recv_exit_status() # Blocking call
        if(ret != 0):
            for line in stderr:
                print(line)
        else:
            for line in stdout:
                print(line)
        print("\n******Remote info (end)*******:")
        
        # make staging folder
        self._system_type = platform.system()
        if self._system_type == 'Windows':
            temp_dir =  "C:\\temp"
        elif self._system_type == 'Linux':
            temp_dir =  "~/temp"
        else:
            raise Exception('System %s not supported' % (self._system_type))
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)


        self._status_manager = status_manager.StatusManager(os.path.join(temp_dir, "all_job_stat.json"))

        self.localdirpath = os.path.join(temp_dir, "cyberwater-staging-ssh")
        if not os.path.exists(self.localdirpath):
            os.makedirs(self.localdirpath)
        self.exp_input_path = os.path.join(self.localdirpath, self.project_name, "")
        if  os.path.exists(self.exp_input_path):
            remove_tree(self.exp_input_path)


        os.makedirs(self.exp_input_path)

        print("launchagent is created in a %s system, local staging dir is: %s" % (self._system_type, self.exp_input_path))
    
    def _ssh_connect(self, timeout = None):
        self._ssh = paramiko.SSHClient()
        # Trust all key policy on remote host
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if(self.password):
            # try password if user provides one
            try:
                self._ssh.connect(self._login_url, self.port, self.username, password = self.password, timeout = timeout)

            except (paramiko.BadHostKeyException, paramiko.AuthenticationException, 
                    paramiko.SSHException) as e:

                print("Login failed for user " + self.username+ " with current password..." + self.password + "Error Info:")
                print(e)
                exit()

        else:
            # otherwise check ssh keypair 
            try:
                self._ssh.connect(self._login_url, self.port, self.username, key_filename=self.key_filename, timeout=timeout)
            except (paramiko.BadHostKeyException, paramiko.AuthenticationException, 
                    paramiko.SSHException, ValueError) as e:
                print("Public-key authorization failed (Server doesn't have your key)")
                print(" For Google Cloud and Jetstream, please send your key (yourhomedir/.ssh/id_rsa.pub) to Feng Li (lifen@iu.edu), ")
                print(" For other system, please try to provide password: launchgent(xxx, passwd=)")
                print("exiting...")
                exit()

        self.is_started = True
        
        #ssh.close()
    
    def _may_reconnect(self):
        transport = self._ssh.get_transport() if self._ssh else None
        if not (transport and transport.is_active()):
            print("connection lost, now reconnecting...")
            self._ssh_connect()

    def __del__(self):
        if(self.is_started):
            self._ssh.close()
    
    def configure_slurm_job(self, nodes = 1, ntasks_per_node = 1, email='', 
                          walltime_in_mins=5, env_cmd='', execute_cmd='', execute_script='', remote_results_folder='.'):
        """generate a cluster job script
        
        Automatic generate a Slurm job script for user in case they know nothing about writing a HPC job script.
        Jobs can be described in either way (see examples)::
        
            1. env_cmd + execute_cmd
            2. execute_script (contains both  the path to a shell script)
        
        Args:
            nodes: number of compute nodes used on cluster for this job.
            ntasks_per_node: number of tasks running on a compute node, specifically for parallel program (e.g. MPI)
            email: user's email to receive email about submission, running, error and complete
            walltime_in_mins: estimated time for this job to be executed, in mins 
            env_cmd: command to preprare environment(e.g module load)
            execute_cmd: command to execute applications
            execute_script: a path to shell script.
            remote_results_folder: remote folder to download results from.
            
        Returns:
            the jobid that can be used in global status_manager
            
        Examples:
            >>> agent.configure_exp(node = 1, ntasks_per_node=10, env_cmd="module load python/3.7", execute_cmd="python somescript.py")

            ./run.sh can be shell script contains both env_cmd and execute_cmds

            >>> agent.configure_exp(node = 1, ntasks_per_node=10, env_cmd="module load python/3.7", execute_cmd="./run.sh")

            Can specify a subfoler that contains useful results, so that other contents of the remote working dir will not be downloaded  

            >>> agent.configure_exp(node = 1, ntasks_per_node=10, env_cmd="module load python/3.7", execute_cmd="./run.sh", remote_results_folder='./results')
        """
        now = datetime.now()
        file_name =  'cyberwater_' + self.site_name + '_slurm_job.sh'
        
        jobfile_path =  os.path.join(self.exp_input_path, file_name)
        # force unix-style newline: slurm forbits Windows crlf-style line termination
        f= open( jobfile_path, "w+", newline='')

        if(execute_script.endswith('.csh')):
            f.write("#!/bin/csh\n")
        else:
            f.write("#!/bin/bash\n")
        
        f.write('#SBATCH --job-name=\"' + file_name +'\"\n')                                                                                               
        f.write('#SBATCH --output=\"slurm_logs/' + file_name + '.out.%j\"\n')

        f.write("#SBATCH --partition=" + self.defaultqueue + "\n")
        
        f.write('#SBATCH --nodes=' + str(nodes) + '\n')
        f.write('#SBATCH --ntasks-per-node=' + str(ntasks_per_node) + '\n')


        if 'slurm_directive_str' in self.site_dict[self.site_name]: 
            f.write(self.site_dict[self.site_name]['slurm_directive_str'] + '\n')
            
        f.write("#SBATCH --export=ALL\n")
                
        f.write("#SBATCH --mail-type=ALL\n")        
        if (email != ''):
            f.write('#SBATCH --mail-user=' + str(email) + '\n')
        
        hours, mins = divmod(walltime_in_mins, 60)
        run_time = "{:0>2}:{:0>2}:{:0>2}".format(int(hours), int(mins), 0)
        f.write('#SBATCH -t ' + run_time + '\n\n')

        f.write('## my job commands start as below:\n')
        f.write('cd ' + self.prjDir + '\n')
        
        f.write('## Environment setup are as below:\n')
        f.write(env_cmd + '\n')
        
        f.write('## Execution commands are as below:\n')
        if(execute_cmd == ""):
            fin = open(execute_script, 'r')
            execute_cmd = fin.read()
            print('Using command script file', execute_script)
            fin.close()
        f.write(execute_cmd + '\n')
        f.close()

        self._remote_results_folder=remote_results_folder
        
        print("Job_file is generated: " + file_name)
        print("Using nr_nodes=%d, nprocs_per_node=%d\n" %(nodes, ntasks_per_node))
        print("Remote results folder at: %s\n" %(remote_results_folder))

        jid = self._status_manager.add_entry('slurm', self.site_name)
        return jid

    def configure_bash_job(self, env_cmd='', execute_cmd='', execute_script='', remote_results_folder='.'):
        """Configure a job that runs in remote bash environment

        Jobs can be described in either way::
        
            1. env_cmd + execute_cmd
            2. execute_script (contains both  the path to a shell script)

        Args:
            env_cmd: command to preprare environment(e.g module load)
            execute_cmd: command to execute applications
            execute_script (str): Script to be executed remotely.
            remote_results_folder (str, optional): Results folder path. Defaults to '.'.
        """
        now = datetime.now()

        job_file_name =  'cyberwater_' + self.site_name + '_bash_job.sh'
        # the actual work defined in the execute_cmd or execute_script
        work_file_name =  'do_work.sh'
        
        job_file_path =  os.path.join(self.exp_input_path, job_file_name)
        work_file_path =  os.path.join(self.exp_input_path,  work_file_name)

        with open(job_file_path, "w+", newline='') as f:
            f.write('''\
#!/bin/bash
bash do_work.sh &
process_id=$!
echo "PID: $process_id"
wait $process_id
echo "ExitStatus: $?" > $process_id.status
''')

        # force unix-style newline: slurm forbits Windows crlf-style line termination
        with open(work_file_path, "w+", newline='') as f:
            if(execute_script.endswith('.csh')):
                f.write("#!/bin/csh\n")
            else:
                f.write("#!/bin/bash\n")
            
            f.write('## my job commands start as below:\n')
            f.write('cd ' + self.prjDir + '\n')
            
            f.write('## Environment setup are as below:\n')
            f.write(env_cmd + '\n')
            
            f.write('## Execution commands are as below:\n')
            if(execute_cmd == ""):
                fin = open(execute_script, 'r')
                execute_cmd = fin.read()
                print('Using command script file', execute_script)
                fin.close()
            f.write(execute_cmd + '\n')

        self._remote_results_folder=remote_results_folder
        
        print("Job_file is generated: " + job_file_name)
        print("Remote results folder at: %s\n" %(remote_results_folder))

        jid = self._status_manager.add_entry('bash', self.site_name)
        return jid
    
    def launch_job(self, jobID):
        """Launch this job based on the configuration
        """

        self._may_reconnect()

        sftp = self._ssh.open_sftp()
        # callback: accepts the bytes transferred so far and the total bytes to be transferred
        # confirm=True: do a stat() on the file afterwards to confirm the file size
                
        for filename in os.listdir(self.exp_input_path):
            srcPath = os.path.join(self.exp_input_path, filename)
            dest = self.prjDir + filename
            print ("Uploading file: %s to path: %s/@%s:%s\n" %(srcPath,self.username, self._login_url,  dest))
            #sftp.put(srcPath, dest, callback=self.printTotals, confirm=True)
            sftp.put(srcPath, dest, confirm=True)

        sftp.close()

        job_entry = self._status_manager.get_entry(jobID)

        # SubmitJob
        if job_entry["AgentType"] == 'slurm':
            jobFileName =  'cyberwater_' + self.site_name + '_slurm_job.sh'
            commands = 'tar -xf packed.tar;'+ 'sbatch '+ jobFileName

            print("running remote command: " + commands)
            joboutput = self._ssh_block_command(commands) # Non-blocking call

            remote_jobID = joboutput.read().split()[-1].decode("utf-8")


        elif job_entry["AgentType"] == 'bash':
            # https://stackoverflow.com/questions/17560498/running-process-of-remote-ssh-server-in-the-background-using-python-paramiko
            # https://stackoverflow.com/a/14158100/6261848
            jobFileName =  'cyberwater_' + self.site_name + '_bash_job.sh'

            commands = 'tar -xf packed.tar;'+ 'sh '+ jobFileName

            print("running remote command: " + commands)
            joboutput = self._ssh_block_command(commands) # Non-blocking call

            remote_jobID = joboutput.readline().rstrip().split()[-1].decode("utf-8")
        else:
            raise RuntimeError("job entry has corrupted AgentType")

        print("Successfully Submit your job on cluster with jobID %d (remote_jobID=%d)" % (jobID, int(remote_jobID)))
        self._status_manager.update_entry(jobID, 'JobStatus', 'PENDING')
        self._status_manager.update_entry(jobID, 'RemoteJobID', remote_jobID)

        return
    
    def _printTotals(self, transferred, toBeTransferred):
        """print real-time transfer(upload/download) status"""
        print("Transferred: {0}\tOut of: {1}".format(transferred, toBeTransferred))
    
   
    def _ssh_block_command(self, commands):
        """Execute commands on cluster Login Node
        
        A blocking call to execute commands on remote login node.
        This function will autumatically cd to your prjDir. Specifically, 
        if a job script has been uploaded to a remote login node, you can 
        directly call this function with setting input commands "sbatch job_script"
        
        Args:
            commands (str): The commands. 
        
        Returns:
            print your commands to screen 
            
        Raises:
            None
        
        Examples:
            >>> obj._ssh_block_command('cd cyberwater; squeue -u username')
        """
        commands = 'cd ' + self.prjDir + ';' + commands

        self._may_reconnect()
        stdin, stdout, stderr = self._ssh.exec_command(commands, get_pty=True)
        ret = stdout.channel.recv_exit_status() # Blocking call
        if(ret != 0):
            print('return with'+ str(ret))
            print('stderr:')
            for line in stderr:
                print(line)
            raise Exception('command: '+ commands + 'return with'+ str(ret))

        for line in stderr:
            print(line)
        return stdout
    
    def run_monitor_job(self, jobID):
        """Upload a job script, submit this job, and monitor this job status
        
        Specify the job
        Get the job_ID and use the ID to monitor job status.
        
        Args:
            jobID (int): 
        
        Returns:
            None
            
        Raises:
            OSError: No suchfile
        """

        t_start_upload = time.time()

        self.launch_job(jobID)

        t_end_upload = time.time()

        print("Start Monitor Job: %d" % jobID)
        jobFinalStatus = self._monitor_job(jobID)

        if jobFinalStatus != 'COMPLETED':
            raise RuntimeError('Remote job failed!')

        #print("\n******Timing********\n\tupload\tprocessing\tdownload")
        #print("\t%.3f\t%.3f\t%.3f" %(t_end_upload-t_start_upload, t_start_download - t_end_upload, t_end_download - t_start_download))

    def get_job_status(self, jobID):
        """Get job status

        Args:
            jobID (int): the jobID maintained by launchAgent. 

        Returns:
            str: the status string, can be one of {CREATED, PENDING, RUNNING, COMPLETED, FAILED}
        """
        return self.get_job_info(jobID)['JobStatus']

    def get_job_info(self, jobID):
        """Obtain registered job information

        Args:
            jobID (int): the jobID maintained by launchAgent.
        
        Returns:
            A dictionary of fields to describe this job.  
            if not the above states, return 1, means job completely finshed or no jobID found
            
        Raises:
            runtimeError if trying to use a non-exsiting jobID.
            
        Examples:
            >>> job_entry = obj.get_job_info(jobID)
            >>> print("localjobid: %d, job description: %s" %(jobID, job_entry))
            Will output:
            >>> localjobid: 5, job description: {'SiteName': 'stampede2', 'AgentType': 'gateway', 'JobStatus': 'CREATED', 'RemoteJobID': -1, 'CreatedTime': '20210510-2231', 'JobID': 5}
        """

        job_entry = self._status_manager.get_entry(jobID)
        
        # Explanation of slurm job state is here: https://slurm.schedmd.com/squeue.html#lbAG
        if job_entry["AgentType"] == 'slurm':
            stdout = self._ssh_block_command('scontrol show job %s |grep JobState' % int(job_entry["RemoteJobID"]))
            #lines = stdout.read().strip().split('\n')
            for line in stdout:
                stat_dict=dict(s.split('=', 1) for s in line.split())
            #return stat_dict

            status = stat_dict['JobState']
            if (status == 'COMPLETING'):
                job_entry['JobStatus'] = "RUNNING"
            else:
                job_entry['JobStatus'] = status

            self._status_manager._persist()
            return job_entry
            #print('get_job_stat ' + jobID + ' completed')
        elif job_entry["AgentType"] == 'bash':

            self._may_reconnect()

            commands = 'cd ' + self.prjDir + ';' + "cat %d.status 2>/dev/null " % int(job_entry["RemoteJobID"])
            stdin, stdout, stderr = self._ssh.exec_command(commands, get_pty=True)
            ret = stdout.channel.recv_exit_status() # Blocking call

            if(ret != 0):
                job_entry["JobStatus"] = "RUNNING"
                print('-- commands:', commands)
                print('-- return with'+ str(ret))
                print('-- stderr:')
                for line in stderr:
                    print(line)
            else:
                job_ExitStatus = int(stdout.readline().rstrip().split()[-1].decode("utf-8"))
                if job_ExitStatus == 0:
                    job_entry["JobStatus"] = "COMPLETED"
                else:
                    job_entry["JobStatus"] = "FAILED"
            #print('get_job_stat ' + jobID + ' completed')

            self._status_manager._persist()

            return job_entry

        else:
            return None
    
    def _monitor_job(self, jobID):
        """Monitor this job status
        
        check job status with Pending, Running, or Nearly Completed (CG)
        This function is for internal used, and not exposed to user.
        
        Args:
            jobID: 
        
        Returns:
            Final job status
            
        Raises:
            None
        """

        secs_wait = 5
        
        while True:

            status = self.get_job_status(jobID)

            if status == 'PENDING':
                print('jobid = %d, status: %s, wait for %d seconds' % (jobID, status, secs_wait))
                time.sleep(secs_wait)
            elif status == 'RUNNING':
                print('jobid = %d, status: %s, wait for %d seconds' % (jobID, status, secs_wait))
                time.sleep(10)
            elif status == 'COMPLETING':
                print('jobid = %d, status: %s, wait for %d seconds' % (jobID, status, secs_wait))
                time.sleep(self.check_run_feq)
                time.sleep(self.check_cg_feq) #
            elif status == 'CONFIGURING':
                print('jobid = %d, status: %s, wait for %d seconds' % (jobID, status, secs_wait))
                time.sleep(self.check_cg_feq) #
            elif status == 'COMPLETED':
                print('jobid = %d, Completed' % (jobID))
                break

            else:
                raise RuntimeError('jobid =%d  Failed!' % (jobID))
                break

        return status


    def upload_folder(self, inputpath):
        """ Upload local folder to remote working directory

        Args:
            inputpath (Path): path of local folder to be uploaded 

        Examples:
            agent.upload_folder('tests/matrix/')

        """
        archivefile = os.path.join(self.exp_input_path, 'packed')
        shutil.make_archive(archivefile, 'tar', inputpath)
        print('Archive created at(', archivefile ,'), using local files in:', inputpath)


    def download_folder(self, outputpath):
        """ Download all contents from remote remote directory to local folder

        This will recursively copy files/folders from remote working directory.
        If remote_results_foder is provided in the `configure_slurm_job` or `configure_bash_job` function, downloading will starts from that remote subfolder.

        Args:
            outputpath (path): directory path where remote files will be copied to 
        """
        # make a tarball of the working dir
        print (_print_header, "creating tarball for remote results...")
        result_tarball_name = self.project_name + '_results.tar'
        # tar -cf results.tar -C cyberwater .
        commands = 'cd ../; tar -cf ' + result_tarball_name + ' -C '+ self.experiment_time_str + ' ' + self._remote_results_folder
        joboutput = self._ssh_block_command(commands) # blocking call

        t_start_download = time.time()
        # callback: accepts the bytes transferred so far and the total bytes to be transferred
        # confirm=True: do a stat() on the file afterwards to confirm the file size
        srcPath = self.prjDir + '../' +result_tarball_name 

        result_tarball_folder=os.path.join(self.localdirpath, self.experiment_time_str)

        if not os.path.exists(result_tarball_folder):
            os.makedirs(result_tarball_folder)

        self.result_tarball_fullpath = os.path.join(result_tarball_folder, result_tarball_name)
        print (_print_header, "Completed, downloading tarball of remote working directory to path: %s\n" %(self.result_tarball_fullpath))

        self._may_reconnect()
        sftp = self._ssh.open_sftp()

        #sftp.get(srcPath, dest, callback=self.printTotals)
        sftp.get(srcPath, self.result_tarball_fullpath)
        sftp.close()

        t_end_download = time.time()

        tarball = tarfile.open(self.result_tarball_fullpath, 'r')
        tarball.extractall(outputpath)
        tarball.close
        print(_print_header, "extract results from tarball to ", outputpath)