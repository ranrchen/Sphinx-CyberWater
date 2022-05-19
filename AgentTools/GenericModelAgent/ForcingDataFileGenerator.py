from __builtin__ import sorted
from vistrails.core.modules.vistrails_module import Module, ModuleError
from vistrails_helpers.utils.vistrail_types import STRING_TYPE, VARIANT_TYPE, BOOLEAN_TYPE
from vistrails.core.modules.basic_modules import String, Float, File
from msm_core.msm_dao.helper.dao_dataset import DaoDataSet
from vistrails.core.modules.module_registry import get_module_registry
import os
import math
import shutil
import numpy
from os.path import join
from vistrails.core.modules.config import IPort, CIPort
from util.DocumentUtil import DocumentUtil

class ForcingDataFileGenerator(Module):
    """
    ForcingDataFileGenerator Organizes the forcing data brought by the MainGenerator. 
    The user should be aware of the expected format of the forcing data for their model.
    By default, this module creates forcing data in a folder names 'Forcing'. Such forcing data is 
    always created as timeseries where different columns hold different variables, ie: 

            ``(Precipitation_t0 | Temerature_t0 | Wind_t0, etc)``

            ``(Precipitation_t1 | Temerature_t1 | Wind_t1, etc)``

            ``(Precipitation_t2 | Temerature_t2 | Wind_t2, etc)``

            ``(Precipitation_t3 | Temerature_t3 | Wind_t3, etc)``

    and the data is divided in different files, were each one represents a single cell of the forcing inputs. 
    So, a 2 by 2 (2x2) model will generate 4 files, each one with the full timeseries of the forcing data.

    :Input Ports:
        - **WD_Path:** This is the working folder provided by the MainGenerator module.
        - **DataSet_Class:** This is the dataset information provided by the MainGenerator module.
        - **Forcing_Folder_Name:** **[Optional]** Name of the subfolder where the forcing info will be stored. The default value is *Forcing*.
        - **Forcing_File_Prefix:** **[Optional]** Prefix for the name of the forcing files. The default value is *data*.
        - **Date_Label_Format:** **[Optional]** Format taken for the dates of the first column.(i.e 05/16/1997-05:30:00 can be expressed as %m/%d/%YYYY-%H:%M:%S ), \
        The default value is `None`, which means the files will not have dates. For more information about python date formats go to https://strftime.org/
        - **Subrange:** **[Optional]** Subset of the dataset by giving the boundary limitation including x_min, x_max, y_min, y_max.
        - **Mask_File:** **[Optional]** Mask file for generating specific forcing data files, there are two types of mask files, which are inclusive and exclusive.\
        In the mask file, it records the latitude and longitude of the cell each line, and for inclusive mask file, the ForcingDataFileGenerator module will only\
        yield the forcing data files of the certain cell given in mask file. and in reverse, the exclusive mask file provided to create the forcing data files of the cells which is excluded in the mask file.\
        The format of the mask file, should be ``latitude,longitude`` each line, and user can make comment freely in any other line.

    :Output Ports:
        - **Ready:** Starting flag for RunModuleAgent. The value is either *True* or *False*.
    """
    _input_ports = [
                    ('Forcing_Folder_Name', STRING_TYPE, {"optional": True}),
                    IPort(name="Forcing_File_Prefix", signature="basic:String", default='data', optional=True),
                    IPort(name="Date_Label_Format", signature="basic:String", optional=True), #Examples: MM/DD/YYYY-HH
                    CIPort("Subrange",[Float, Float, Float, Float],optional=True, labels=["**x_min</b>","**x_max</b>","**y_min</b>","**y_max</b>"]),
                    CIPort("Mask_File", [String, File], entry_types=["enum", None],optional=True, labels=["**Type</b>","**Path</b>"],values=[["","Exclusive","Inclusive"],None],defaults = ["",""]),
                    ('WD_Path', VARIANT_TYPE),
                    ('DataSet_Class', VARIANT_TYPE)]
    _output_ports = [('Ready', BOOLEAN_TYPE)]
   
    NUM_DIGITS_FILENAME = 4
    WRITE_EMPTY_VALUE = None
    subrange = []
    mask_type, mask_path = "", ""

    def compute(self):
        """
        The main function of ForcingDataFileGenerator module is to organize the forcing data brought by the MainGenerator module
        """
        # Getting Inputs -----------------------------------------------------------------------------------------------
        files_dir = self.force_get_input("WD_Path")
        DataSet = self.force_get_input("DataSet_Class")
        file_name = self.force_get_input("Forcing_File_Prefix", 'data')
        forcing_dir=self.force_get_input("Forcing_Folder_Name")
        date_label_format = self.force_get_input("Date_Label_Format")
        self.subrange = self.force_get_input("Subrange")
        mask = self.force_get_input("Mask_File")
        if mask:
            self.mask_type = mask[0]
            self.mask_path = mask[1].name

        # Checking Inputs and provide defaults
        self.dd = None
        if files_dir is None or files_dir == "": raise Exception("WD_Path is empty or undefined.")
        if DataSet is None or DataSet == "": raise Exception("DataSet_Class is empty or undefined.")
        #print(" ===== DataSet_Class", DataSet, type(DataSet))
        if file_name == "" or file_name == None: file_name = 'data'
        if forcing_dir == "" or forcing_dir == None: forcing_dir = 'Forcing'
        if date_label_format == "" or date_label_format == None: date_label_format = None
        self.check_dimensions(DataSet)
        # remove exist dir
        try:
            shutil.rmtree(join(files_dir,forcing_dir), ignore_errors=True)
        except Exception as e:
            print "Could not delete the folders"
            raise e
        # Start Computing ----------------------------------------------------------------------------------------------
        print "files, generating"
        ready_sign = False
        if DataSet != "" and DataSet is not None:
            os.makedirs(join(files_dir,forcing_dir), mode=0777)
            self.prepare_forcing(forcing_dir_prefix=join(files_dir,forcing_dir,file_name)+"_", inputs=DataSet, date_format=date_label_format)
            ready_sign = True
        else:
            print "DataSet_Class port is empty"
            raise Exception("DataSet_Class port is empty")

        self.set_output("Ready", str(ready_sign))
    def exact_rounding(self, number, decimals):
        """
        This Function is to return a floating point number that is a rounded version of the specified number, with the specified number of decimals

        :param number: The number to be rounded
        :type number: float
        :param decimals: The number of decimals to use when rounding the number.
        :type decimals: int
        :return: The rounded number
        :rtype: float
        """
        power = math.pow(10, decimals)
        exactRounding = None
        if number is not None:
            exactRounding = math.ceil(number*power) / power
        return exactRounding
    def change_forcing_name(self, folder, file_name):
        """
        This function is to change the name of files in the given folder

        :param folder: The path of the folder
        :type folder: str
        :param file_name: The prefix of the file needed adding or the new file name needed changing
        :type file_name: str
        """
        filelist = os.listdir(folder)
        for files in filelist:
            Olddir = os.path.join(folder, files)
            file = files.split("_")
            Newdir = os.path.join(folder, file_name+"_"+file[-2]+"_"+file[-1])
            os.rename(Olddir, Newdir)


    # user_inputs = DataSet_class (list with the names of the datasets)
    def save_forcing(self, filename, user_inputs, row, col, date_format):
        """
        This function is to build a unique file with all the forcing information of a cell

        :param filename: The name of the file
        :type filename: str
        :param user_inputs: The names of the integrated forcing dataset
        :type user_inputs: str
        :param row: The row index of the 2D-forcing dataset
        :type row: int
        :param col: The column index of the 2D-forcing dataset
        :type col: int
        :param date_format: The format taken for the dates of the first column
        :type date_format: str
        """
        if self.dd.timeini_datetime is None or self.dd.timeend_datetime is None:
            raise Exception("No time range detected")
        dataset_class_dict=user_inputs
        if len(dataset_class_dict) > 0:
            the_series=[]
            n_of_empty_rows = 0
            for dataset_id in sorted(dataset_class_dict):
                if dataset_class_dict[dataset_id] is not None:
                    tmp_series=self.get_time_series(dataset_name=dataset_class_dict[dataset_id],
                                                    time_ini=self.dd.timeini_datetime, \
                                                    time_end=self.dd.timeend_datetime, \
                                                    row=row, col=col, empty_value=self.WRITE_EMPTY_VALUE)

                    # Remove nan values and replace them with zeros.
                    tmp_series_numpy = numpy.asarray(tmp_series)
                    tmp_series_numpy[numpy.isnan(tmp_series_numpy)] = 0
                    tmp_series = tmp_series_numpy.tolist()
                    the_series.append(tmp_series)
                else:
                    n_of_empty_rows += 1

            for i in range(0,n_of_empty_rows):
                empty_series = numpy.zeros(len(tmp_series)).tolist()
                the_series.insert(0, empty_series)

            ff = open(filename,"w")
            timeStep = self.dd.compute_uniform_step()
            # print the_series
            for value_pos in range(len(the_series[0])):
                current_date = self.dd.timeini_datetime+timeStep*value_pos
                line = ""
                if date_format is not  None: line = current_date.strftime(date_format)+"\t" #current_date.strftime("%m/%d/%Y-%H.%M.%S\t")
                for the_serie in range(len(the_series)):
                    line = line + str(the_series[the_serie][value_pos]) + "\t"
                line = line[:-1] + "\n"
                ff.write(line)
            ff.close()

    def prepare_forcing(self, forcing_dir_prefix, inputs, date_format):
        """
        This Function is to prepare forcing dataset

        :param forcing_dir_prefix: The prefix of the forcing data directory
        :type forcing_dir_prefix: str
        :param inputs: The names of the integrated forcing dataset
        :type inputs: str
        :param date_format: The format taken for the dates of the first column
        :type date_format: str
        """
        side=self.dd.side
        base=self.dd.base
        hor_resolution=self.dd.get_resolution_hor()
        ver_resolution=self.dd.get_resolution_ver()
        left=self.dd.left
        top=self.dd.top
        
        print side, base,

        #Data for use later in save_outputs
        print "saving-forcing-timeseries pixel:",
        for row in range(side):
            print "%02d" % (float(base * row) * 100 / float(base * side)) + "%",
            for col in range(base):
                # print "(", row, ",", col, ")"
                lat=self.exact_rounding(top-(ver_resolution*row)-(ver_resolution/2), self.NUM_DIGITS_FILENAME)
                lon=self.exact_rounding(left+(hor_resolution*col)+(hor_resolution/2), self.NUM_DIGITS_FILENAME)
                if self.check_subrange(lat,lon):
                    tmp_filename="%."+str(self.NUM_DIGITS_FILENAME)+"f_%."+str(self.NUM_DIGITS_FILENAME)+"f"
                    forcing_filename = forcing_dir_prefix + tmp_filename%(lat,lon)
                    self.save_forcing(filename=forcing_filename, user_inputs=inputs, row=row, col=col, date_format=date_format)

    def check_subrange(self,lat,lon):
        """
        This Function is to check whether the targeted cell is included in the sub-range

        :param lat: The latitude of the targeted cell
        :type lat: float
        :param lon: The longitude of the targeted cell
        :type lon: float
        :return: return the result of a boolean value on whether the targeted cell is included in the sub-range
        :rtype: bool
        """
        if not self.subrange or (self.subrange[2] <= lat <= self.subrange[3] and self.subrange[0] <= lon <= self.subrange[1]):
            return self.check_mask(lat,lon)
        return False

    def check_mask(self,lat,lon):
        """
        This Function is to check whether the targeted cell is included in the mask

        :param lat: The latitude of the targeted cell
        :type lat: float
        :param lon: The longitude of the targeted cell
        :type lon: float
        :return: return the result of a boolean value on whether the targeted cell is included in the mask
        :rtype: bool
        """
        if self.mask_type == "":
            return True
        mask_file = open(self.mask_path, "r")
        mask_list = []
        for line in mask_file:
            if not line:
                continue
            try:
                mask_lat, mask_lon = line.split(",")
                mask_lat = float(mask_lat)
                mask_lon = float(mask_lon)
                mask_list.append([mask_lat, mask_lon])
            except:
                continue
        if self.mask_type == "Exclusive":
            return not [lat,lon] in mask_list
        else:
            return [lat,lon] in mask_list

    def check_dimensions_var(self, dataset_name, input_name, check_space = True, check_time = True):
        """
        This Function is to initialize and update detected dimensions

        :param dataset_name: The name of the integrated dataset
        :type dataset_name: str
        :param input_name: The id of the integrated dataset
        :param check_space: The parameter on whether the space variable exists, default value is True
        :type check_space: bool
        :param check_time: The parameter on whether the time variable exists, default value is True
        :type check_time: bool
        """
        if dataset_name is None or not isinstance(dataset_name, str) or dataset_name == "":
            raise Exception("dataset_name must be not empty string")
        
        dds = DaoDataSet()
        dataset = dds.get_dataset(dataset_name)
        dataset.compute_uniform_step()
        dataset.compute_timeend()
        if self.dd is None: 
            self.dd = dataset
        else:
            if check_space:
                dataset.equals_space(self.dd, True)
            if check_time:
                dataset.equals_time(self.dd, True)

    def check_dimensions(self, dataset_class, check_space = True, check_time = True):
        """
        This Function is to check the detected dimension of the dataset

        :param dataset_class: The name of the integrated dataset
        :type dataset_class: str
        :param check_space: The parameter on whether the space variable exists, default value is True
        :type check_space: bool
        :param check_time: The parameter on whether the time variable exists, default value is True
        :type check_time: bool
        """
        self.initialize_dimensions()
        for dataset_id in dataset_class:
            dataset_name=dataset_class[dataset_id]
            if dataset_name is None or not isinstance(dataset_name, str) or dataset_name == "":
                print("WARNING: Some Datasets are empty")
                #raise Exception("dataset_name in user_inputs was None. user_inputs:%s"%(str(dataset_class)))
            else:
                self.check_dimensions_var(dataset_name=dataset_name, input_name=dataset_id,
                                      check_space=check_space, check_time=check_time)

    def initialize_dimensions(self):
        """
        This Function is to initialize the detected dimensions
        """
        self.dd = None

    def get_time_series(self, dataset_name, time_ini, time_end, row, col, empty_value=None):
        """
        This Function is to obtain the time-series of the targeted dataset

        :param dataset_name: The name of the integrated dataset
        :type dataset_name: str
        :param time_ini: The initial time of the dataset
        :type time_ini: datetime
        :param time_end: The ending time of the dataset
        :type time_end: datetime
        :param row: The row number of the dataset
        :type row: int
        :param col: The column number of the dataset
        :type col: int
        :param empty_value: The value to replace when the element in dataset is NAN, the default value is None
        :type empty_value: str
        :return: The list of the time-series of the dataset
        :rtype: dict
        """
        dds=DaoDataSet()
        dataset=dds.get_dataset(dataset_name)
        return dataset.get_time_series(time_ini, time_end, row, col, empty_value)

    @classmethod
    def get_documentation(cls, docstring, module=None):
        """
        This function is to get the documentation of ForcingDataFileGenerator module

        :param docstring: A string used to document a ForcingDataFileGenerator module
        :param module: ForcingDataFileGenerator module
        :return: A invoked function from package DocumentUtil to get documentation of ForcingDataFileGenerator module
        """
        module_name = cls.__dict__['__module__'].split(".")[-1]
        return DocumentUtil.get_documentation(module_name)

def initialize(*args, **keywords):
    """
    This function is to initialize the ForcingDataFileGenerator module
    """
    reg = get_module_registry()
    reg.add_module(ForcingDataFileGenerator)