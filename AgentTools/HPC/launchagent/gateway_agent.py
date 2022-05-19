#  Licensed to the Apache Software Foundation (ASF) under one or more
#  contributor license agreements.  See the NOTICE file distributed with
#  this work for additional information regarding copyright ownership.
#  The ASF licenses this file to You under the Apache License, Version 2.0
#  (the "License"); you may not use this file except in compliance with
#  the License.  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import logging
import time
import json

from airavata_sdk.clients.keycloak_token_fetcher import Authenticator
from airavata_sdk.clients.api_server_client import APIServerClient
from airavata_sdk.clients.utils.api_server_client_util import APIServerClientUtil
from airavata_sdk.clients.credential_store_client import CredentialStoreClient
from airavata_sdk.clients.utils.data_model_creation_util import DataModelCreationUtil
from airavata_sdk.clients.sftp_file_handling_client import SFTPConnector

from airavata.model.workspace.ttypes import Gateway, Notification, Project
from airavata.model.experiment.ttypes import ExperimentModel, ExperimentType, UserConfigurationDataModel
from airavata.model.scheduling.ttypes import ComputationalResourceSchedulingModel
from airavata.model.data.replica.ttypes import DataProductModel, DataProductType, DataReplicaLocationModel, \
    ReplicaLocationCategory, ReplicaPersistentType

from airavata.model.application.io.ttypes import InputDataObjectType
from airavata.model.appcatalog.groupresourceprofile.ttypes import GroupResourceProfile
from airavata.api.error.ttypes import TException, InvalidRequestException, AiravataSystemException, \
    AiravataClientException, AuthorizationException

from airavata_sdk.transport.settings import GatewaySettings

import os
import os.path as path
import shutil
from distutils.dir_util import copy_tree, remove_tree
import tarfile, zipfile
import tempfile
from datetime import datetime

from . import version

_print_header="--GatewayAgent:"

def get_supported_sites():
    siteFile = os.path.dirname(os.path.abspath(__file__)) + "/resources/site_dict.json"

    f = open(siteFile)
    site_dict = json.load(f)["gateway_agent"]["sites"]
    f.close()
    return [ x.encode('UTF8') for x in list(site_dict.keys()) ]

def _dos2unix(infile, outfile):
    # replacement strings
    WINDOWS_LINE_ENDING = b'\r\n'
    UNIX_LINE_ENDING = b'\n'

    with open(infile, 'rb') as open_file:
        content = open_file.read()
        
    content = content.replace(WINDOWS_LINE_ENDING, UNIX_LINE_ENDING)

    with open(outfile, 'wb') as open_file:
        open_file.write(content)

