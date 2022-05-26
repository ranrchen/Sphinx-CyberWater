import math
import os
from utils.types_utils.FloatUtils import FloatUtils
from msm_core.msm_srv.task_cache.TaskCache import TaskCache
from msm_core.msm_dao.helper.dao_dataset import DaoDataSet
from msm_core.model.DataSet import DataSet
from msm_core.model.TimeStep import TimeStep
from msm_core.msm_dao.helper.dataset_cache import DataSetCache
from msm_core.msm_dao.helper.dao_timestep import DaoTimeStep
from datetime import datetime, timedelta
import numpy

class OutputUtil:
    """
    OutputUtil class is a utility class to provide relative methods on calculation and saving the forcing dataset for RunModuleAgent and HPC module.
    """
    @staticmethod
    def exact_rounding(number, decimals):
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
            exactRounding = math.ceil(number * power) / power
        return exactRounding

    @staticmethod
    def point_distance(x1, x2, y1, y2):
        """
        This Function is to calculate the distance between two points (x1,y1) and (x2,y2)

        :param x1: The x coordinate of the point (x1,y1)
        :type x1: float
        :param x2: The x coordinate of the point (x2,y2)
        :type x2: float
        :param y1: The y coordinate of the point (x1,y1)
        :type y1: float
        :param y2: The y coordinate of the point (x2,y2)
        :type y2: float
        :return: The distance between two points (x1,y1) and (x2,y2)
        :rtype: float
        """
        return math.sqrt(pow(x1 - x2, 2) + pow(y1 - y2, 2))


    @staticmethod
    def search_file_with_closest_lat_lon(estimated_lat, estimated_lon, directory, filename_pattern,
                                         min_resolution):
        """
        This function takes an estimation of a latitude and longitude coordinates of a specific cell (in a distributed
        output scenario), together with a directory where a list of cells are saved, and returns the name of the file
        with the closest coordinates to the given ones. If the resulting coordinate gives a difference superior to the
        current resolution, it throws an error.

        :param estimated_lat: The estimation of a latitude
        :type estimated_lat: float
        :param estimated_lon: The estimation of a longitude
        :type estimated_lon: float
        :param directory: The path of directory having a list of cells
        :type directory: str
        :param filename_pattern: The prefix of the file
        :type filename_pattern: str
        :param min_resolution: The miminum of reslution
        :type min_resolution: int
        :return: The name of the file with the closest coordinates to the given ones
        :rtype: str
        """
        min_dist = min_resolution
        lat = estimated_lat
        lon = estimated_lon
        # Check all the files, one by one, and compare how far away they are from our current position. The closer, the better
        list_of_files = os.listdir(directory)
        for file_name in list_of_files:
            if len(file_name.split('_')) == 3:
                coords = file_name.split('_')
                current_distance = OutputUtil.point_distance(estimated_lon, float(coords[2]), estimated_lat, float(coords[1]))
                if current_distance < min_dist:
                    min_dist = current_distance
                    lat = float(coords[1])
                    lon = float(coords[2])
        if min_dist == min_resolution:
            file_not_found = os.path.join(directory, filename_pattern % (lat, lon))
            raise Exception("The output file '%s' does not exists" % file_not_found)
        filename = filename_pattern % (lat, lon)
        print()
        "File '%s', taken as replace of '%s'" % (filename, filename_pattern % (estimated_lat, estimated_lon))
        return filename

    @staticmethod
    def save_output(output_folder, file_key, var_name, dataset_name, pos, file_prefix, point_output, separator,
                    number_of_header_lines, dd):
        """
        This Function is to create a dataset and save the result in the dataset as the output.

        :param output_folder: The path of the folder for output
        :type output_folder: str
        :param file_key: The name of the output dataset
        :type file_key: str
        :param var_name: The name of the variable of the dataset
        :type var_name: str
        :param dataset_name: The name of the input integrated dataset
        :type dataset_name: str
        :param pos: The position (column index) in the result files for the output dataset
        :type pos: int
        :param file_prefix: The prefix of the result file
        :type file_prefix: str
        :param point_output: The boolean value represented whether the output dataset is a single-time-series in a signle file, in contrast of a distributed result in multiple files, once per cell. The default value is False.
        :type point_output: bool
        :param separator: The delimiter in the result file to separate each data filed in result file
        :type separator: str
        :param number_of_header_lines: The number of the header in the result file to skip
        :type number_of_header_lines: int
        :param dd: The detected dimensions
        :type dd: dict
        :return: The created output dataset
        :rtype: dict
        """
        NUM_DIGITS_FILENAME = 4  # NUM_DIGITS_FILENAME
        EMPTY_VALUE = ""
        dataset = OutputUtil.create_dataset(dataset_name, var_name, \
                                      dd.left, dd.right, dd.top, dd.bottom, \
                                      dd.side, dd.base, \
                                      dd.timeini_datetime, dd.timeend_datetime - timedelta(hours=1), \
                                      True, dd.step, None)
        # print("dd_datetime (start:%s, end:%s)" % (dd.timeini_datetime, dd.timeend_datetime))
        if point_output:
            filePath = os.path.join(output_folder, file_prefix)
            if not os.path.exists(filePath): raise Exception("The file <%s> does not exists" % (filePath))
            # tableData = numpy.loadtxt(filePath, dtype='str', skiprows=number_of_header_lines, delimiter=separator)
            tableData = []
            handler = open(filePath, "r")
            for line in handler:
                linelist = line.split()
                tableData.append(linelist)
            # if len(tableData.shape) == 1: tableData = numpy.transpose(tableData)
            # print("tableData shape ========",type(tableData.shape),tableData.shape, len(tableData.shape)), len(tableData)
            current_time = dd.timeini_datetime
            while current_time <= dd.timeend_datetime:
                i = int((current_time - dd.timeini_datetime).total_seconds() / dd.step.total_seconds())
                if i >= len(tableData):  # Our iterator moved beyond the size of the list.
                    if time_step is None: raise Exception("The resulting timeseries should have more than 1 value")
                    oldData = time_step.data
                    time_step = TimeStep()
                    time_step.data = oldData
                    time_step.timestep_datetime = current_time
                    time_step.last_update = datetime.now()
                    time_step.completed = True
                    dataset.set_timestep(time_step)
                    # TODO: This has to be added because the output is usually shorter than the input by 1.
                else:
                    time_step = TimeStep()
                    if len(tableData[0]) == 1 and pos == 0:
                        item = tableData[i]
                        while isinstance(item, list):
                            if len(item) > 0:
                                item = item[0]
                            else:
                                item = 0
                        data = [[float(item)]]
                    else:
                        if len(tableData[i]) == 1 and pos > 0:  # This means, the file has a different separator than 'tab'
                            tableData == tableData.split(separator)
                        data = [[float(tableData[i][pos])]]
                    time_step.data = data
                    time_step.timestep_datetime = current_time
                    time_step.last_update = datetime.now()
                    time_step.completed = True
                    dataset.set_timestep(time_step)
                current_time += dd.step
        else:  # NOT point output
            for row in range(dd.side):
                for col in range(dd.base):
                    lat = OutputUtil.exact_rounding(
                        dd.top - (dd.get_resolution_ver() * row) - (dd.get_resolution_ver() / 2),
                        NUM_DIGITS_FILENAME)
                    lon = OutputUtil.exact_rounding(
                        dd.left + (dd.get_resolution_hor() * col) + (dd.get_resolution_hor() / 2),
                        NUM_DIGITS_FILENAME)
                    filename_pattern = file_prefix + "_%." + str(NUM_DIGITS_FILENAME) + "f_%." + str(
                        NUM_DIGITS_FILENAME) + "f"
                    filename = filename_pattern % (lat, lon)
                    full_path_file = os.path.join(output_folder, filename)
                    if not os.path.exists(full_path_file):
                        filename = OutputUtil.search_file_with_closest_lat_lon(lat, lon, output_folder, filename_pattern,
                                                                         min(dd.get_resolution_ver(),
                                                                             dd.get_resolution_hor()))
                        full_path_file = os.path.join(output_folder, filename)
                    OutputUtil.process_output_file(dataset_name, row, col, full_path_file, EMPTY_VALUE, file_key, pos,
                                             dd.timeini_datetime, dd.timeend_datetime, dd.step,
                                             number_of_header_lines)
        OutputUtil.save_dataset(dataset_name)
        return dataset

    @staticmethod
    def save_outputs(output_folder, desired_outputs, position_list, file_prefix, input_identification,
                     point_output, separator, number_of_header_lines, module_name, ret, dd):  # Add position_list
        """
        This Function is to save the output datasets

        :param output_folder: The path of the folder for output
        :type output_folder: str
        :param desired_outputs: The list of the names of output datasets
        :type desired_outputs: list
        :param position_list: The list of the positions (column indices) in the result files for the output datasets
        :type position_list: list
        :param file_prefix: The prefix of the file
        :type file_prefix: str
        :param input_identification: The id of the input dataset
        :type input_identification: str
        :param point_output:The boolean value represented whether the output dataset is a single-time-series in a signle file,\
        in contrast of a distributed result in multiple files, once per cell. The default value is False.
        :type point_output: bool
        :param separator:The delimiter in the result file to separate each data filed in result file
        :type separator: str
        :param number_of_header_lines: The number of the header in the result file to skip
        :type number_of_header_lines: int
        :param module_name: The name of the current module
        :type module_name: str
        :param ret: The list of the name of output result datasets
        :type ret: list
        :param dd: The detected dimensions
        :type dd: dict
        :return: The integrated result dataset and the list of the name of output result datasets
        :rtype: (dict,list)
        """
        outputs = {}
        taskCache = TaskCache()
        for i in range(len(desired_outputs)):
            desired_output = desired_outputs[i]
            position = int(position_list[i])
            dataset_name = TaskCache.get_task_id(module_name, input_identification, desired_output)
            ret.append(dataset_name)
            dataset = OutputUtil.save_output(output_folder=output_folder, file_key=desired_output, var_name=desired_output, \
                                       dataset_name=dataset_name, pos=position, file_prefix=file_prefix,
                                       point_output=point_output, separator=separator,
                                       number_of_header_lines=number_of_header_lines, dd=dd)
            outputs[desired_output] = [dataset]
        taskCache.put_task_result_to_cache(input_identification, outputs)
        return outputs,ret

    @staticmethod
    def process_output_file(dataset_name, row, col, filename, empty_value, file_key, pos, timeini, timeend,
                            timestep, number_of_header_lines):
        """
        This Function is to process input dataset  and create corresponding output result file

        :param dataset_name: The name of the dataset
        :type dataset_name: str
        :param row: The row number of the input integrated dataset
        :type row: int
        :param col: The column number of the dataset
        :type col: int
        :param filename: The name of the result file
        :type filename: str
        :param empty_value: The value to replace when the element in dataset is empty
        :type empty_value: str
        :param file_key: The name of the output dataset
        :type file_key: str
        :param pos: The position (column index) of the output dataset in the result file
        :type pos: int
        :param timeini: The initial time of the dataset
        :type timeini: datetime
        :param timeend: The ending time of the dataset
        :type timeend: datetime
        :param timestep: The time step of the dataset
        :type timestep: timedelta
        :param number_of_header_lines: The number of header lines in the result file
        :type number_of_header_lines: int
        """
        handler = open(filename, "r")
        timeseries_dict = {}
        currentDate = timeini
        for index, line in enumerate(handler, start=0):
            firstElement = line[0]
            if firstElement[0] != '#' and index >= number_of_header_lines:
                try:
                    [timestep_datetime, value] = OutputUtil.process_results_line(line, empty_value, file_key, pos,
                                                                           currentDate)
                except Exception as e:
                    raise Exception("Error reading file:" + filename + "\tCause:\t" + e.message)
                timeseries_dict[timestep_datetime] = value
                currentDate = currentDate + timestep
        handler.close()
        OutputUtil.set_time_series_to_dataset(dataset_name, timeseries_dict, row, col)

    @staticmethod
    def process_results_line(line, empty_value, file_key, pos, timestep_datetime):
        """
        This Function is to process and extract the result data in each header field in each line of the result file

        :param line: The line being processed in the result file
        :type line: str
        :param empty_value: The value to replace when the element in dataset is empty
        :type empty_value: str
        :param file_key: The name of the output dataset
        :type file_key: str
        :param pos: The position (column index) of the output dataset in the result file
        :type pos: int
        :param timestep_datetime: The current timestamp for the current line in the result file
        :type timestep_datetime: datetime
        :return: The current timestamp for the current line in the result file and the corresponding\
        value in the given position of the current line in the result file
        :rtype: (datetime, float)
        """
        values_line = line.split()
        index = int(pos)

        if values_line[index] == empty_value:
            value = None
        else:
            value = FloatUtils.try_parse(values_line[index])

        return [timestep_datetime, value]

    @staticmethod
    def set_time_series_to_dataset(dataset_name, timeseries_dict, row, col):
        """
        This function is to set the time series for the current dataset
        
        :param dataset_name: The name of the targeted dataset
        :type dataset_name: str
        :param timeseries_dict: The time-series dictionary to be set for the targeted dataset
        :type timeseries_dict: dict
        :param row: The row number of the dataset
        :type row: int
        :param col: The column number of the dataset
        :type col: int
        """
        dataset = DaoDataSet().get_dataset(dataset_name)
        dataset.set_time_series(timeseries_dict, row, col)

    @staticmethod
    def create_dataset(dataset_name, variable_name, left, right, top, bottom, side, base, timeini, timeend, \
                       initialize_ts, step, value, save=False):
        """
        This function is to create the responding dataset in the form of *msmDataset* with the parameters given
        
        :param dataset_name: The name of dataset to be created
        :type dataset_name: str
        :param variable_name: The name of the variable of the dataset
        :type variable_name: str
        :param left: The left boundary value in the space range of the dataset
        :type left: float
        :param right: The right boundary value in the space range of the dataset
        :type right: float
        :param top: The top boundary value in the space range of the dataset
        :type top: float
        :param bottom: The bottom boundary value in the space range of the dataset
        :type bottom: float
        :param side: The vertical resolution of the dataset
        :type side: int
        :param base: The horizontal resolution of the dataset
        :type base: int
        :param timeini: The initial time in the time range of the dataset
        :type timeini: datetime
        :param timeend: The ending time in the time range of the dataset
        :type timeend: datetime
        :param step: The time step of the dataset
        :type step: datetime
        :param value: The result value in the dataset
        :type value: list
        :param save: Flag on whether to save the dataset The default value is *False*
        :type save: bool
        """
        dataset = DataSet()

        dataset.initialize(dataset_name, variable_name, \
                           left, right, top, bottom, side, base, \
                           timeini, timeend, \
                           initialize_ts, step, value)

        DataSetCache().put(dataset_name, dataset)
        return dataset

    @staticmethod
    def check_dimensions(user_inputs, dd, check_space=True, check_time=True):
        """
        This Function is to check the detected dimension of the dataset

        :param user_inputs: The name of the integrated dataset
        :type user_inputs: str
        :param dd: The detected dimensions
        :type dd: dict
        :param check_space: The parameter on whether the space variable exists, default value is *True*.
        :type check_space: bool
        :param check_time: The parameter on whether the time variable exists, default value is *True*.
        :type check_time: bool
        :return: The detected dimensions
        :rtype: dict
        """
        for input_sent in user_inputs:
            dataset_name = user_inputs[input_sent]
            if dataset_name is None or not isinstance(dataset_name, str) or dataset_name == "":
                print("WARNING: Some Datasets are empty")
            dd = OutputUtil.check_dimensions_var(dataset_name=dataset_name, input_name=input_sent, dd=dd,check_space=check_space, check_time=check_time)
        return dd
    @staticmethod
    def get_time_series(dataset_name, time_ini, time_end, row, col, empty_value=None):
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
        :param empty_value: The value to replace when the element in dataset is empty, the default value is None
        :type empty_value: str
        :return: The list of the time-series of the dataset
        :rtype: dict
        """
        dds = DaoDataSet()
        dataset = dds.get_dataset(dataset_name)
        return dataset.get_time_series(time_ini, time_end, row, col, empty_value)

    @staticmethod
    def check_dimensions_var(dataset_name, input_name, dd, check_space=True, check_time=True):
        """
        This Function is to initialize and update detected dimensions

        :param dataset_name: The name of the input integrated dataset
        :type dataset_name: str
        :param input_name: The id of the integrated dataset
        :param check_space: The parameter on whether the space variable exists, default value is True
        :type check_space: bool
        :param check_time: The parameter on whether the time variable exists, default value is True
        :type check_time: bool
        :return: The detected dimensions
        :rtype: dict
        """
        if dataset_name is None or not isinstance(dataset_name, str) or dataset_name == "":
            raise Exception("dataset_name must be not empty string")
        dds = DaoDataSet()
        dataset = dds.get_dataset(dataset_name)
        dataset.compute_uniform_step()
        dataset.compute_timeend()
        if dd is None:
            dd = dataset
        else:
            if check_space:
                dataset.equals_space(dd, True)
            if check_time:
                dataset.equals_time(dd, True)
        return dd

    @staticmethod
    def save_dataset(dataset_name):
        """
        This Function is to save dataset in database and refreshe in cache

        :param dataset_name: The name of the input integrated dataset
        :type dataset_name: str
        """
        dsc = DataSetCache()
        if not dsc.has(dataset_name):
            raise Exception("Dataset not available to save:" + dataset_name)

        dataset = dsc.get(dataset_name)
        DaoDataSet().save_dataset(dataset)
        DaoTimeStep().save_timesteps(dataset_name, dataset.timesteps)
