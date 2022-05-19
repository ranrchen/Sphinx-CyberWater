import os

class DocumentUtil():
    """
    DocumentUtil class is a utility class for the modules in Generic Model Agent Toolkits to get the corresponding documentation.
    """
    @staticmethod
    def get_documentation(module_name):
        """
        This function is to get the documentation of the current module

        :param module_name: The name of the current module
        :type module_name: str
        :return: The documentation of the current module
        :rtype: str
        """
        local_path = r'' + os.path.dirname(os.path.abspath(__file__))
        doc_path = os.path.join(local_path, '..', 'docs', module_name + ".html")
        doc_file = file(doc_path, mode='r')
        docs = doc_file.read()
        doc_file.close()
        return docs