class GatewayAgent():
    """ Launch agent: use airavata gateway api to offload local computation.

    local files will be saved in C:/temp/cyberwater-staging-gateway/exp_name,
    local files will then be uploaded to HPC, and being processed, 
    the remote working directory will be first downloaded as a tarball at at: C:/temp/cyberwater-staging-gateway/YYYYMMDD-HHMM,
    then extract to the user-defined download-folder.
    """

    def __init__(self, gateway_username='fengggli2', gateway_passwd= None, exp_name = "test-exp-name", site_name = "karst"):
        """ Construct a gatewayAgent

        Args:
            gateway_username (str, optional): The user name used to login to cyberwater.scigap.org. Defaults to 'fengggli2'.
            gateway_passwd (str, optional): The corresponding password. Defaults to None
            exp_name (str, optional): name for this experiment. Defaults to "test-exp-name".
            site_name (str, optional): hpc resource to use, refer to site_dict.json for supported resources. Defaults to "karst".
        
        Examples:
            >>> agent = GatewayAgent("someusername", "somepassword", "cyberwater", "bridges-LM")

        """

        print(("Initializing ssh-agent, version=" +  version.__version__))

        self.exp_config = {}
        lib_dir = path.dirname(path.abspath(__file__))
        temp_dir =  "C:\\temp"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        print(('libdir' + lib_dir +',file:', __file__))
        siteFile = path.join(lib_dir,"resources", "site_dict.json")
        with open(siteFile) as f:
            gateway_conf = json.load(f)["gateway_agent"]
            self.site_dict = gateway_conf["sites"]
            self.gateway_id = gateway_conf["gateway_id"]
            self.storage_id = gateway_conf["storage_id"]

        self.logger = logging.getLogger(__name__)

        self.logger.setLevel(logging.DEBUG)
        self.app_name = "gateway-agent" # this is the application name registered by Feng Li in advance at gateway

        configFile = path.join(lib_dir, "resources", "settings-feng.ini")

        self.user_name = gateway_username
        print(("Using username (" + self.user_name + ') for ssh session'))

        password = gateway_passwd
        self.gateway_resource = self.site_dict[site_name] 

        authenticator = Authenticator(configFile)

        print(("Using configure file at:", configFile))
        token = authenticator.get_token_and_user_info_password_flow(username=self.user_name, password=password,
                                                                    gateway_id=self.gateway_id)

        api_server_client = APIServerClient(configFile)

        airavata_util = APIServerClientUtil(configFile, username=self.user_name, password=password, gateway_id=self.gateway_id)
        data_model_client = DataModelCreationUtil(configFile,
                                                username=self.user_name,
                                                password=password,
                                                gateway_id=self.gateway_id)

        credential_store_client = CredentialStoreClient(configFile)


        self.gateway_settings = GatewaySettings(configFile)

        # make staging folder
        self.localdirpath = path.join(temp_dir, "cyberwater-staging-gateway")
        if not path.exists(self.localdirpath):
            os.makedirs(self.localdirpath)


        self.api_server_client = api_server_client
        self.data_model_client = data_model_client
        self.airavata_util = airavata_util
        self.credential_store_client = credential_store_client 
        self.token = token
        self.exp_name = exp_name

        self.exp_input_path = path.join(self.localdirpath, self.exp_name, "")
        if path.exists(self.exp_input_path):
            remove_tree(self.exp_input_path)
        os.makedirs(self.exp_input_path)

        executionId = airavata_util.get_execution_id(self.app_name)

        self.experiment_time_str=datetime.now().strftime("%Y%m%d-%H%M")

        print((_print_header, " experiment ", exp_name, "input folder will be copied to ", self.exp_input_path))
        print((_print_header, " execution_id: %s" % (executionId) ))
        #print(_print_header,  "results from hpc  will be copied to ", self.exp_input_path)

    
    def configure_exp(self, nodes = 1, ntasks_per_node = 1, email='', 
                          walltime_in_mins= 5):
        """ Configure a gateway experiment

        Args:
            nodes (int, optional): [description]. Defaults to 1.
            ntasks_per_node (int, optional): [description]. Defaults to 1.
            email (str, optional): [description]. Defaults to ''.
            walltime_in_mins (int, optional): [description]. Defaults to 5.
        """
        self.exp_config['nodes'] = nodes
        self.exp_config['ntasks_per_node'] = ntasks_per_node 
        self.exp_config['walltime_in_mins'] = walltime_in_mins 
        self.exp_config['email'] = email 
        print(("Agent configured:", self.exp_config))

    def run_monitor_job(self):
        """ Submit the experiment and wait until it finishes

        This is a blocking call
        """

        good_status_dict = {0: "Created", 4: "Running", 7: "Completed"}
        bad_status_dict = {8: "Experiment Setup failed (resource profile)"}

        api_server_client = self.api_server_client
        data_model_client = self.data_model_client
        airavata_util = self.airavata_util
        credential_store_client = self.credential_store_client
        token = self.token
        localdirpath = self.localdirpath
        exp_name = self.exp_name
        app_name = self.app_name
        gateway_id = self.gateway_id

        executionId = airavata_util.get_execution_id(app_name)

        # create Experiment data Model
        experiment = data_model_client.get_experiment_data_model_for_single_application(
            project_name="Default Project",
            application_name=self.app_name,
            experiment_name=self.exp_name,
            description="Testing")

        # remote path of experiments results (relative to Project foler)
        experiment_remote_path_str = executionId + '/' +self.experiment_time_str

        driverFile = path.dirname(path.abspath(__file__)) + "/driver.sh"
        outfile_driver = path.join(self.exp_input_path, "driver.sh")

        _dos2unix(infile = driverFile, outfile= outfile_driver)

        sftp_connector = SFTPConnector(host="cyberwater.scigap.org", port=9000, username=self.user_name,
                                    password=token.accessToken)
        # will be /projectname/experiment_name/ in sftp server
        path_suffix = sftp_connector.upload_files(self.exp_input_path,
                                                "Default_Project",
                                                experiment_remote_path_str)

        # generate path for gateway that is
        remotepath = self.gateway_settings.GATEWAY_DATA_STORE_DIR + path_suffix

        group_resource_profile_name = self.gateway_resource["group_resource_profile_name"]
        computation_resource_name= self.gateway_resource["url"]
        queue_name = self.gateway_resource["queue_name"] 

        print(("Using group_reource profile:" + group_resource_profile_name + ", with resource name:" + computation_resource_name))
        experiment = data_model_client.configure_computation_resource_scheduling(experiment_model=experiment,
                                                                                computation_resource_name=computation_resource_name,
                                                                                group_resource_profile_name=group_resource_profile_name,
                                                                                storageId=self.storage_id,
                                                                                node_count=self.exp_config['nodes'],
                                                                                total_cpu_count=self.exp_config['nodes'] * self.exp_config['ntasks_per_node'],
                                                                                wall_time_limit=self.exp_config['walltime_in_mins'],
                                                                                queue_name=queue_name,
                                                                                experiment_dir_path=remotepath)
        # I only need to register the run.sh file
        input_files = []
        for input_file_name in ['driver.sh', 'packed.tar']:
        #for input_file_name in ['driver.sh']:
            data_uri = data_model_client.register_input_file(file_identifier=input_file_name,
                                                            storage_name='pgadev.scigap.org',
                                                            storageId=self.storage_id,
                                                            input_file_name=input_file_name,
                                                            uploaded_storage_path=remotepath)

            print(("registering uri:", data_uri))
            input_files.append(data_uri)

        experiment = data_model_client.configure_input_and_outputs(experiment, input_files=input_files,
                                                                application_name=self.app_name)

        # create experiment
        ex_id = api_server_client.create_experiment(token, "cyberwater", experiment)

        # launch experiment
        api_server_client.launch_experiment(token, ex_id, "cyberwater")

        status = api_server_client.get_experiment_status(token, ex_id);

        if status is not None:
            print(("Initial state: " + good_status_dict[status.state]))

        while status.state in good_status_dict and status.state <= 6:
            status = api_server_client.get_experiment_status(token,
                                                            ex_id);
            time.sleep(15)
            print(("Current State: %s" % (good_status_dict[status.state])))
        
        if status.state in bad_status_dict:
            raise RuntimeError('Experiment get bad status %d: %s' %(status.state, bad_status_dict[status.state]))

        print("Completed!")

        # pysftp will try to create the Default_project
        result_dir = path.join(self.localdirpath,'Default_Project')
        if(path.isdir(result_dir)):
            remove_tree(result_dir)

        # this will save results to localdirpath/YYYYMMDD-HHMM
        sftp_connector.download_files(localdirpath.replace('\\','/'), "Default_Project", experiment_remote_path_str)
        print((_print_header, "Downloading tarball of remote working directory and logs, saved to:", path.join(self.localdirpath, self.experiment_time_str)))
    
    def upload_folder(self, inputpath):
        """ Upload local folder to remote working directory

        Args:
            inputpath (Path): path of local folder to be uploaded 

        Examples:
            >>> agent.upload_folder('tests/matrix/')

        """

        archivefile = path.join(self.exp_input_path, 'packed')
        shutil.make_archive(archivefile, 'tar', inputpath)


    def download_folder(self, outputpath):
        """ Download all contents from remote remote directory to local folder

        This will recursively copy files/folders from remote working directory

        Args:
            outputpath (path): directory path where remote files will be copied to 
        """
        srcPath = path.join(self.localdirpath, self.experiment_time_str)
        archivefile = path.join(srcPath, 'agent_results.zip')
        tarball = zipfile.ZipFile(archivefile, 'r')
        tarball.extractall(outputpath)
        tarball.close()
        print((_print_header, "extract results from tarball to ", outputpath))