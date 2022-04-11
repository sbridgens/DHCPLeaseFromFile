#!/usr/bin/env python3
import os
import re
import logging
import logging.handlers
from datetime import datetime
from OffNetHandler import off_net_manager

log=logging.getLogger('root')

off_net_manager=off_net_manager()

class lease_manager(object):
    def __init__(self):
        self.configParse = None
        self.logline = None
        self.logFields = None
        self.hostCid = None
        self.ip_address = None
        self.newCid = None
        self.mdfId = None
        self.leaseFile = None
        self.leaseDict = None
        self.leaseConfig = None


    """Helper function to read config values"""
    def config_value(self, param):
        return self.configParse.get('dhcp_params', param).strip('"')


    """Set Lease handler variables"""
    def set_workflow_vars(self):
        self.logFields = self.logline.split()
        self.hostCid = self.logFields[7].strip('"')
        self.ip_address = self.logFields[6]
        self.newCid = f'\"{self.hostCid} {self.logFields[8]} {self.logFields[9]}'.strip()
        self.leaseFile = None


    """Helper function to detect the correct circuit id based on incoming dhcp request"""
    def detect_cid_config(self):
        return "HVW" if len(self.hostCid) == 0 else ("OffNet" if "BAA" in self.hostCid else "OnNet")


    """"Helper funtion to split the option82 line into a list"""
    def parse_configLine(self):
        # get match group 1 and disregard remaining results
        self.leaseConfig = self.leaseConfig[0]
        # split the single line into a list
        self.leaseDict = self.leaseConfig.split(' ')


    """
    Validate the order of the incoming dhcp request 
    to ensure formatting has not changed
    """
    def validate_dhcp_format(self):
        return True if (self.leaseDict[5] in self.config_value('field_validators') 
            and self.leaseDict[9] in self.config_value('field_validators')) \
        else False


    """
    Set the lease value line to the correct format ensuring the circuit id 
    block section is correctly replaced with the option 82 circuit information
    """
    def parse_lease_values(self):
        # subsitute the block with the new CiruitID (CID)
        self.leaseDict[10] = self.newCid
        # remove last lease section as this is the block data
        self.leaseDict.remove(self.leaseDict[11])
        # create the new Lease line
        return ' '.join([str(value) for value in self.leaseDict])


    """
    Write the updated lease information to the correct dhcp lease file
    """
    def update_leases(self, data):
        # print("Updating Lease Data")
        # open lease file in write mode
        with open(self.leaseFile,'w') as file:
            try:
                # write the static lease data
                file.write(data)
                log.info("Lease successfully written to file.")
                # print("Data Written")
            except Exception as e:
                # log error
                log.error(f'Error updating DHCP results in file: {e}', exc_info=True)
        

    """Read the correct dhcp lease config file based on host circuit id."""
    def read_leases(self):
        searchValue = f'\"{self.hostCid} block-.*[0-9]\";'
        with open(self.leaseFile, 'r') as file:
            data = file.read()
            self.leaseConfig = re.findall(f'host\sHOST-.*{searchValue}\s\}}',data)
            if self.leaseConfig:
                self.parse_configLine()
                # verify format using list positions of know values
                # fixed-address & agent.circuit-id
                if self.validate_dhcp_format():
                    # double check we have a valid match against the circuit id sent in
                    if not self.newCid in data:
                        log.info(f'Available Lease found with IP: {self.leaseDict[6]} and CID: {self.newCid.strip()}')
                        # create the new Lease line
                        cidResults = self.parse_lease_values()
                        # Replace the old line with the new lease line
                        data = re.sub(self.leaseConfig, cidResults, data)
                        self.update_leases(data)
                    # Cid exists so likely not picked up static address
                    else:
                        log.error(f'Duplicate CID received: {self.newCid}, possible DHCP service has not restarted?')
                else:
                    log.error("fatal error - dhcp file format has changed")
            else:
                # no block data in file so no more leases log as an error.
                log.error(f'No Leases Available? CID: {self.newCid}')


    """Function to parse the incoming Option82 log line and start parsing"""
    def parse_log_line(self, logline):
        # Parse logline and set workflow variables
        self.logline = logline
        self.set_workflow_vars()
        processType = self.detect_cid_config()
        log.info(f"Lease request with CID: {self.hostCid} and Process Type: {processType}")
        if processType.lower() == "hvw":
            # A Null host cid means the request is from Haverford West
            # Log example: Feb  9 03:52:48 swhv-dhcp-hsi0 dhcpd[21744]: LeaseOption82 185.126.248.160 " eth 1/1/05/11/4/1/1";
            self.leaseFile = os.path.join(self.config_value('dhcp_config_root'), "dhcpd-004HVW1.conf")
        elif processType.lower() == "offnet":
            # hostCid's starting with BAA are Offnet.
            # Log example: Feb  9 11:09:57 ngd-dhcp-hsi0 dhcpd[96783]: LeaseOption82 194.150.200.162 "BAAHPM xpon 0/13/10:2.1.101";
            log.info("Offnet request detected searching for correct MDFID")
            self.mdfId = off_net_manager.get_offnet_leasefile(self.config_value('offnet_config'), self.hostCid)
            if self.mdfId:
                log.info(f"Offnet MDFID found: {self.mdfId}, using value to detect correct lease file")
                self.leaseFile = os.path.join(self.config_value('dhcp_config_root'), f"dhcpd-offnet-{self.mdfId}.conf")
                self.hostCid = self.config_value('offnet_host_cid').strip()
            else:
                log.error(f"No valid offnet config found for L2SId: {self.hostCid}!")
                return
        else:
            # Other network hostCid's are based on OLT areas:
            # Log example: Feb  9 04:05:10 swag-dhcp-hsi0 dhcpd[96015]: LeaseOption82 185.81.252.57 "001ABG1 eth 1/1/03/01/2/1/1";
            self.leaseFile = os.path.join(self.config_value('dhcp_config_root'), f"dhcpd-{self.hostCid}.conf")
        log.info(f"Lease file being used for request: {self.leaseFile}")
        self.read_leases()

