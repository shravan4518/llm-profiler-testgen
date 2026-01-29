"""
Demo Suite Loader - Load framework-specific demo test suite examples
Provides test patterns and examples for LLM-based test generation
"""

import logging
from pathlib import Path
from typing import Dict
import PyPDF2

logger = logging.getLogger(__name__)


def load_demo_suite(framework_type: str = "pstaff") -> str:
    """
    Load framework-specific demo test suite examples

    Args:
        framework_type: "pstaff" or "client"

    Returns:
        Demo suite content as string
    """
    if framework_type == "client":
        return load_client_demo_suite()
    else:
        return load_pstaff_demo_suite()


def load_client_demo_suite() -> str:
    """Load aut-pypdc client framework demo suite with PPS adaptations"""

    # PCS demo suite examples (from PDF)
    pcs_demo = """
=== CLIENT FRAMEWORK DEMO SUITE EXAMPLES (PCS - Adapt for PPS) ===

## File Structure:
1. Feature_Data.py      - Test data and configuration
2. Feature_TestSuite.py - Test case functions
3. Feature_Test.py      - Pytest runner

## EXAMPLE 1: Data File Pattern

```python
# Profiler_Config_Data.py
from FWUtils import FWUtils

objFWUtils = FWUtils()
pps_ip = objFWUtils.get_config('DEVICE')['IP']['MGMT']

# Use CAPITAL LETTERS for constants
WMI_CONFIG = {
    'enabled': True,
    'timeout': 60,
    'deep_scan': False
}

PROFILER_ENDPOINT = 'https://' + pps_ip
```

## EXAMPLE 2: TestSuite File Pattern

```python
# Profiler_Config_TestSuite.py
from FWUtils import FWUtils
from Initialize import Initialize
from CommonUtils import CommonUtils
from Profiler_Config_Data import *
from admin_pps.PpsRestUtils import PpsRestClient
from admin_pps.authentication import Authentication
import sys

# Create required objects
objFwUtils = FWUtils()
log = objFwUtils.get_logger(__name__, 1)
objInitialize = Initialize()
objCommonUtils = CommonUtils()

# PPS REST client for Profiler
pps_client = PpsRestClient()

def INITIALIZE():
    tc_id = sys._getframe().f_code.co_name
    log.info('-' * 50)
    log.info(tc_id + ' [START]')

    try:
        step_text = "Initializing the test bed"
        log.info(step_text)
        return_dict = objInitialize.initialize()
        assert return_dict['status'] == 1, "Failed to initialize Test Bed"

        step_text = "Logging into PPS as admin"
        log.info(step_text)
        # PPS client automatically handles authentication
        log.info("PPS REST client initialized")

        log.info(tc_id + ' [PASSED]')
        eresult = True

    except AssertionError as e:
        log.error(e)
        log.info(tc_id + ' [FAILED]')
        if objCommonUtils.get_screenshot(file_name=tc_id) is None:
            log.error('Failed to get screenshot')
        eresult = False

    log.info(tc_id + ' [END]')
    log.info('-' * 50)
    return eresult


def TC_001_PPS_CONFIGURE_WMI():
    tc_id = sys._getframe().f_code.co_name
    log.info('-' * 50)
    log.info(tc_id + ' [START]')

    try:
        step_text = "Configuring WMI profiling"
        log.info(step_text)

        # Use PPS REST API
        uri = "/api/v1/configuration/profiler/wmi"
        payload = WMI_CONFIG

        response = pps_client.execute_request(
            resource_uri=uri,
            method_type=pps_client.PUT,
            payload=payload
        )
        assert response.status_code == 200, f"Failed to configure WMI: {response.text}"

        step_text = "Verifying WMI configuration"
        log.info(step_text)

        response = pps_client.execute_request(
            resource_uri=uri,
            method_type=pps_client.GET
        )
        assert response.status_code == 200, "Failed to verify WMI config"
        config = response.json()
        assert config['enabled'] == WMI_CONFIG['enabled'], "WMI enabled mismatch"

        log.info(tc_id + ' [PASSED]')
        eresult = True

    except AssertionError as e:
        log.error(e)
        log.info(tc_id + ' [FAILED]')
        if objCommonUtils.get_screenshot(file_name=tc_id) is None:
            log.error('Failed to get screenshot')
        eresult = False

    log.info(tc_id + ' [END]')
    log.info('-' * 50)
    return eresult


def CLEANUP():
    tc_id = sys._getframe().f_code.co_name
    log.info('-' * 50)
    log.info(tc_id + ' [START]')

    try:
        step_text = "Cleaning up test environment"
        log.info(step_text)

        log.info(tc_id + ' [PASSED]')
        eresult = True

    except AssertionError as e:
        log.error(e)
        log.info(tc_id + ' [FAILED]')
        eresult = False

    log.info(tc_id + ' [END]')
    log.info('-' * 50)
    return eresult
```

## EXAMPLE 3: Pytest Runner Pattern

```python
# Profiler_Config_Test.py
import pytest
from Profiler_Config_TestSuite import *

def setup_module():
    assert INITIALIZE() is True

def test_1_TC_001_PPS_CONFIGURE_WMI():
    assert TC_001_PPS_CONFIGURE_WMI() is True

def teardown_module():
    assert CLEANUP() is True
```

## KEY PATTERNS FOR PROFILER (PPS):

1. **Imports for PPS**:
   ```python
   from admin_pps.PpsRestUtils import PpsRestClient
   from admin_pps.authentication import Authentication
   from admin_pps.endpoint_policy import EndpointPolicy
   from admin_pps.users import Users
   ```

2. **PPS REST Client Usage**:
   ```python
   pps_client = PpsRestClient()

   # GET request
   response = pps_client.execute_request(
       resource_uri="/api/v1/configuration/...",
       method_type=pps_client.GET
   )

   # PUT request with payload
   response = pps_client.execute_request(
       resource_uri="/api/v1/configuration/...",
       method_type=pps_client.PUT,
       payload={'key': 'value'}
   )
   ```

3. **Test Function Pattern**:
   ```python
   def TC_<ID>_PPS_<DESCRIPTION>():
       tc_id = sys._getframe().f_code.co_name
       log.info('-' * 50)
       log.info(tc_id + ' [START]')

       try:
           step_text = "Description of step"
           log.info(step_text)

           # Test logic
           response = pps_client.execute_request(...)
           assert response.status_code == 200, "Error message"

           log.info(tc_id + ' [PASSED]')
           eresult = True

       except AssertionError as e:
           log.error(e)
           log.info(tc_id + ' [FAILED]')
           eresult = False

       log.info(tc_id + ' [END]')
       log.info('-' * 50)
       return eresult
   ```

4. **Profiler-Specific URIs**:
   - WMI Config: `/api/v1/configuration/profiler/wmi`
   - SSH Config: `/api/v1/configuration/profiler/ssh`
   - SNMP Config: `/api/v1/configuration/profiler/snmp`
   - Authentication: `/api/v1/configuration/authentication/signin/urls/access-url/`
   - Users: `/api/v1/configuration/users/user/`
"""

    return pcs_demo


