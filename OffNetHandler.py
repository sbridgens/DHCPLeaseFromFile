#!/usr/bin/env python3
import json
import logging
import logging.handlers
from datetime import datetime

log=logging.getLogger('root')

class off_net_manager(object):

    """
    Helper function to detect and process an offnet circuit
    This creates a reverse lookup by taking the incoming layer2switchid l2sid
    and working backwards in the offnet config file to get the correct mdfid (bt exchange id)
    this allows parsing of the correct lease config
    """
    def get_offnet_leasefile(self, offnet_config, l2sId):
        try:
            # load the offnet config file each time to pick up any deltas.
            with open(offnet_config,'r') as f:
                # parse the json formatted file
                data = json.load(f)
                for config in data["Switches"]:
                    for l2s_list in config["L2SIds"]:
                        if l2sId in l2s_list:
                            # get the correct mdfid based on switch value and return
                            return config['MdfId']
        except Exception as offnetEx:
            log.error(f'Error obtaining offnet lease l2s config: {offnetEx}', exc_info=True)
