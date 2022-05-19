#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Tu Dec 17 15:15:39 2019
@author: Feng Li
@author: Yuankun Fu
"""

from __future__ import (absolute_import, division, print_function, unicode_literals)
from builtins import *

import paramiko, getpass
import time, ntpath
import os, json
from datetime import datetime
import tempfile
import shutil
import tarfile

class LaunchAgent(object):
    """A class/agent to connect to cluster
    
    """
    
    def __init__(self, site_name='bigred3', project_name='cyberwater', login_url=None,username = None, password = None, check_pend_feq = 30, 
                 check_run_feq = 10, check_cg_feq = 5):
        """Inits a cluster object
        
        Create an ssh agent to connect to cluster
        1. Ask for user name on cluster.
        2. Ask for the user's password on cluster.
        3. User have 3 times to retry their password if they typed wrong.
        
        Attributes:
            site_name: name of cluster resource. (gcp, bigred3, jetstream) 
            login_url: login_url to cluster login node
            username: ask input of user name to log on to cluster
            port: ssh default port is 22
            prjDir: create a directory under /home/username/project_name on cluster
            is_started: whether the ssh session is started or not
        
        Args:
            site_name: HPC site can be (currently supports 'bigred3') 
            project_name: create a directory under /home/username/project_name on cluster
            username: ask input of user name to log on to cluster
            check_pend_feq: check the job whether has been submitted to 
                cluster every @check_pend_feq seconds
            check_run_feq: check the job whether is running on cluster 
                every @check_run_feq seconds
            check_cg_feq: when job completed, check the job whether is in 'CG' 
                state on cluster every @check_run_feq seconds
            
        Returns:
            None
            
        Raises:
            If password is wrong, raise authentication fail error and ask you retry
            If 3-times retries on password is still wrong, abort
            
        Examples:
            >>> Bigred3(project_name = 'cyberwater', username = 'lifen')
            >>> Bigred3('cyberwater', 'lifen',60, 600, 5)
        """
        
        self.is_started = False
        self.site_name = site_name

        with open('site_dict.json') as f:
            self.site_dict = json.load(f)

        if(login_url):
            self.login_url = login_url
        else:

            try:
                self.login_url = self.site_dict[site_name]['login_url'] 
            except KeyError:
                print('site name (' + site_name + ') is not supported, supported options are:')
                print(list(self.site_dict.keys()))
                quit()

        print("Prepare connecting to " + self.site_name + "(" + self.login_url + ")")

        if(username):
            self.username = username
            print("Using username (" + username + ') for ssh session')
        else:
            self.username = self.site_dict[site_name]['username']

        self.port = [22,22][site_name=="bridges" or site_name=="bridges-LM"]
        self.project_name = project_name
        self.check_pend_feq = check_pend_feq
        self.check_run_feq = check_run_feq
        self.check_cg_feq = check_cg_feq

        if(self.site_name == 'bigred3'):
            self.prjDir = '/N/u/' + self.username + '/BigRed3/' + self.project_name + '/'
        else:
            self.prjDir = '/home/' + self.username + '/' + self.project_name + '/'
        
        self.key_filename = r''+os.path.abspath(os.path.expanduser('~/.ssh/id_rsa'))

        self.defaultqueue = self.site_dict[site_name]['defaultqueue'] 
        
        ssh = paramiko.SSHClient()
        self.ssh = ssh
        # Trust all key policy on remote host
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Retry password 3 times 
        count = 0
        maxTries = 3
        self.password = None

        # try to login using public key first
        try:
            ssh.connect(self.login_url, self.port, self.username, key_filename=self.key_filename)
            self.is_started = True
        except (paramiko.BadHostKeyException, paramiko.AuthenticationException, 
                paramiko.SSHException) as e:
            print("Public-key authorization failed (Server doesn't have your key), now try password...")


        # fall back to password if publick key failed
        if(self.is_started == False):
            while True:
                #print("Authentification fail times: " + str(count) + " of " + str(maxTries))
                #print("Please input your password on cluster:")
                self.password = password#getpass.getpass("Enter your password")
				
                try:
                    ssh.connect(self.login_url, self.port, self.username, password = self.password)
                    self.is_started = True
                    break

                except (paramiko.BadHostKeyException, paramiko.AuthenticationException, 
                        paramiko.SSHException) as e:

                    count = count+1
                    if count == maxTries:
                        print("Login failed after " + str(maxTries) +" tries")
                        print(e)
                        raise Exception("Login to %s failed after $s tries"%(site_name,str(maxTries)))
        
        # mkdir results to store job logs
        # Non-blocking call
        command = 'rm -rf ' + self.prjDir +';mkdir -p ' + self.prjDir + 'logs/'
        print(command)
        stdin, stdout, stderr = ssh.exec_command(command)
        ret = stdout.channel.recv_exit_status() # Blocking call
        if(ret != 0):
            for line in stderr:
                print(line)

        command = 'sinfo -O "partition,nodes,cpus,memory,time,available"'
        print("\n******Resource info*******:")
        stdin, stdout, stderr = ssh.exec_command(command)
        ret = stdout.channel.recv_exit_status() # Blocking call
        if(ret != 0):
            for line in stderr:
                print(line)
        else:
            for line in stdout:
                print(line)
        
        # make staging folder
        self.localdirpath = os.path.join(tempfile.gettempdir(), "cyberwater-staging")
        if not os.path.exists(self.localdirpath):
            os.makedirs(self.localdirpath)
        self.exp_input_path = os.path.join(self.localdirpath, self.project_name, "")
        if not os.path.exists(self.exp_input_path):
            os.makedirs(self.exp_input_path)

        print("launchagent is created, stagin dir is: ", self.exp_input_path)

        
        #ssh.close()
    def __del__(self):
        if(self.is_started):
            self.ssh.close()
    
    def configure_exp(self, nodes = 1, ntasks_per_node = 1, email='', 
                          walltime_in_mins=5, env_cmd='', execute_cmd=''):
        """generate a cluster job script
        
        Automatic generate a job script for user in case they know nothing about writing a HPC job script.
        
        Args:
            nodes: number of compute nodes used on cluster for this job.
            ntasks_per_node: number of tasks running on a compute node, specifically for parallel program (e.g. MPI)
            email: user's email to receive email about submission, running, error and complete
            walltime_in_mins: estimated time for this job to be executed, in mins 
            
        Returns:
            Job script file directory
            
        Examples:
            >>> obj.generateJobScript('usr@email', '', './exe')
            >>> obj.generateJobScript('usr@email', run_time = '00:10:00', '', './exe')
            >>> obj.generateJobScript(2, 10, 'usr@email', '00:10:00', 'module load python3', 'python3 your_prog')
        """
        now = datetime.now()
        file_name =  'cyberwater_' + self.site_name + '_job.sh'
        
        jobfile_path =  os.path.join(self.exp_input_path, file_name)
        # force unix-style newline: slurm forbits Windows crlf-style line termination
        f= open( jobfile_path, "w+", newline='')
        f.write("#!/bin/bash\n")
        
        f.write('#SBATCH --job-name=\"' + file_name +'\"\n')                                                                                               
        f.write('#SBATCH --output=\"logs/' + file_name + '.out.%j\"\n')

        f.write("#SBATCH --partition=" + self.defaultqueue + "\n")
        
        # if special directive is used
        if('slurm_directive_str' not in self.site_dict[self.site_name]):
            f.write('#SBATCH --nodes=' + str(nodes) + '\n')
            f.write('#SBATCH --ntasks-per-node=' + str(ntasks_per_node) + '\n')
        else:
            f.write(self.site_dict[self.site_name]['slurm_directive_str'])
            
        f.write("#SBATCH --export=ALL\n")
                
        f.write("#SBATCH --mail-type=ALL\n")        
        if (email != ''):
            f.write('#SBATCH --mail-user=' + str(email) + '\n')
        
        days, rem = divmod(walltime_in_mins, 3600)
        hours, mins = divmod(rem, 60)
        run_time = "{:0>2}:{:0>2}:{:0>2}".format(int(days),int(hours), int(mins))
        f.write('#SBATCH -t ' + run_time + '\n\n')

        f.write('## my job commands start as below:\n')
        f.write('cd ' + self.prjDir + '\n')
        
        f.write('## Environment setup are as below:\n')
        f.write(env_cmd + '\n')
        
        f.write('## Execution commands are as below:\n')
        f.write(execute_cmd + '\n')
        f.close()
        
        print("Job_file is generated: " + file_name)
        return jobfile_path
    
    def printTotals(self, transferred, toBeTransferred):
        """print real-time transfer(upload/download) status"""
        print("Transferred: {0}\tOut of: {1}".format(transferred, toBeTransferred))
    
   
    def ssh_block_command(self, commands):
        """Execute commands on cluster Login Node
        
        A blocking call to execute commands on remote login node.
        This function will autumatically cd to your prjDir. Specifically, 
        if a job script has been uploaded to a remote login node, you can 
        directly call this function with setting input commands "sbatch job_script"
        
        Args:
            commands: string
        
        Returns:
            print your commands to screen 
            
        Raises:
            None
        
        Examples:
            >>> obj.ssh_block_command('cd cyberwater; squeue -u username')
        """
        ssh = self.ssh
        commands = 'cd ' + self.prjDir + ';' + commands

        stdin, stdout, stderr = ssh.exec_command(commands, get_pty=True)
        ret = stdout.channel.recv_exit_status() # Blocking call
        if(ret != 0):
            print('return with'+ str(ret))
            print('stderr:')
            for line in stderr:
                print(line)
            raise Exception('command: '+ commands + 'return with'+ str(ret))

        print('Command executed:')
        for line in stderr:
            print(line)
        return stdout
    
        
    def run_monitor_job(self):
        """Upload a job script, submit this job, and monitor this job status
        
        Specify the job
        Get the job_ID and use the ID to monitor job status.
        
        Args:
        
        Returns:
            
        Raises:
            OSError: No suchfile
        
        """
        sftp = self.ssh.open_sftp()
        # callback: accepts the bytes transferred so far and the total bytes to be transferred
        # confirm=True: do a stat() on the file afterwards to confirm the file size
                
        for filename in os.listdir(self.exp_input_path):
            srcPath = os.path.join(self.exp_input_path, filename)
            dest = self.prjDir + filename
            print ("Copying file: %s to path: %s\n" %(srcPath, dest))
            sftp.put(srcPath, dest, callback=self.printTotals, confirm=True)

        sftp.close()

        # SubmitJob
        jobFileName =  'cyberwater_' + self.site_name + '_job.sh'
        commands = 'tar -xf packed.tar;'+ 'sbatch '+ jobFileName
        print("running remote command: " + commands)
        joboutput = self.ssh_block_command(commands) # Non-blocking call

        jobID = joboutput.read().split()[-1].decode("utf-8")

        print("Successfully Submit your job on cluster with jobID = " + str(jobID))

        print("Start Monitor Job: " + jobID)
        self.monitor_job(jobID)

        # make a tarball of the working dir
        result_tarball_name = self.project_name + '_results.tar'
        # tar -cf results.tar -C cyberwater .
        commands = 'cd ../; tar -cf ' + result_tarball_name + ' -C '+ self.project_name +' .'
        joboutput = self.ssh_block_command(commands) # Non-blocking call

        sftp = self.ssh.open_sftp()
        # callback: accepts the bytes transferred so far and the total bytes to be transferred
        # confirm=True: do a stat() on the file afterwards to confirm the file size
        srcPath = self.prjDir + '../' +result_tarball_name 
        dest = os.path.join(self.localdirpath, result_tarball_name)
        print ("Agent: job completed, copying result tarballs: %s to path: %s\n" %(srcPath, dest))

        sftp.get(srcPath, dest, callback=self.printTotals)
        sftp.close()

    
    def check_job_stat(self, jobID):
        """Check job status
        
        Get the status of a job with @job_ID.
        
        Args:
            jobID:
        
        Returns:
            status: PD, R, CG, CF
            if not the above states, return 1, means job completely finshed or no jobID found
            
        Raises:
            None.
            
        Examples:
            >>> obj.check_job_stat(jobID)
        """
        
        ssh = self.ssh

        # Execute 'squeue -u username' command
        stdin, stdout, stderr = ssh.exec_command('squeue -u ' + self.username) # Non-blocking call
        stdout.channel.recv_exit_status() # Blocking call
        #lines = stdout.read().strip().split('\n')
        for line in stdout:
            tmpJobID = line.strip().split()[0]
            if (tmpJobID == jobID):
                status = line.strip().split()[4]
                return status
        #print('check_job_stat ' + jobID + ' completed')
        return 1
    
    def monitor_job(self, jobID):
        """Monitor this job status
        
        check job status with Pending (PD), Running (R) or Nearly Completed (CG)
        This function is for internal used, and not exposed to user.
        
        Args:
            jobID: 
        
        Returns:
            
        Raises:
            None
        """
        
        while True:
            status = self.check_job_stat(jobID)
            if status == 'PD':
                print('jobid = ' + jobID + ' status = ' + status + ', wait for '+ str(self.check_pend_feq) + ' secs')
                time.sleep(self.check_pend_feq)
            elif status == 'R':
                print('jobid = ' + jobID + ' status = ' + status + ', wait for '+ str(self.check_run_feq) + ' secs')
                time.sleep(self.check_run_feq)
            elif status == 'CG':
                print('jobid = ' + jobID + ' status = ' + status + ', wait for '+ str(self.check_cg_feq) + ' secs')
                time.sleep(self.check_cg_feq) #
            elif status == 'CF':
                print('jobid = ' + jobID + ' status = ' + status + ', wait for '+ str(self.check_cg_feq) + ' secs')
                time.sleep(self.check_cg_feq) #
            elif status == 1:
                print('jobid = ' + jobID + ' status = Completed\n')
                return
            else:
                print('jobid = ' + jobID + ' status =' + status + 'Error!!!!!\n')
                return

        # return exit code
        stdin, stdout, stderr = ssh.exec_command('squeue -u ' + self.username) # Non-blocking call
        stdout.channel.recv_exit_status() # Blocking call
        #lines = stdout.read().strip().split('\n')
        for line in stdout:
            exitStatusLine = line.readline.strip()
            exitCode = int(exitStatusLine.split(':')[0])
            exitSignal = int(exitStatusLine.split(':')[1])
            if (exitCode != 0):
                raise RuntimeError('job failed with exit code(' + str(exitCode) +') and exit signal(', str(exitSignal), ')')
        #print('check_job_stat ' + jobID + ' completed')

    def upload_folder(self, inputpath):
        archivefile = os.path.join(self.exp_input_path, 'packed')
        shutil.make_archive(archivefile, 'tar', inputpath)


    def download_folder(self, outputpath):
        archivefile = os.path.join(self.localdirpath,self.project_name+'_results.tar')
        tarball = tarfile.open(archivefile, 'r')
        tarball.extractall(outputpath)
        print("All done, results saved in ", outputpath)