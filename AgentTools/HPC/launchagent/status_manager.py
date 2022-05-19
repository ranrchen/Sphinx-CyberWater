import os
import json
#import pandas as pd
from datetime import datetime

_supported_agent_types = {'slurm', 'gateway', 'shell'}

class StatusManager(object):
    """Manage all job submitted from slurm, gateway, shell based launchAgent
    """
    def __init__(self, db_file_path, ignore_previous=False):
        """Initialization of the status database file.

        Args:
            db_file_path (str): a path to store the global status file
            ignore_previous (bool): an option to start fresh
        """
        self._db_file_path = db_file_path
        if ignore_previous == False and os.path.exists(db_file_path):
            # if there is old state file
            with open(db_file_path) as f:
                try:
                    self._job_stat = json.load(f)
                except ValueError:
                    print(("ERROR: StateFile %s corrupted or empty, delete it!" % db_file_path))
                    raise
                    
        else:
            self._job_stat = {}
            self._job_stat["job_list"] = []
            self._job_stat["nr_allocated_jobs"] = 0
    
    def add_entry(self, agent_type, site_name):
        """Allocate a slot in the db and update status.

        Args:
            agent_type (str): either 'slurm' or 'bash' 
            site_name (str): site names defined in site_dict.json file

        Returns:
            int: job_id for this entry
        """
        job_id = self._job_stat["nr_allocated_jobs"]
        created_time = datetime.now().strftime("%Y%m%d-%H%M")
        job_entry = {'JobID': job_id, 'AgentType': agent_type, 'SiteName': site_name, 'JobStatus': 'CREATED', 'CreatedTime': created_time, 'RemoteJobID': -1}
        self._job_stat["job_list"].append(job_entry)
        self._job_stat["nr_allocated_jobs"] += 1

        self._persist()

        return job_id 
    
    def get_entry(self, job_id):
        """Return the status of a job

        Args:
            job_id (int): the jobid returned by add_entry
        
        Return:
            dict: a dictory that contains the job information:
            
        Examples:
            >>> print(manager.get_entry(id))
            {'JobID': 13, 'AgentType': 'slurm', 'JobStatus': 'RUNNING', 'CreatedTime': '20210510-2231', 'RemoteJobID': 12387}

            The JobStatus can be: 'CREATED', 'PENDING', 'RUNNING', 'COMPLETED','FAILED'
        """
        for job_entry in self._job_stat["job_list"]:
            if job_entry["JobID"] ==  job_id:
                return job_entry

        raise RuntimeError("jobid %d doesn's exist, check state file at %s" % (job_id, self._db_file_path))

    def update_entry(self, job_id, field_name, value):
        """Update specific field of an entry in the catalog

        Args:
            job_id ([type]): [description]
            field_name ([type]): [description]
            value ([type]): [description]
        """

        for job_entry in self._job_stat["job_list"]:
            if job_entry["JobID"] ==  job_id:
                job_entry[field_name] = value
                self._persist()
                return

        raise RuntimeError("jobid %d doesn's exist, check state file at %s" % (job_id, self._db_file_path))
    
    def print_all_status(self):
        """Print status to console
        """

        all_entries = json.dumps(self._job_stat, indent = 4)
        print(all_entries)
    
    def _persist(self):
        """Persist current state to disk
        """
        with open(self._db_file_path, 'w') as f:
            json.dump(self._job_stat, f, sort_keys=False, indent = 4)


    
        