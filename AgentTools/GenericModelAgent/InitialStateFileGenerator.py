from vistrails.core.modules.vistrails_module import Module, ModuleError
from vistrails_helpers.utils.vistrail_types import STRING_TYPE, BOOLEAN_TYPE
from vistrails.core.modules.module_registry import get_module_registry
from vistrails.core.modules.basic_modules import File
from util.DocumentUtil import DocumentUtil
import os
import shutil

class InitialStateFileGenerator(Module):
    """
    InitialStateFileGenerator is an optional module to organizes the initial state data of a generic simulation.
    The initial state files are not always required for the execution of some models.

    :Input Ports:
        - **WD_Path:** This is the working folder provided by the MainGenerator module.
        - **Init_State_Folder_Name:** Name of the initial state folder that will be created. If left empty, the state files will be saved in the working directory.
        - **File_In_x:** Path of the x-th initial state file, (x=0,1,2,...,9).
    
    :Output Ports:
        - **Ready:** Starting flag for RunModuleAgent. The value is either *True* or *False*.
    """
    _input_ports = [('Init_State_Folder_Name', STRING_TYPE, {"optional": True}),
                    ('WD_Path', STRING_TYPE),
                    ('File_In_0', File, {"optional": True}),
                    ('File_In_1', File, {"optional": True}),
                    ('File_In_2', File, {"optional": True}),
                    ('File_In_3', File, {"optional": True}),
                    ('File_In_4', File, {"optional": True}),
                    ('File_In_5', File, {"optional": True}),
                    ('File_In_6', File, {"optional": True}),
                    ('File_In_7', File, {"optional": True}),
                    ('File_In_8', File, {"optional": True}),
                    ('File_In_9', File, {"optional": True}),
                    ('04_Ready', BOOLEAN_TYPE, {"optional": True})]
    _output_ports = [('Ready', BOOLEAN_TYPE)]

    def compute(self):
        """
        The main function of InitialStateFileGenerator module is to organize the initial state data of a generic simulation.
        """
        files_dir = self.force_get_input("WD_Path")
        # params_dir="params"
        initial_state_dir=self.force_get_input("Init_State_Folder_Name")
        # Checking Inputs and provide defaults
        self.dd = None
        if files_dir is None or files_dir == "": raise Exception("WD_Path is empty or undefined.")
        # remove exist dir
        try:
            if initial_state_dir=="" or initial_state_dir==None:
                initial_state_dir = files_dir
            else:
                initial_state_dir = os.path.join(files_dir, initial_state_dir)
                shutil.rmtree(initial_state_dir, ignore_errors=True)
                os.makedirs(initial_state_dir, mode=0777)
        except Exception as e:
            print "Could not delete the folders"
            raise e

        print "state files, generating"

        ready_sign = True
        for i in xrange(0,10):
            name = "File_In_"+str(i)
            temp = self.force_get_input(name)
            if temp == None or temp == "":
                continue
            if not isinstance(temp, str): temp = temp.name
            if temp != "" and os.path.exists(temp) and os.path.isfile(temp):
                file_name = os.path.basename(temp)
                initial_state_file = initial_state_dir+"/"+file_name
                try:
                    shutil.copyfile(temp,initial_state_file)
                except Exception as e:
                    print "Could not copy initial state files to folder"
                    ready_sign = False
                    raise e
            else:
                print "Path or File not Exist"
                ready_sign = False

        self.set_output("Ready", str(ready_sign))

    @classmethod
    def get_documentation(cls, docstring, module=None):
        """
        This function is to get the documentation of InitialStateFileGenerator module

        :param docstring: A string used to document a InitialStateFileGenerator module
        :param module: InitialStateFileGenerator module
        :return: A invoked function from package DocumentUtil to get documentation of InitialStateFileGenerator module
        """
        module_name = cls.__dict__['__module__'].split(".")[-1]
        return DocumentUtil.get_documentation(module_name)

def initialize(*args, **keywords):
    """
    This function is to initialize the InitialStateFileGenerator module
    """
    reg = get_module_registry()
    reg.add_module(InitialStateFileGenerator)