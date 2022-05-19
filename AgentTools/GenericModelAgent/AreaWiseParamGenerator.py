from vistrails.core.modules.vistrails_module import Module, ModuleError
from vistrails_helpers.utils.vistrail_types import STRING_TYPE, BOOLEAN_TYPE
from vistrails.core.modules.module_registry import get_module_registry
from vistrails.core.modules.basic_modules import File, Directory, PathObject
import os
import shutil
from util.DocumentUtil import DocumentUtil

class AreaWiseParamGenerator(Module):
    """
    AreaWiseParamGenerator Organizes the parameter files required for the execution of the model. 
    The user is responsible for the contents and format of the files provided.
    This module only receives the files as parameters and places them in a file with a name set by the user.
    By default, this module places the parameter files in a folder named 'Parameters'.

    :Input Ports:
        - **WD_Path:** This is the working folder provided by the MainGenerator module.
        - **Parameter_Folder_Name:** Name of the parameter folder that will be created. The default value is Parameter.
        - **File_In_x :** Path of the x-th parameter file, (x=00,01,02,...15).

    :Output Ports:
        - **Ready:** Starting flag for RunModuleAgent. The value is either *True* or *False*.
    """
    _input_ports = [('Parameter_Folder_Name', STRING_TYPE, {"optional": True}),
                    ('File_In_00', File, {"optional": True}),
                    ('File_In_01', File, {"optional": True}),
                    ('File_In_02', File, {"optional": True}),
                    ('File_In_03', File, {"optional": True}),
                    ('File_In_04', File, {"optional": True}),
                    ('File_In_05', File, {"optional": True}),
                    ('File_In_06', File, {"optional": True}),
                    ('File_In_07', File, {"optional": True}),
                    ('File_In_08', File, {"optional": True}),
                    ('File_In_09', File, {"optional": True}),
                    ('File_In_10', File, {"optional": True}),
                    ('File_In_11', File, {"optional": True}),
                    ('File_In_12', File, {"optional": True}),
                    ('File_In_13', File, {"optional": True}),
                    ('File_In_14', File, {"optional": True}),
                    ('File_In_15', File, {"optional": True}),
                    ('WD_Path', STRING_TYPE)]


    _output_ports = [('Ready', BOOLEAN_TYPE)]

    def compute(self):
        """
        The main function of AreaWiseParamGenerator module is to organize the parameter files required for the execution of the model.
        """
        # Getting Inputs -----------------------------------------------------------------------------------------------
        files_dir = self.force_get_input("WD_Path")
        params_dir = self.force_get_input("Parameter_Folder_Name")
        # Checking Inputs and provide defaults
        if files_dir is None or files_dir == "": raise Exception("WD_Path is empty or undefined.")
        if params_dir == "" or params_dir == None: params_dir = None #'Parameters'
        number_of_input_parameters = 0
        for i in range(0,16):
            temp_file_in = self.force_get_input("File_In_%02d"%i)
            if isinstance(temp_file_in, PathObject): temp_file_in = temp_file_in.name
            if temp_file_in !="" and temp_file_in is not None:
                number_of_input_parameters += 1
                if not os.path.exists(temp_file_in): raise Exception("Parameter file <%s> does not exists"%(temp_file_in))
        if number_of_input_parameters == 0: raise Exception("No parameter files were included")
        #prepare dir
        if params_dir is not None:
            if not os.path.exists(files_dir+"/"+params_dir):
                os.makedirs(files_dir+"/"+params_dir, mode=0o777)
            files_dir = os.path.join(files_dir,params_dir)

        # Start Computing ----------------------------------------------------------------------------------------------
        print("Parameters, generating")
        status = True
        for i in range(0,16):
            name = "File_In_%02d"%i
            temp = self.force_get_input(name)
            if temp == None or temp == "":
                continue
            if not isinstance(temp, str): temp = temp.name
            if temp != "" and os.path.exists(temp) and os.path.isfile(temp):
                file_name = os.path.basename(temp)
                try:
                    shutil.copyfile(temp,os.path.join(files_dir,file_name))
                except Exception as e:
                    print("Could not copy Param files to folder")
                    status = False
                    raise e
            else:
                print(("Path or File do not Exist: ", temp))
                status = False
        self.set_output("Ready", str(status))

    @classmethod
    def get_documentation(cls, docstring, module=None):
        """
        This function is to get the documentation of AreaWiseParamGenerator module

        :param docstring: A string used to document a AreaWiseParamGenerator module
        :param module: AreaWiseParamGenerator module
        :return: A invoked function from package DocumentUtil to get documentation of AreaWiseParamGenerator module
        """
        module_name = cls.__dict__['__module__'].split(".")[-1]
        return DocumentUtil.get_documentation(module_name)
def initialize(*args, **keywords):
    """
    This function is to initialize the AreaWiseParamGenerator module
    """
    reg = get_module_registry()
    reg.add_module(AreaWiseParamGenerator)