"""
Author: Jagan Shankar
Desc: This class file contains methods related to initialization
"""
from subprocess import getoutput as go
import sys
import logging
import inspect
import os
import shutil
import time
import socket
from Utils import Utils
from Log import Log
from BrowserActions import BrowserActions
from SysUtils import SysUtils
from ConfigUtils import ConfigUtils
from SSHClient import *
from SftpClient import *
from Gateway import *
from REST.REST import RestClient

config = ConfigUtils.getInstance()
util = Utils()
browseractions = BrowserActions()
sysutils = SysUtils()

class Initialize():
    def __init__(self):
        pass

    def initialize(self):
        '''
		Description:
		   | To initialize logging module, cleanup any existing browser session |
		Input Param:
           | None
		Output:
			| return_dict = {'status': 1 (success) or non-zero (for failure),
                             'value': <Success OR Error Message (include exception info)>} |
        Usage:
            |  initobj.initialize()
        '''
        return_dict = {'status': 0, 'value': None}
        try:
            Log().setloggingconf()
            server_count = config.get_server_count()
            start_sikuli = None
            branch = None
            pvt_branch = None
            for i in range(server_count):
                i=i+1
                server_ip = config.server(i).get_IP()
                try:
                    branch = config.fw_tags().get_IVE_VER()
                    start_sikuli = config.device(i).get_START_SIKULI()
                except:
                    start_sikuli = "0"
                if server_ip == "localhost" or server_ip == "127.0.0.1":
                    logging.info("Local run Start PSRS Manually")
                else:
                    for j in range(1,5):
                        ssh = SSHClient(server_ip, 22, "qa1", "dana123")
                        return_dict = ssh.create_connection(server_ip, 22, "qa1", "dana123")
                        if (return_dict['status'] == 1):
                            logging.info("SSH server is up and running.")
                            break
                        else:
                            time.sleep(10)
                            logging.warn("Re-attempt: "+str(j)+" Waiting 10 seconds for SSH server to up and running.")

                    assert return_dict['status'] == 1, return_dict['value']
                    if sys.platform == 'linux':
                        sftp = SftpClient(server_ip, 22, "qa1", "dana123")
                        status = sftp.is_dir_exist("C:/pisa")
                        pstafDir_status = sftp.is_dir_exist("C:/pstaf")
                        if status:
                            logging.info("C:/pisa exist.")
                        else:
                            logging.info("C:/pisa does not exist")
                            logging.info("Copying from /home/qa1/automation5/pisa/pisa/" + branch)
                            logging.info("Copying pisa to server : " + server_ip)
                            ssh.scp_put("/home/qa1/automation5/pisa/pisa/" + branch, "C:/pisa")
                            for k in range(5):
                                sftp = SftpClient(server_ip, 22, "qa1", "dana123")
                                status = sftp.is_dir_exist("C:/pisa")
                                if status:
                                    logging.info("C:/pisa exist.")
                                    status = sftp.is_dir_exist("C:/pisa/utils")
                                    break
                                else:
                                    ssh.scp_put("/home/qa1/automation5/pisa/pisa/" + branch, "C:/pisa")

                        if pstafDir_status:
                            logging.info("C:/pstaf exist.")
                        else:
                            logging.info("C:/pstaf does not exist")
                            logging.info("Copying from /home/qa1/automation5/pisa/pstaf/" + branch)
                            logging.info("Copying pstaf to server : " + server_ip)
                            ssh.scp_put("/home/qa1/automation5/pisa/pstaf/" + branch, "C:/pstaf")
                            ssh.scp_put("/home/qa1/automation5/pisa/pstaf/" + branch + "/drivers/chromedriver.exe",
                                        "C:/Katalon_C/configuration/resources/drivers/chromedriver_win32")


                    if(sysutils.is_port_open(server_ip, "9999")):
                        logging.info("PSRS is up and running.")
                    else:
                        logging.info("Getting PSRS from GitHub...")
                        try:
                            pvt_branch = config.fw_tags().get_PVT_IVE_VER()
                            if pvt_branch != None and pvt_branch !="":
                                branch = pvt_branch
                                logging.info("Private Branch defined. Branch : " + str(branch))
                        except:
                            logging.info("Private Branch not defined.")

                        branch = "\"" + branch + "\""
                        output = ssh.run_command(
                            'C:/GitCloneCode/PsExec.exe /accepteula -u qa1 -p dana123 -d -i 1 cmd.exe /c start py -3 '
                            '"C:/GitCloneCode/GitCloneRepo.py"' + " " + '"PSRS"' + " " + branch)
                        # time.sleep(90) # need to make dynamic wait

                        path = os.environ['PSTAF_HOME'] + "/log/gitclonerepo" + str(i) + ".txt"
                        logging.info(path)
                        sftp = SftpClient(server_ip, 22, "qa1", "dana123")
                        git_clone_status = "Failed"
                        for i in range(10):
                            git_clone_read_data = sftp.read_file('C:/gitclonerepo.txt')
                            if 'Updating files: 100' in str(git_clone_read_data):
                                logging.info("PSRS clone successful.")
                                git_clone_status = "Success"
                                break
                            else:
                                if i >= 9:
                                    logging.error("Failed to clone PSRS from git.")
                                else:
                                    logging.warn("Attempt :"+str(i)+" Check Clone PSRS from git. Waiting 30 seconds.")
                                    time.sleep(30)
                        assert git_clone_status == "Success", git_clone_status
                        logging.info("Starting PSRS")
                        output = ssh.run_command(
                            'C:/pisa/utils/PsExec.exe /accepteula -u qa1 -p dana123 -d -i 1 cmd.exe /c start py -3 '
                            '"C:/psrs/PSRS_Framework/PSRS.py"')
                        if (self.is_server_up(server_ip, "9999", 60)):
                            logging.info("Successfully Started PSRS...")
                            logging.info("PSRS Start Status : " + str(output))
                        else:
                            logging.error("Fail to Start PSRS. Exiting...")
                            exit();

                    if (sysutils.is_port_open(server_ip, "9876") and sysutils.is_port_open(server_ip, "4444")):
                        logging.info("Selenium and ROME server is up and running.")
                    else:
                        logging.info("Starting ROME and Selenium Server")
                        output = ssh.run_command(
                            'C:/pisa/utils/PsExec.exe /accepteula -u qa1 -p dana123 -d -i 1 cmd.exe /c start '
                            '"C:/pisa/utils/pisa_win_startup.exe"')
                        logging.info("ROME and Selenium server status : " + str(output))
                        if (self.is_server_up(server_ip, "9876", 120)):
                            logging.info("Successfully Started ROME and Selenium Server...")
                            logging.info("ROME Start Status : " + str(output))
                        else:
                            logging.error("Fail to Start ROME and Selenium Server. Exiting...")
                            exit();

                    if start_sikuli == "1":
                        logging.info("Getting pyRome from GitHub...")
                        try:
                            branch = config.fw_tags().get_SIKULI_VER()
                            branch = "\"" + branch + "\""
                        except:
                            branch = '"latest"'
                        output = ssh.run_command(
                            'C:/GitCloneCode/PsExec.exe /accepteula -u qa1 -p dana123 -d -i 1 cmd.exe /c start py -3 '
                            '"C:/GitCloneCode/GitCloneRepo.py"' + " " + '"pyrome"' + " " + branch)
                        time.sleep(90)# need to make dynamic wait
                        logging.info("Starting pyRome")
                        output = ssh.run_command(
                            'C:/pisa/utils/PsExec.exe /accepteula -u qa1 -p dana123 -d -i 1 cmd.exe /c start jython '
                            '"C:/pisa/JythonLib/pyRome.py"')
                        logging.info("PSRS Status : " + str(output))

            gateway = Gateway()
            status = gateway.register_all_devices()
            if (status != "Skip"):
                assert status == "Success", status
            logging.info("Registration Status : " +status)

            #Config Upload is already verified. So, no need to wait here
            #if (status == "Success"):
            #    logging.info("Sleeping 15 minutes for config to sync with controller after successful Registration")
            #    time.sleep(900)
            return_dict = browseractions.cleanup_browser_session()
            assert return_dict['status'] == 1, return_dict['value']
            env_str = "initialize() - log fileconfig initialized..." \
                             "start using logging.info, error, debug, etc., to log your messages"
            logging.info(env_str)
            env_str = "=========================================== *Environment Details* START " \
                                                   "============================================="
            logging.info(env_str)
            logging.info(sysutils.getOSEnvInfo())
            logging.info(sysutils.getBrowserInfo())
            env_str = "=========================================== *Environment Details* END " \
                                                 "============================================="
            logging.info(env_str)
        except:
            e_message = sys.exc_info()[1]
            print("*ERROR* Exception in Intialize.py:initialize(): " + str(e_message))
            raise Exception(e_message)

    def get_psrs_logs(self):
        '''
        Description:
           | To get PSRS logs from the client machine |
        Input Param:
           | None
        Output:
            | donwloads the log files to Jenkins |
        Usage:
            |  initobj.get_psrs_logs()
        '''

        func_name = inspect.stack()[0][3]
        util.FUNC_HEADER_FOOTER('Enter', func_name)
        try:
            if sys.platform == 'darwin' or sys.platform == 'linux':
                server_count = config.get_server_count()
                for i in range(server_count):
                    i = i + 1
                    path = os.environ['PSTAF_HOME'] + "/log/" + "server_" + str(i) + "/"
                    logging.info(path)
                    os.mkdir(path)
                    server_ip = config.server(i).get_IP()
                    sftp = SftpClient(server_ip, 22, "qa1", "dana123")
                    sftp.get_all_files("C:\\psrs\\log\\",path)
        except:
            e_message = sys.exc_info()[1]
            logging.error("Exception in " + str(func_name) + ": " + str(e_message))
        util.FUNC_HEADER_FOOTER('Exit', func_name)

    def cleanup(self):
        '''
        Description:
           | To perform the cleanup after test execution |
        Input Param:
           | None
        Usage:
            |  initobj.cleanup()
        '''

        func_name = inspect.stack()[0][3]
        util.FUNC_HEADER_FOOTER('Enter', func_name)

        self.get_psrs_logs()
        RestClient().set_device_type('zta_c')
        gateway = Gateway()
        gateway.delete_all_gateways()


        util.FUNC_HEADER_FOOTER('Exit', func_name)

    def startservers(self):
        '''
		Description:
		   | To start PSRS server in the client machine |
		Input Param:
           | None
		Output:
			| return_dict = {'status': 1 (success) or non-zero (for failure),
                             'value': <Success OR Error Message (include exception info)>} |
        Usage:
            |  initobj.startservers()
        '''
        func_name = inspect.stack()[0][3]
        util.FUNC_HEADER_FOOTER('Enter', func_name)
        try:
            ret_msg = go('wmic /node:127.0.0.1 process where name="python.exe" get commandline, \
                                          processid | findstr /R "python[ ]*PSRS.py"')
            ret_msg = ret_msg.strip()
            if len(ret_msg) == 0:
                logging.info("PSRS.py is not running")
            else:
                logging.info("PSRS.py is runnning........" + ret_msg)
        except:
            e_message = sys.exc_info()[1]
            logging.error("Exception in " + str(func_name) + ": " + str(e_message))

        util.FUNC_HEADER_FOOTER('Exit', func_name)

    def is_server_up(self, ip, port, timeout=None):
        '''
        Description:
           | To check if a specific port is open or close in remote machine|
        Input Param:
           | 1. ip = 1.1.1.1 (Remote machine IP)
             2. port = 9999 (Remote machine port)
             3. timeout = timeout in seconds (Optional)
           |
        Output:
            | 1/0 |
        Usage:
            |  initobj.is_server_up("10.67.54.89", "9999", 30)
               initobj.is_server_up("10.67.54.89", "9999")
        '''
        func_name = inspect.stack()[0][3]
        util.FUNC_HEADER_FOOTER('Enter', func_name)
        for i in range(30):
            status = sysutils.is_port_open(ip, port, timeout)
            i = i + 1
            if (status):
                break
            else:
                time.sleep(10)
                logging.info("Waiting 10 seconds for Server to come up...")
        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return status

#=================================================================================================
#Author-Jagan Shankar
#Modified by-Raghu S
#Modified date- 22/JULY/2021
#Bugs Fixed if any-<List Of Bugs>
#pylintscore- 6.89
#Licence -COPYRIGHT & LICENSE
#Copyright 2020, Pulse Secure, LLC, all rights reserved.
#This program is free software; you can redistribute it and/or modify it under the same terms as
#Python itself.
#=================================================================================================
