"""
Author: Jagan Shankar 
Desc: This class file contains methods related to Browser Actions

Locators Usage:                 - Example Below
id or name or xpath             => btn_save or //div[@id="example"]
identifier:Either id or name 	=> identifier:example
id:element id                   => id:example
name:name attribute 	        => name:example
class:element class	            => class:example
tag:tag name	                => tag:div
xpath:xPath expression	        => xpath://div[@id="example"]
css:sSS selector                => css:div#example
dom:DOM expression              => dom:document.images[5]
link:Exact text a link has  	=> link:The example
partial link:Partial link text  => partial link:he ex
jquery:jQuery expression    	=> jquery:div.example

"""

import sys, time, inspect, selenium, logging
from Utils import *
from PSRSClient import *
#from ConfigUtils import ConfigUtils
#config = ConfigUtils.getInstance()

util       = Utils()
psrsclient = PSRSClient()

class BrowserActions(object):
    def __init__(self):
        self.sel = None

    def get_current_browser(self):
        #TODO - Get from current config.xml
        currbrowser = 'firefox'
        return currbrowser

    def cleanup_browser_session(self):
        '''
		Description:
		   |  To clean all browser (zombie) sessions, if any. It is more of internal use. And will be called only in Initialize->initialize() |
		Input Param:
			| None |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Dimensions of the browser windows OR Error Message (include exception info)>} |
        Usage:
            | browseractions.cleanup_browser_session()
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            logging.info('Sending Request to PSRS....')
            
            dict = {'api_name': 'cleanup_browser_session'}
            return_dict = psrsclient.execute_api("POST", dict)
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def launch_browser(self,input_dict):
        '''
		Description:
		    | To launch a browser - Supported browser - firefox, chrome, safari, internetexplorer, edge |
		Input Param:
			| input_dict (dict) (mandatory)
            | "type"     : "admin|user|guestuser" - Type of login |
            | "browser"  : "firefox|chrome|ie|safari|edge" - Browser name |
            | "url"      : URL with http or https |
            | "username" : Username |
            | "password" : Password |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Success OR Error Message (include exception info)>} |
        Usage:
            | login_dict = {
                |  "type" : "admin",
                 | "browser": "firefox",
                 | "url" : "https://10.64.55.226/admin",
                |  "username" : "admindb",
                 | "password" : "dana123",
           |  }
            | browseractions.launch_browser(login_dict)
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            #input_dict['browser'] = self.getCurrentBrowser()  #I think this design is not required
            
            logging.info('Sending Request to PSRS....')
            dict = {'api_name': 'launch_browser', 'params': input_dict}
            return_dict = psrsclient.execute_api("POST", dict)
            #Retrun status check is required
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg
            #raise Exception(e)

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def switch_browser_to(self,input_dict):
        '''
		Description:
		    | To switch to other browser - Supported browser - firefox, chrome, safari, internetexplorer, edge |
		Input Param:
			| input_dict (dict) (mandatory)
            | "browser"  : "firefox|chrome|ie|safari|edge" - Browser name |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Success OR Error Message (include exception info)>} |
        Usage:
            | login_dict = {
                | "browser": "firefox",
          |   }
           |  browseractions.switch_browser_to(input_dict)
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]

        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            if not input_dict or not "browser" in input_dict:
                return_dict['value'] = "Input parameters - input_dict dictionary or browser key is missing.....please check the input dictionary"
            else:
                logging.info('Sending Request to PSRS....')
                dict = {'api_name': 'switch_browser_to', 'params': input_dict}
                return_dict = psrsclient.execute_api("POST", dict)
                logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def handle_login_intermediate_page(self, input_dict):
        '''
		Description:
		    | To handle PCS/PSS intermediate page appears immedaitely after the login page |
		Input Param:
			| input_dict['click'](dictionary)(Mandatory) - "continue or readonly or cancel" |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Successful or Error Message (include exception info)>} |
        Usage:
            | input_dict['click'] = "continue"
            | browseractions.handle_login_intermediate_page(input_dict)
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            #input_dict['browser'] = self.getCurrentBrowser() #I think this design is not required
            if not input_dict or not "click" in input_dict:
                return_dict['value'] = "Input parameters - input_dict dictionary or click key is missing.....please check the input dictionary"
            logging.info('Sending Request to PSRS....')
            
            if input_dict is None:
                input_dict = {'click' : "continue" }
            dict = {'api_name': 'handle_login_intermediate_page', 'params': input_dict}
            return_dict = psrsclient.execute_api("POST", dict)
            #Retrun status check is required
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def get_browser_desired_capabilities(self):
        '''
		Description:
		    | To get desired capabilities of the launched browser |
		Input Param:
			| None |
		Output:
			| Returns a dictionary
            | return_dict = {'status': 1 or non-zero (for failure), 'value': <Desired Capabilities Infor or Error Message (include exception info)>} |
        Usage:
            | browseractions.get_browser_desired_capabilities()
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            #input_dict['browser'] = self.getCurrentBrowser() #I think this design is not required
            logging.info('Sending Request to PSRS....')
            
            dict = {'api_name': 'get_browser_desired_capabilities'}
            return_dict = psrsclient.execute_api("POST", dict)
            #Retrun status check is required
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def verify(self, input_dict):
        '''
		Description:
		    | To verify element (button, checkbox, text) exists or not in the launched browser |
		Input Param:
			| input_dict (dict) (mandatory)
            | type  (mandatory)  - Element or Text - button, checkbox, text  |
            | value (mandatory)  - Locators or Text - Any of below mentioned locator OR text to verify (incase of type is text) in the browser |
            | Locators:
            | id or name or xpath             => btn_save or //div[@id="example"]
            | identifier:Either id or name 	=> identifier:example
            | id:element id                   => id:example
            | name:name attribute 	        => name:example
            | class:element class	            => class:example
            | tag:tag name	                => tag:div
            | xpath:xPath expression	        => xpath://div[@id="example"]
            | css:sSS selector                => css:div#example
            | dom:DOM expression              => dom:document.images[5]
            | link:Exact text a link has  	=> link:The example
            | partial link:Partial link text  => partial link:he ex
            | jquery:jQuery expression    	=> jquery:div.example
		Output:
			| Returns a dictionary
            | return_dict = {'status': 1 or non-zero (for failure), 'value': <Desired Capabilities Infor or Error Message (include exception info)>} |
        Usage:
            | input_dict = {'type' : "text", 'value' : "Ivanti Connect Secure"}
            | browseractions.verify(input_dict)
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            if not input_dict or not "type" in input_dict or not "value" in input_dict:
                return_dict['value'] = "Input parameters - input_dict dictionary or type or value key is missing.....please check the input dictionary"
            logging.info('Sending Request to PSRS....')
            dict = {'api_name': 'verify', 'params' : input_dict}
            return_dict = psrsclient.execute_api("POST", dict)
            #Retrun status check is required
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def maximize_window(self):
        '''
		Description:
		    | To maximize browser window |
		Input Param:
			| None |
		Output:
			| Returns a dictionary 
            | return_dict = {'status': 1 or non-zero (for failure), 'value': <Successful or Error Message (include exception info)>} |
        Usage:
            | browseractions.maximize_window()
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            logging.info('Sending Request to PSRS....')
            dict = {'api_name': 'maximize_window'}
            return_dict = psrsclient.execute_api("POST", dict)
            #Retrun status check is required
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict  

    def mouse_over(self, input_dict):
        '''
		Description:
		    | To move mouse over an element on a browser |
		Input Param:
		| input_dict['locator'](dictionary)(Mandatory) - 1.1.1.1 or google.com |
		Output:
			| Returns a dictionary 
            | return_dict = {'status': 1 or non-zero (for failure), 'value': <Successful or Error Message (include exception info)>} |
        Usage:
           |  input_dict['locator'] = "button:button1"
            | browseractions.mouse_over(input_dict)
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            #input_dict['browser'] = self.getCurrentBrowser() #I think this design is not required
            if not input_dict or not "locator" in input_dict:
                return_dict['value'] = "Input parameters - input_dict dictionary or locator key is missing.....please check the input dictionary"
            logging.info('Sending Request to PSRS....')
            
            dict = {'api_name': 'mouse_over', 'params': input_dict}
            return_dict = psrsclient.execute_api("POST", dict)
            #Retrun status check is required
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def focus(self, input_dict):
        '''
		Description:
		    | To focus over an element on a browser |
		Input Param:
			| input_dict['locator'](dictionary)(Mandatory) - 1.1.1.1 or google.com |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Successful or Error Message (include exception info)>} |
        Usage:
                | input_dict['locator'] = "button:button1"
            | browseractions.focus(input_dict)
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            #input_dict['browser'] = self.getCurrentBrowser() #I think this design is not required
            if not input_dict or not "locator" in input_dict:
                return_dict['value'] = "Input parameters - input_dict dictionary or locator key is missing.....please check the input dictionary"
            logging.info('Sending Request to PSRS....')
            
            dict = {'api_name': 'focus', 'params': input_dict}
            return_dict = psrsclient.execute_api("POST", dict)
            #Retrun status check is required
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def get_browser_window_size(self):
        '''
		Description:
		    | To get browser window size |
		Input Param:
			| None |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Dimensions of the browser windows OR Error Message (include exception info)>} |
        Usage:
            | browseractions.get_browser_window_size()
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            #input_dict['browser'] = self.getCurrentBrowser() #I think this design is not required
            logging.info('Sending Request to PSRS....')
            
            dict = {'api_name': 'get_browser_window_size'}
            return_dict = psrsclient.execute_api("POST", dict)
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def get_browser_title(self):
        '''
		Description:
		   |  To get browser window title |
		Input Param:
			| None |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Browser Window Title OR Error Message (include exception info)>} |
        Usage:
           |  browseractions.get_browser_title()
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            #input_dict['browser'] = self.getCurrentBrowser() #I think this design is not required
            logging.info('Sending Request to PSRS....')
            
            dict = {'api_name': 'get_browser_title'}
            return_dict = psrsclient.execute_api("POST", dict)
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def get_browser_url(self):
        '''
		Description:
		    | To get browser URL |
		Input Param:
			| None |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Browser URL OR Error Message (include exception info)>} |
        Usage:
            | browseractions.get_browser_url()
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            #input_dict['browser'] = self.getCurrentBrowser() #I think this design is not required
            logging.info('Sending Request to PSRS....')
            
            dict = {'api_name': 'get_browser_url'}
            return_dict = psrsclient.execute_api("POST", dict)
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def close_browser_window(self):
        '''
		Description:
            | To close the browser session and exit completely |

		Input Param:
			| None |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Success OR Error Message (include exception info)>} |
        Usage:
            | browseractions.close_browser_window()
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            logging.info('Sending Request to PSRS....')
            
            dict = {'api_name': 'close_browser_window'}
            return_dict = psrsclient.execute_api("POST", dict)
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def close_all_browsers_window(self):
        '''
		Description:
		    | To close session of all opened browsers and exit completely |
		Input Param:
			| None |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Success OR Error Message (include exception info)>} |
        Usage:
            | browseractions.close_all_browsers_window()
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            logging.info('Sending Request to PSRS....')
            
            dict = {'api_name': 'close_all_browsers_window'}
            return_dict = psrsclient.execute_api("POST", dict)
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def reload_page(self):
        '''
		Description:
		    | To refresh/reload the browser |
		Input Param:
			| None |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Success OR Error Message (include exception info)>} |
        Usage:
           |  browseractions.reload_page()
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            logging.info('Sending Request to PSRS....')
            
            dict = {'api_name': 'reload_page'}
            return_dict = psrsclient.execute_api("POST", dict)
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def capture_webpage_screenshot(self, input_dict):
        '''
		Description:
            | To capture browser screenshot, it will be stored in remote machine under ENV{PSTAF_HOME}/screeenshots/ folder, will be artifact incase of Jenkins |
		Input Param:
			| input_dict['filename'] (Dict)(Mandatory) - Filename without extension |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Success OR Error Message (include exception info)>} |
        Usage:
            | input_dict['filename'] = "GEN_001_FUNC_ADMIN_GUI"
            | browseractions.capture_webpage_screenshot(input_dict)
        '''
        return_dict = {'status': '0', 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            if not input_dict or not "filename" in input_dict:
                return_dict['value'] = "Input parameters - input_dict dictionary or filename key is missing.....please check the input dictionary"
            logging.info('Sending Request to PSRS....')
            
            dict = {'api_name': 'capture_webpage_screenshot', 'params': input_dict}
            return_dict = psrsclient.execute_api("POST", dict)
            #Retrun status check is required
            logging.info("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def click(self, input_dict):
        '''
		Description:
		    | To click on any element like button, link, image or any element on the browser |
		Input Param:
            | input_dict(dictionary)(Mandatory) |
            | input_dict['type']    (Mandatory) - button or link or image or element |
			| input_dict['locator'] (Mandatory) - Locator of the element (Please refer locator on top of the file) |
            | Locators:
            | id or name or xpath             => btn_save or //div[@id="example"]
            | identifier:Either id or name 	=> identifier:example |
            | id:element id                   => id:example |
            | name:name attribute 	        => name:example |
            | class:element class	            => class:example |
           |  tag:tag name	                => tag:div |
            | xpath:xPath expression	        => xpath://div[@id="example"] |
           | css:sSS selector                => css:div#example |
            | dom:DOM expression              => dom:document.images[5] |
           |  link:Exact text a link has  	=> link:The example |
           |  partial link:Partial link text  => partial link:he ex |
            | jquery:jQuery expression    	=> jquery:div.example |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Success OR Error Message (include exception info)>} |
        Usage:
            | input_dict = { "type" : "button", "locator" : "id:btn_save" }
          |                        OR
            | input_dict = {"type" : "link", "locator" : "link:Sign Out" }
             |                    OR
            | input_dict = { "type" : "image", "locator" : "img://img[@id="example" }
             |                    OR
           |  input_dict = { "type" : "element", "locator" : "identifier:example" } #it matches either id or name
            | browseractions.click(input_dict)
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            #input_dict['browser'] = self.getCurrentBrowser()  #I think this design is not required
            if not input_dict or not "type" in input_dict or not "locator" in input_dict:
                return_dict['value'] = "Input parameters - input_dict dictionary or type or locator key is missing.....please check the input dictionary"
            logging.info('Sending Request to PSRS....')
            dict = {'api_name': 'click', 'params': input_dict}
            return_dict = psrsclient.execute_api("POST", dict)
            #Retrun status check is required
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg
            #raise Exception(e)

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def navigate(self, input_dict):
        '''
		Description:
		    | To navigate to a page by clicking on any link on the browser |
		Input Param:
            | input_dict(dictionary)(Mandatory) |
            | input_dict['link']    (Mandatory) - String or Xpath |
            | Locators:
            | id or name or xpath             => btn_save or //div[@id="example"]
            | identifier:Either id or name 	=> identifier:example |
            | id:element id                   => id:example |
            | name:name attribute 	        => name:example |
            | class:element class	            => class:example |
           |  tag:tag name	                => tag:div |
            | xpath:xPath expression	        => xpath://div[@id="example"] |
           | css:sSS selector                => css:div#example |
            | dom:DOM expression              => dom:document.images[5] |
           |  link:Exact text a link has  	=> link:The example |
           |  partial link:Partial link text  => partial link:he ex |
            | jquery:jQuery expression    	=> jquery:div.example |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Success OR Error Message (include exception info)>} |
        Usage:
            | input_dict = { "link" : "//a[@href='/dana-admin/user/vdisessions.cgi']" }
            | browseractions.navigate(input_dict)
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            if not input_dict or not "link" in input_dict:
                return_dict['value'] = "Input parameters - input_dict dictionary or link key is missing.....please check the input dictionary"
            logging.info('Sending Request to PSRS....')
            dict = {'api_name': 'click', 'params': input_dict}
            return_dict = psrsclient.execute_api("POST", dict)
            #Retrun status check is required
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg
            #raise Exception(e)

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def switch_to_window(self, input_dict):
        '''
		Description:
		    | To switch to main or child window, it will not activate the window but the commands will be sent to the selected window |
		Input Param:
			| input_dict['window'](dictionary)(Mandatory) - "MAIN or NEW" |
            | MAIN - To select Parent Window |
            | NEW  - To select Recently opened child window |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Successful or Error Message (include exception info)>} |
        Usage:
            | input_dict['window'] = "MAIN or NEW"
            | browseractions.switch_to_window(input_dict)
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            if not input_dict or not "window" in input_dict:
                return_dict['value'] = "Input parameters - input_dict dictionary or window key is missing.....please check the input dictionary"
            logging.info('Sending Request to PSRS....')
            
            dict = {'api_name': 'switch_to_window', 'params': input_dict}
            return_dict = psrsclient.execute_api("POST", dict)
            #Retrun status check is required
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    #Not Ready For Use - TODO 
    def switch_browser(self, aliasname):
        #logging.info('Switch Browser to alias' + aliasname)
        #sl = BuiltIn().get_library_instance('SeleniumLibrary')
        #sl.switch_browser(aliasname)
        pass

    def set(self, input_dict):
        '''
		Description:
		    | To set the values to a textbox or select values in a drop down |
		    As of now the drop down values are selected based on the "value", API can be updated based on the requirement.
		Input Param:

            | input_dict(dictionary)(Mandatory) |
            | input_dict['type']    (Mandatory) - textbox or selectbox |
			| input_dict['locator'] (Mandatory) - Locator of the element (Please refer locator on top of the file) |
			| input_dict['value'] (Mandatory) - value that should be entered into the textbox or value that should
			be selected from the dropdown|
            | Locators:
            | id or name or xpath             => btn_save or //div[@id="example"]
            | identifier:Either id or name 	=> identifier:example |
            | id:element id                   => id:example |
            | name:name attribute 	        => name:example |
            | class:element class	            => class:example |
           |  tag:tag name	                => tag:div |
            | xpath:xPath expression	        => xpath://div[@id="example"] |
           | css:sSS selector                => css:div#example |
            | dom:DOM expression              => dom:document.images[5] |
           |  link:Exact text a link has  	=> link:The example |
           |  partial link:Partial link text  => partial link:he ex |
            | jquery:jQuery expression    	=> jquery:div.example |
		Output:
			| return_dict = {'status': 1 or non-zero (for failure), 'value': <Success OR Error Message (include exception info)>} |
        Usage:
            | input_dict = {"type": "textbox", "locator": "id:html5name", "value":"inputtext"}
            |                        OR
            | input_dict = {"type": "dropdown", "locator": "id:html5name", "value":"inputtext"}

            | browseractions.set(input_dict)
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            if not input_dict or not "type" in input_dict or not "locator" in input_dict or not "value" in input_dict:
                return_dict[
                    'value'] = "Input parameters - input_dict dictionary or type or locator key is missing.....please check the input dictionary"
            logging.info('Sending Request to PSRS....')
            dict = {'api_name': 'set', 'params': input_dict}
            return_dict = psrsclient.execute_api("POST", dict)
            # Retrun status check is required
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e)
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg
            # raise Exception(e)

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def browse(self, input_dict):
        '''
        Description:
           | This API is used to browse URL
        Input Param:
            login_dict = {
                 | "browser": "firefox",    (Optional)
                |  "url" : "http://certserverc.com",        (Mandatory)
        Output:
         | return_dict = {'status': 1 (success) or non-zero (for failure),
         'value': <Success OR Failure Message (include exception info)>} |
        Usage:
           browseractions.browse(input_dict)
        '''
        return_dict = {'status': '0', 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            logging.debug('Sending Request to PSRS....')

            if not "browser" in input_dict:
                input_dict['browser'] = config.getConfig('BROWSER_TYPE')
                logging.debug('BROWSER value taken from config.xml')

            if not "url" in input_dict:
                return_dict['value'] = "Mandatory input Parameter-URL missing....."
                return return_dict

            psrs_dict = {'api_name': 'browse', 'params': input_dict}
            return_dict = psrsclient.execute_api("POST", psrs_dict)
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e)
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict
        
    def get_html_source(self):
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            logging.info('Sending Request to PSRS....')
            dict = {'api_name': 'get_html_source'}
            return_dict = psrsclient.execute_api("POST", dict)
            #Retrun status check is required
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e) 
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def get(self,input_dict):
        '''
        Description:
        	To get the text of various web element properties
            	Input Param:
            		input_dict = {'type':'xpath',path: <xpath to the webelement>}
            	Output:
            		return_dict = {'status': 1 or non-zero (for failure), 'value': <Browser element property value (include exception info)>}
                Usage:
                    dict = {'api_name': 'get'}
                    url = "http://" + remote_server_ip + ":9999/execute_api"
                    return_dict = psrsclient.execute_api("POST", dict) (Please refer PSTAF - BrowserActions.py)
                                        OR
                    Python => return_dict = requests.post(url, json=dict, headers={"Content-Type": "application/json"}, timeout=(15, 300))
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            logging.info('Sending Request to PSRS....')
            dict = {'api_name': 'get','params':input_dict}
            return_dict = psrsclient.execute_api("POST", dict)
            print(return_dict)
            # Return status check is required
            logging.debug("Return Dict From PSRS:" + str(return_dict))
        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e)
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def handlecertpopups(self):
        '''
        Description:
  	         handle java cert popups
  	     Input Param:
			 None
		Output:
            return_dict = {'status': 1 or non-zero (for failure), 'value': <Browser element property value (include exception info)>}
        Usage:
           browser = BrowserActions()
           browser.handlecertpopups()
        '''
        return_dict = {'status': 0, 'value': None}
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            logging.info('Sending Request to PSRS....')
            dict = {'api_name': 'handlecertpopups'}
            return_dict = psrsclient.execute_api("POST", dict)
            logging.debug("Return Dict From PSRS:" + str(return_dict))
            if return_dict['status'] != 1:
                logging.error("Alert not present")
                return (config.getConfig('FAIL'))

        except:
            e = sys.exc_info()[1]
            exceptionmsg = "Exception in " + func_name + "(): " + str(e)
            logging.error(exceptionmsg)
            return_dict['value'] = exceptionmsg

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict





"""
========================================================================================================================
Author-Jagan Shankar,venkatesh, Raghu
Modified by-Jagan Shankar
Modified date- 21/Sep/2021
Bugs Fixed if any-<List Of Bugs>
pylintscore- 5.92
Licence -COPYRIGHT & LICENSE
Copyright 2021, Ivanti Secure, LLC, all rights reserved.
This program is free software; you can redistribute it and/or modify it under the same terms as Python itself.
========================================================================================================================
"""