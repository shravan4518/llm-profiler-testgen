"""
Author: Jagan Shankar 
Desc: This class file contains utility methods required for the framework and scripting
"""

import logging, inspect, sys

class Utils(object):
    ROBOT_LIBRARY_SCOPE = 'GLOBAL'


    def __init__(self):
        #log = Log()
        pass

    def TC_HEADER_FOOTER(self, startorstop, tc_name):
        logging.info("=" * (len(tc_name) + 18))
        logging.info(startorstop.upper() + " OF TESTCASE: " + str(tc_name))
        logging.info("=" * (len(tc_name) + 18))

    def FUNC_HEADER_FOOTER(self, enterexit, func_name):
        if enterexit.lower() == "enter":
            enterexit = "Entering "
        elif enterexit.lower() == "exit":
            enterexit = "Exiting "

        #logging.info("=" * (len(func_name) + 18))
        logging.info(enterexit.upper() + str(func_name) + str("()..........."))
        #logging.info("=" * (len(func_name) + 18))

    def compare_json(self, data_a, data_b):
        '''
         To compare 2 json data
         :param data_a : JSon data to compare
         :param data_b : JSon data to compare
         :return: Boolean
            True/False ( based on json data are same or not)
         :Usage:
            json1 = { "name" : "AD_SERVER" , "ad" : { "settings" : ...... } }
            json2 = { "name" : "Auth_SERVER" , "ad" : { "settings" : {......} } }
            Example:result = utils.compare_json(json1, json2 )
        '''
        func_name = inspect.stack()[0][3]
        try:
            # List Type
            if ( type(data_a) is list ) :
                if ( (type(data_b) != list) or (len(data_a) != len(data_b)) ):
                    logging.error("Length of list element is not equal")
                    logging.debug("Source Data : {}".format(data_a))
                    logging.debug("Expected Data : {}".format(data_b))
                    return False
                # Parse each list elemt
                for element in data_a:
                    if ( type(element) is list or type(element) is dict):
                        length = len(data_b)
                        counter = 0
                        # If list element is again a list or dict compare with all other elements in b
                        for item in data_b:
                            if ( not self.compare_json(element, item)):
                                counter = counter + 1
                        if counter == length:
                            logging.error("Expected data : {} not found ".format(element))
                            return False
                    else:
                        if element not in data_b:
                            logging.error("Expected data : {} not found ".format(element))
                            return False
                # Indentical data
                return True
            # Dict type
            elif ( type(data_a) is dict):
                if ( type(data_b) != dict):
                    logging.error("Expected data is not a dictionary")
                    logging.info("Source Data : {}".format(data_a))
                    logging.info("Expected Data : {}".format(data_b))
                    return False
                # iterate over dict elements
                for dict_key,dict_value in data_a.items():
                    # key exists in [data_b] dictionary, and same value?
                    if (dict_key not in data_b ):
                        logging.debug("Source Data : {}".format(data_a))
                        logging.debug("Expected Data : {}".format(data_b))
                        logging.error("Key : {} not present in the expected json".format(dict_key))
                        return False
                    elif (not self.compare_json(dict_value, data_b[dict_key]) ):
                        logging.warning("Error comparing for key : {}".format(dict_key))
                        return False
                # Dictionary identical
                return True

            # value - compare both value and type for equality
            if ( (data_a == data_b) and (type(data_a) is type(data_b)) ):
                return True
            else:
                logging.warning("Expected : {}, got : {}".format(data_a,data_b))
                return False
        except:
            e = sys.exc_info()[1]
            logging.error("Exception in " + func_name + " api: " + str(e))
        return False

"""
========================================================================================================================
Author-Jagan Shankar
Modified by-Jagan Shankar
Modified date- 26/APR/2020
Bugs Fixed if any-<List Of Bugs>
pylintscore- 8.00
Licence -COPYRIGHT & LICENSE
Copyright 2020, Pulse Secure, LLC, all rights reserved.
This program is free software; you can redistribute it and/or modify it under the same terms as Python itself.
========================================================================================================================
"""
