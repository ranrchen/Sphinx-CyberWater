from vistrails.core.modules.vistrails_module import Module, ModuleError
from vistrails_helpers.utils.vistrail_types import STRING_TYPE
from vistrails.core.modules.module_registry import get_module_registry
from vistrails.core.modules.basic_modules import File, Directory, Variant
import os
import shutil
from vistrails.core.modules.config import IPort, CIPort, OPort
from vistrails.core.modules.basic_modules import NotCacheable, String, Boolean, Integer
from util.DocumentUtil import DocumentUtil


class MainGenerator(Module):
    """
     The MainGenerator module is the first component of the Generic Model Agent tools.
     This component is responsible for setting up the folder where the simulation will be performed.
     It receives all the forcing datasets as inputs. The order at which they are added matters,
     since the final forcing files will display the data in the same order:
     first Dataset_01, then Dataset_02, and so on.
     The purpose of the Generic Model Agent tools is to enable the integration of new Models into the
     CyberWater environment. Therefore, users are expected to be highly knowledgeable about the
     details of their own models if they want to perform an integration with the Generic tools.

     :Input Ports:
         - **01_Path:** Path of the folder where the files of the simulation will be created.
         - **02_GPF:** Path of the main configuration (global parameter) file for the simulation.
         - **03_Override?:** Flag on whether to override the original working directory, The value is either *True* or *False*.
         - **04_Ready:** Ready signal from precedent-connected modules, The value is either *True* or *False*,
         - **Dataset_x:** Dataset of the x-th forcing variable, (x=01,02,03,...,15).
     
     :Output Ports:
         - **WD_Path:** Folder where the execution will be performed.
         - **DataSet_Class:** The information of the forcing datasets.
    """

    _input_ports = [('Dataset_01', STRING_TYPE, {"optional": True}),
                    ('Dataset_02', STRING_TYPE, {"optional": True}),
                    ('Dataset_03', STRING_TYPE, {"optional": True}),
                    ('Dataset_04', STRING_TYPE, {"optional": True}),
                    ('Dataset_05', STRING_TYPE, {"optional": True}),
                    ('Dataset_06', STRING_TYPE, {"optional": True}),
                    ('Dataset_07', STRING_TYPE, {"optional": True}),
                    ('Dataset_08', STRING_TYPE, {"optional": True}),
                    ('Dataset_09', STRING_TYPE, {"optional": True}),
                    ('Dataset_10', STRING_TYPE, {"optional": True}),
                    ('Dataset_11', STRING_TYPE, {"optional": True}),
                    ('Dataset_12', STRING_TYPE, {"optional": True}),
                    ('Dataset_13', STRING_TYPE, {"optional": True}),
                    ('Dataset_14', STRING_TYPE, {"optional": True}),
                    ('Dataset_15', STRING_TYPE, {"optional": True}),
                    ('01_Path', Directory, {"optional": True}),
                    ('02_GPF', File, {"optional": True}),
                    IPort('03_Override?', Boolean, optional=True, default=True),
                    IPort('04_Ready', Variant, optional=True)]
    _output_ports = [
        ('WD_Path', STRING_TYPE),
        ('DataSet_Class', STRING_TYPE)
    ]


    def compute(self):
        """
        The main function of MainGenerator module is to retrieve the inputs from GUI, \
        and  setup the folder where the simulation will be performed.\
        It receives all the forcing datasets and integrates them in an overall dataset as output.
        """
        # Getting Inputs -----------------------------------------------------------------------------------------------
        files_dir = self.force_get_input("01_Path")
        gpf_dir = self.force_get_input("02_GPF")
        isOverridden = self.force_get_input("03_Override?")

        if not isinstance(files_dir, str): files_dir = files_dir.name
        if not isinstance(gpf_dir, str) and gpf_dir is not None: gpf_dir = gpf_dir.name
        DataSet_Class = {}
        # Checking Inputs and provide defaults
        # Start Computing ----------------------------------------------------------------------------------------------
        for i in range(1, 16):
            val = "Dataset_%02d" % (i)
            inputFromPort = self.force_get_input(val)
            if inputFromPort != "":
                if isinstance(inputFromPort, list):
                    inputFromPort = inputFromPort[0]
            else:
                inputFromPort = None
            DataSet_Class[val] = inputFromPort

        start_deleting = False # This was added to allow the GT to have empty columns as forcings
        for key in sorted(DataSet_Class):
            if not DataSet_Class.get(key):
                if start_deleting:
                    del DataSet_Class[key]
            else:
                if not start_deleting:
                    start_deleting = True

        if os.path.exists(files_dir) and isOverridden: self.remove_existing_folder(files_dir)
        if not os.path.exists(files_dir):  # Tries to make the folder if it does not exist
            try:
                os.makedirs(files_dir, mode=0o777)
            except Exception as e:
                os.makedirs(files_dir, mode=0o777)

        if gpf_dir != '' and gpf_dir != None:
            gpf_name = os.path.basename(gpf_dir)
            try:
                shutil.copyfile(gpf_dir, files_dir + "/" + gpf_name)
            except Exception as e:
                print("Could not copy GPF file to folder")
                raise e
        self.set_output("DataSet_Class", DataSet_Class)

        self.set_output("WD_Path", files_dir)

    def remove_existing_folder(self, files_dir):
        """
        This function is to remove an existing folder

        :param files_dir: The path of the folder
        :type files_dir: string
        """
        try:
            shutil.rmtree(files_dir, ignore_errors=True)
        except Exception as e:
            print("Could not delete the work folders")
            raise e

    @classmethod
    def get_documentation(cls, docstring, module=None):
        """
        This function is to get the documentation of MainGenerator module
        param docstring: A string used to document a MainGenerator module
        
        :param module: MainGenerator module
        :return: A invoked function from package DocumentUtil to get documentation of MainGenerator module
        """
        module_name = cls.__dict__['__module__'].split(".")[-1]
        return DocumentUtil.get_documentation(module_name)


def initialize(*args, **keywords):
    """
    This function is to initialize the MainGenerator module
    """
    reg = get_module_registry()
    reg.add_module(MainGenerator)