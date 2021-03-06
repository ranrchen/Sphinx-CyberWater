from vistrails.core.modules.vistrails_module import Module, ModuleError
from vistrails.core.modules.basic_modules import NotCacheable, File, Directory, String, Integer, Boolean
from vistrails.core.modules.config import IPort, OPort, CIPort, IPItem
from msm_core.msm_srv.task_cache.TaskCache import TaskCache
from datetime import datetime
import os
import shutil
import uuid
from ntpath import join
from .launchagent.ssh_agent import LaunchAgent
from .launchagent.gateway_agent import GatewayAgent
from PyQt4 import QtGui
import json
from util.OutputUtil import OutputUtil
from util.DocumentUtil import DocumentUtil


class HPC(NotCacheable, Module):
    """
    HPC module is responsible for the execution of a Model on a remote high-performance computing platform. 
    
    :Input Ports:
        :(1) Platform Selection:
            - **SSH Platform:** Platform for SSH connection, including 6 slurm-based platforms: bigred3, bridges2, bridges2-shared, stampede2, google cloud, and jetstream, and 4 bash-based platforms: sievert, rain, thunder, and lightning.
            - **Gateway Platform:** Platform for gateway connection, including bigred3, bridges2, bridges2-shared and carbonate.
            - **Customized:** Customized based-based platform for user to connect, user can choose to save their customized platform, so that this server option will be displayed in the list of SSH Platform next time.
        :(2) Credential:
            - **Username:** Username for high performance computing platform.
            - **Password:** Password for high performance computing platform.
        :(3) Project Configuration:
            - **Project Name:** The name of project created in high-performance computing platform.
            - **Email:** User will receive a notification email when job done.
            - **Estimated Runtime:** The duration of the task in the platform which user want to apply for, and the default value is 5 minus.
            - **Argument:** Argument required for the model execution. e.g., -g vic_global_file_val
            - **Result File Prefix:** The prefix of all the cells generated by the model.
            - **Point Output:**  (True/False). Check if the output is a single time-series in contrast of a distributed result in multiple files, once per cell. Default = False.
            - **Result File Separator:**  Separation character in the output files. Default = ' '
            - **Header Lines:**  Number of lines at the top of the resulting files that need to be ignored. Default = 0
        :(4) Model Source:
            - **Executable Program:** The file path of the executable program of computation model, e.g., vicNl.exe.
            - **Source Code:** The directory path of the source code of computation model,\
             if there is no available executable program running in the high-performance computing platform.\
            The output executable name set in MakeFile should be same as the folder name of source code, e.g., vicNl
        :(5) Output Datasets:
             - **Output Name:** Name of the output dataset x. (x=01,02,03,....,20)
             - **File Pos:** Column index in the result files for the dataset x. (x=01,02,03,....,20)
        :Ready_List: Connect the output of ForcingDataFileGenerator, AreaWiseParamGenerator and InitialStateFileGenerator if it exists.
        :WD_Path: WD_Path output port of the MainGenerator. This is the directory where the simulation files are saved.
        :DataSet_Class: DataSet_Class output port of the MainGenerator.
    
    :Output Ports:
        - **Outputx:**  Output dataset x. (x=01,02,03,....,20)
    """
    taskCache = TaskCache()
    WRITE_EMPTY_VALUE = None

    siteFile = os.path.dirname(os.path.abspath(__file__)) + "/launchagent/resources/site_dict.json"
    with open(siteFile,"r") as f:
        siteList = json.load(f)
        sshList = list(siteList["ssh_agent"]["sites"].keys())
        gatewayList = list(siteList["gateway_agent"]["sites"].keys())
        slurmList = ["bigred3", "gcp", "jetstream", "bridges2", "bridges2-shared", "stampede2"]
        sshList.remove("Customized")
        for i in range(len(sshList)):
            if sshList[i] == 'gcp':
                sshList[i] = "Google Cloud"
            elif sshList[i] in slurmList:
                sshList[i] = sshList[i].capitalize()
        for j in range(len(gatewayList)):
            gatewayList[j] = gatewayList[j].capitalize()

    _input_ports = [CIPort("(1) Platform Selection", [String, String, String], entry_types=["enum", "enum", "query"],
                           values=[sshList,gatewayList,None],
                           optional=True,
                           labels=["<b>SSH Platform</b>", "<b>Gateway Platform</b>", "<b>Customized</b>"]),
                    CIPort("(2) Credential", [String], optional=True, labels=["<b>Username</b>"]),
                    CIPort("(4) Model Source", [File, Directory], optional=True,
                           labels=["<b>Executable Program</b>", "<b>Source Code</b>"]),
                    CIPort("(3) Project Configuration", [String, String, Integer, String, String,String,Boolean,String,Integer], optional=True,
                           defaults=["CyberWater", "[User's Email Address]", "5", None, None,"results",False,' ',0],
                           labels=["<b>Project Name</b>", "<b>Email</b>", "<b>Estimated Runtime</b>", "<b>Argument</b>",
                                   "<b>Result_File_Prefix/Name</b>","<b>Result Folder","<b>Point Output</b>","<b>Result File Separator</b>","<b>Header Lines</b>"]),
                    IPort("Ready_List", Boolean),
                    IPort("WD_Path", String),
                    IPort("DataSet_Class", String),
                    CIPort("(5) Output Datasets", [String,String], optional=True, labels=["<b>File Position</b>","<b>Output Name</b>"])]
    _output_ports = [('Output01', String),
                     ('Output02', String, {"optional": True}),
                     ('Output03', String, {"optional": True}),
                     ('Output04', String, {"optional": True}),
                     ('Output05', String, {"optional": True}),
                     ('Output06', String, {"optional": True}),
                     ('Output07', String, {"optional": True}),
                     ('Output08', String, {"optional": True}),
                     ('Output09', String, {"optional": True}),
                     ('Output10', String, {"optional": True}),
                     ('Output11', String, {"optional": True}),
                     ('Output12', String, {"optional": True}),
                     ('Output13', String, {"optional": True}),
                     ('Output14', String, {"optional": True}),
                     ('Output15', String, {"optional": True}),
                     ('Output16', String, {"optional": True}),
                     ('Output17', String, {"optional": True}),
                     ('Output18', String, {"optional": True}),
                     ('Output19', String, {"optional": True}),
                     ('Output20', String, {"optional": True})]

    def compute(self):
        """
        The main function of HPC module is to execute  a model on a remote high-performance computing platform
        """
        # Getting Input
        output = OutputUtil()
        dd = None
        ret = []

        # Getting Credential
        username = self.force_get_input("(2) Credential")
        title = "Credential Dialog"
        label = "Password for " + username

        (result, ok) = QtGui.QInputDialog.getText(None, title, label, QtGui.QLineEdit.Password, None)
        if not ok:
            raise ModuleError(self, "Canceled")
        password = result


        # Getting Platform
        p = self.force_get_input("(1) Platform Selection")
        sshSite = p[0]
        Gateway = p[1]
        Customized = p[2]

        # Connecting with previous modules
        Dataset_in = self.force_get_input("DataSet_Class")
        Ready_List = self.force_get_input_list("Ready_List")
        Path = self.force_get_input("WD_Path")

        # Getting Model Engine
        model = self.force_get_input("(4) Model Source")
        exe = model[0].name
        obj = model[1].name

        # Getting Project Configuration
        projectconf = self.force_get_input("(3) Project Configuration")
        projectname = projectconf[0]
        email = projectconf[1]
        runtime = projectconf[2]
        arg = projectconf[3]
        file_name = projectconf[4]
        result_folder = projectconf[5]
        point_output = projectconf[6]
        separator = projectconf[7]
        number_of_header_lines = projectconf[8]

        # Checking Inputs and provide defaults
        if Ready_List is None or Ready_List == "": raise Exception("Ready_List is empty or undefined.")
        for single_ready in Ready_List:
            if not single_ready:
                raise Exception("Some of the components are not ready.")
        # Start Computing ----------------------------------------------------------------------------------------------
        exe_str = os.path.basename(exe)
        obj_str = os.path.basename(obj) # The folder name should be the output name in MakeFile
        files_dir = Path
        if obj:
            shutil.copytree(obj, os.path.join(files_dir, obj_str))
        elif exe:
            shutil.copy(exe, os.path.join(files_dir, exe_str))

        isSlurm = False
        if sshSite in ["Bigred3", "Google Cloud", "Jetstream", "Bridges2", "Bridges2-shared", "Stampede2"]:
            isSlurm = True

        if Customized and not Gateway and not sshSite:
            try:
                agent = LaunchAgent(site_name="Customized",login_url=Customized, project_name=projectname, username=username, passwd=password,sched_env='bash')
            except:
                print("Authentication fails, username or password isn't correct")
                result = QtGui.QMessageBox.critical(None, "Authentication Fails","Username or password isn't correct",QtGui.QMessageBox.Ok)
                return
            (result, ok) = QtGui.QInputDialog.getText(None, "Offer to save server", "<b>Do you want CyberWater VisTrails to save this server?</b> \
            (If yes, please enter an alias for this server)", QtGui.QLineEdit.Normal,Customized.split('.')[0])
            if ok:
                if not str(result) in self.sshList:
                    self.siteList["ssh_agent"]["sites"][str(result)] = {
                    "sched_env": "bash",
                    "login_url": Customized}
                    try:
                        with open(self.siteFile,"w") as f:
                            json.dump(self.siteList,f)
                    except:
                        print("Fail to update the dictionary of sites")
                        result = QtGui.QMessageBox.critical(None, "Update Fails","Fail to update the dictionary of sites", QtGui.QMessageBox.Ok)
                else:
                    result = QtGui.QMessageBox.warning(None,"Warning", "This server already exists in the list", QtGui.QMessageBox.Ok)

        if sshSite and isSlurm:
            # sshSite convertion
            sshSite = sshSite.lower()
            if sshSite == "google cloud":
                sshSite = "gcp"
            try:
                # launch agent for ssh
                agent = LaunchAgent(site_name=sshSite, project_name=projectname, username=username, passwd=password)
            except:
                print("Authentication fails, username or password isn't correct")
                result = QtGui.QMessageBox.critical(None, "Authentication Fails", "Username or password isn't correct",QtGui.QMessageBox.Ok)
                return
        elif not isSlurm and sshSite:
            try:
                agent = LaunchAgent(site_name=sshSite, project_name=projectname, username=username, passwd=password,sched_env='bash')
            except:
                print("Authentication fails, username or password isn't correct")
                result = QtGui.QMessageBox.critical(None, "Authentication Fails", "Username or password isn't correct",QtGui.QMessageBox.Ok)
                return
        if Gateway:
            # print("Gateway")
            Gateway = Gateway.lower()
            # launch agent for gateway
            try:
                agent = GatewayAgent(gateway_username=username, gateway_passwd=password,exp_name=projectname, site_name=Gateway)
            except:
                print("Authentication fails, username or password isn't correct")
                result = QtGui.QMessageBox.critical(None, "Authentication Fails", "Username or password isn't correct", QtGui.QMessageBox.Ok)
                return

        inputs = ''
        inputs += str(Dataset_in)
        inputs += str(Ready_List)
        if Path:
            inputs += Path
        if arg:
            inputs += arg
        if exe:
            inputs += exe
        if obj:
            inputs += obj
        if file_name:
            inputs += file_name
        inputs += str(point_output)
        inputs += str(number_of_header_lines)
        inputs += str(separator)

        input_identification = inputs + str(datetime.now())  # TODO delete the datetime.now addition
        input_identification = uuid.uuid5(uuid.NAMESPACE_DNS, input_identification)
        input_identification = str(input_identification)

        # Getting information of output datasets:
        outputDatasetInfo = self.force_get_input_list("(5) Output Datasets")
        # Getting output name list
        self.Output_name = []
        # Getting file position list
        self.Position_list = []
        for pl, on in outputDatasetInfo:
            self.Output_name.append(on)
            self.Position_list.append(pl)

        dd = output.check_dimensions(Dataset_in, dd)

        task_id = input_identification
        cached_result = self.taskCache.get_task_cached_result_dataset_names_by_port(task_id)

        if cached_result is not None:
            # return cached_result[]
            for i in range(1, len(cached_result) + 1):
                temp = 'Output0' + str(i)
                self.set_output(temp, cached_result[self.Output_name[i - 1]])

        else:
            if not os.path.exists(files_dir + "/" + result_folder):
                os.makedirs(files_dir + "/" + result_folder, mode=0o777)

            # Prepare execution script, run.sh
            checkWords = ("$1","$2","$3")
            repWords = (arg,exe_str,obj_str)
            print(repWords)
            with open(os.path.dirname(os.path.abspath(__file__))+"/launchagent/resources/run.sh","r") as f_old:
                with open(os.path.join(files_dir, 'run.sh'),'w') as f_new:
                    for line in f_old:
                        for check, rep in zip(checkWords,repWords):
                            line = line.replace(check,rep)
                        f_new.write(line)
            # upload folders:
            print(("Files being uploaded", files_dir))
            agent.upload_folder(files_dir)

            if sshSite:
                if isSlurm:
                    job_id = agent.configure_slurm_job(nodes=1, ntasks_per_node=1,
                                    email=email, walltime_in_mins=runtime, execute_script=os.path.join(files_dir, 'run.sh'))
                    agent.run_monitor_job(job_id)
                else:
                    job_id = agent.configure_bash_job(execute_script=os.path.join(files_dir, 'run.sh'))
                    agent.launch_job(job_id)

            elif Gateway:
                agent.configure_exp(nodes=1, ntasks_per_node=1,
                                    email=email, walltime_in_mins=runtime)
                QtGui.QMessageBox.about(None, "Airavata Portal", "Web-based Interface of Gateway:<a href='https://cyberwater.scigap.org/'>https://cyberwater.scigap.org/</a>")
                agent.run_monitor_job()

            elif Customized:
                job_id = agent.configure_bash_job(execute_script=os.path.join(files_dir, 'run.sh'))
                agent.launch_job(job_id)

            print("Preparing outputs:")
            output_folder = join(files_dir,result_folder)
            # Download the outputfile
            agent.download_folder(files_dir)
            module_name = self.__class__.__name__
            outputs,ret = output.save_outputs(output_folder, self.Output_name, self.Position_list, file_name, input_identification, point_output, separator, number_of_header_lines,module_name, ret, dd)

            for i in range(1, len(outputs) + 1):
                temp = 'Output%02d' % (i)
                self.set_output(temp, ret[i - 1])

    @classmethod
    def get_documentation(cls, docstring, module=None):
        """
        This function is to get the documentation of HPC module

        :param docstring: A string used to document a HPC module
        :param module: HPC module
        :return: A invoked function from package DocumentUtil to get documentation of HPC module
        """
        module_name = cls.__dict__['__module__'].split(".")[-1]
        return DocumentUtil.get_documentation(module_name)