#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep  5 12:00:04 2019

@author: fuyuan
"""

import paramiko, getpass
import time, sys, logging

def printTotals(transferred, toBeTransferred):
    print "Transferred: {0}\tOut of: {1}".format(transferred, toBeTransferred)

def sftp_put_file(hostname, port, username, password, src, dst):
    ssh = paramiko.client.SSHClient()
    ssh.load_system_host_keys()
    ssh.connect(hostname, port=port, username=username, password=password)
    print (" Connecting to %s \n with username=%s..." %(hostname, username))
    # Using the SSH client, create a SFTP client
    sftp = ssh.open_sftp()
    # Keep a reference to the SSH client in the SFTP client as to prevent the 
    # former being garbage collected an d the connection from being closed.
    sftp.sshclient = ssh
    # callback: accepts the bytes transferred so far and the total bytes to be transferred
    # confirm=True: do a stat() on the file afterwards to confirm the file size
    sftp.put(src, dst, callback=printTotals, confirm=True)
    print ("Copying file: %s to path: %s\n" %(src, dst))
    sftp.close()
    ssh.close()

def sftp_get_file(hostname, port, username, password, src, dst):
    ssh = paramiko.client.SSHClient()
    ssh.load_system_host_keys()
    ssh.connect(hostname, port=port, username=username, password=password)
    print (" Connecting to %s \n with username=%s..." %(hostname, username))
    # Using the SSH client, create a SFTP client
    sftp = ssh.open_sftp()
    # Keep a reference to the SSH client in the SFTP client as to prevent the 
    # former being garbage collected an d the connection from being closed.
    sftp.sshclient = ssh
    # callback: accepts the bytes transferred so far and the total bytes to be transferred
    # confirm=True: do a stat() on the file afterwards to confirm the file size
    sftp.get(src, dst, callback=printTotals)
    print ("Copying file: %s to path: %s\n" %(src, dst))
    sftp.close()
    ssh.close()

def ssh_block_command(command, hostname, port, username, password):
    ssh = paramiko.client.SSHClient()
    ssh.load_system_host_keys()
    print (" Connecting to %s \n with username=%s..." %(hostname,username))
    ssh.connect(hostname, port=port, username=username, password=password)
    # Non-blocking call
    stdin, stdout, stderr = ssh.exec_command(command)
    # Blocking call
    stdout.channel.recv_exit_status()
    print(" Command executed!\n " + command + '\n')
    ssh.close()

print("Prepare connecting to Big Red II ... ")
hostname = "bigred2.uits.iu.edu"
print("Please input your user name on BigRed II:")
username = str(raw_input()) # raw_input() returns the verbatim string entered by the user.
print("Please input your password on Bridges:")
password = getpass.getpass("Enter key:")
port = 22 #default ssh port is 22
bigred2_home_dir = '/N/u/' + username + '/BigRed2/cyberwater/'
local_mac_dir = '/home/fuyuan/Workspace/Cyberwater/paramiko_test/'

client = paramiko.client.SSHClient()
# Trust all key policy on remote host
client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())

count = 0
maxTries = 3
while True:
    try:
        client.connect(hostname, port=port, username=username, password=password)
    except (paramiko.BadHostKeyException, paramiko.AuthenticationException, paramiko.SSHException) as e:
        print("Authentification fail times:", count)
        print("Please input your password on BR2 again:")
        password = getpass.getpass("Enter key:")
#           client.connect(hostname, port=port, username=username, password=password)
        count = count+1
        if count == maxTries:
            print(e)
            quit()
        continue
    break

# Upload in.csv
localFile = 'in.csv'
localFilePath = './' + localFile
remoteFilePath = bigred2_home_dir + localFile
sftp_put_file(hostname, port, username, password, localFilePath, remoteFilePath)

# Uplaod prog
localFile = 'matrix_add.py'
localFilePath = './' + localFile
remoteFilePath = bigred2_home_dir + localFile
sftp_put_file(hostname, port, username, password, localFilePath, remoteFilePath)

# Execute prog and wait for it to complete
# command = 'module load python3; cd /home/qoofyk/cyberwater; python3 matrix_add.py'
# read command from file
f = open("./command_br2", "r")
command =  f.read()
f.close()
ssh_block_command(command, hostname, port, username, password)

# Download out.csv
remoteFile = 'out.csv'
remoteFilePath = bigred2_home_dir + remoteFile
localFilePath = local_mac_dir + remoteFile
sftp_get_file(hostname, port, username, password, remoteFilePath, localFilePath)

client.close()
print("Simple Workflow complete on BR2!")