def load_pstaff_demo_suite() -> str:
    """Load PSTAFF framework demo suite examples"""

    pstaff_demo = """
=== PSTAFF FRAMEWORK DEMO SUITE EXAMPLES ===

## Robot Framework File Pattern

```robot
*** Settings ***
Library    aut-pstaf.RestClient
Library    Collections

*** Variables ***
${DEVICE_IP}    10.0.0.1
${USERNAME}     admin
${PASSWORD}     password

*** Test Cases ***
Configure Basic Settings
    [Documentation]    Configure basic device settings
    [Tags]    configuration

    ${response}=    POST    /api/v1/config    {"setting": "value"}
    Should Be Equal As Integers    ${response.status_code}    200
```

## Python Helper Pattern

```python
from aut-pstaf.RestClient import RestClient

class TestHelpers:
    def __init__(self):
        self.client = RestClient()

    def configure_setting(self, setting, value):
        response = self.client.post('/api/v1/config',
                                   {'setting': setting, 'value': value})
        assert response.status_code == 200
        return response.json()
```
"""

    return pstaff_demo


def get_framework_summary(framework_type: str) -> Dict:
    """Get summary of framework characteristics"""

    if framework_type == "client":
        return {
            'name': 'aut-pypdc Client Framework',
            'description': 'Profiler-specific framework with PpsRestClient',
            'file_pattern': ['Data.py', 'TestSuite.py', 'Test.py'],
            'test_runner': 'pytest',
            'key_imports': [
                'from FWUtils import FWUtils',
                'from Initialize import Initialize',
                'from admin_pps.PpsRestUtils import PpsRestClient'
            ],
            'api_pattern': '/api/v1/configuration/...'
        }
    else:  # pstaff
        return {
            'name': 'PSTAFF Framework',
            'description': 'Generic Policy Secure testing framework',
            'file_pattern': ['test.robot', 'test.py', 'data.py'],
            'test_runner': 'robot',
            'key_imports': [
                'from aut-pstaf.RestClient import RestClient'
            ],
            'api_pattern': '/api/...'
        }
