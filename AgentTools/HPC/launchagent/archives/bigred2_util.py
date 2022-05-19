#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 26 21:32:07 2019

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