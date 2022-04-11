#!/usr/bin/env python3

import os
import sys
import time
import logging
from datetime import datetime
from configparser import ConfigParser
from LeaseHandler import lease_manager
from logging.handlers import RotatingFileHandler


configParse=ConfigParser()
# Static PATH if needed change to suite before creating the egg file
configParse.read('/etc/dhcp_config.ini')
lease_manager=lease_manager()

class ProcessDhcp(object):
    def __init__(self):
        self._logging_level=logging.INFO
        self.log = None
        self.logline = None
        self.dhcplogs = None
        self.logfile = None
        self.inode = None


    def config_value(self, param):
        return configParse.get('dhcp_params', param).strip('"')


    def prepend_log(self):
        with open(self.logfile,'r+') as logf:
            lcontent = logf.read()
            logf.seek(0)


    def initialise_logging(self):
        try:
            if not os.path.exists(self.config_value('log_file_directory')): 
                os.makedirs(self.config_value('log_file_directory'))

            self.logfile = os.path.join(self.config_value('log_file_directory'), 
                datetime.now().strftime(self.config_value('log_file_name')))

            max_bytes=int(self.config_value('log_size_in_bytes').strip())
            backup_Count=int(self.config_value('max_log_backups').strip())
            logFormatter = logging.Formatter(self.config_value('log_format'))
            rfhandler = RotatingFileHandler(
                            filename=self.logfile,
                            mode='a',
                            maxBytes=max_bytes, 
                            backupCount=backup_Count,
                            encoding=None,
                            delay=0)
            
            rfhandler.setFormatter(logFormatter)
            rfhandler.setLevel(self._logging_level)
            self.log = logging.getLogger('root')
            self.log.setLevel(self._logging_level)
            self.log.addHandler(rfhandler)
            self.inode = os.stat(self.logfile).st_ino
        except Exception as log_Ex:
            logging.error(f"Error encountered during log setup: {log_Ex}", exc_info=True)
            sys.exit(1)


    def Start_Polling(self):
        self.dhcplogs = self.config_value('dhcp_logFile_to_Poll')
        self.initialise_logging()
        try:
            while True:
                baseFile = open(self.dhcplogs,'r')
                # stat the file and get inode value for later use
                inoFile = os.fstat(baseFile.fileno()).st_ino
                # seek the end of the file
                baseFile.seek(0,2)
                while True:
                    # read the file
                    self.logline = baseFile.readline()
                    # get current file position
                    curr_position = baseFile.tell()
                    if self.logline is None:
                        # if null retry our file read
                        baseFile.seek(curr_position)
                        break
                    # stdout performs better than print on fast moving processes use for debug only!
                    # sys.stdout.write(line)
                    if "leaseoption82" in self.logline.lower():
                        # detect log rotation
                        newNode = os.stat(self.logfile).st_ino
                        if self.inode != newNode:
                            # bring out the duck!
                            self.prepend_log()
                            self.inode = newNode
                        #process line
                        lease_manager.configParse = configParse
                        lease_manager.parse_log_line(self.logline)
                    try:
                        # update file position
                        baseFile.seek(curr_position)
                        # stat file and check if inode changed
                        if os.stat(self.dhcplogs).st_ino != inoFile:
                            # reparse the file and update values if the inode value changes and restart loop
                            newFile = open(self.dhcplogs,'r')
                            baseFile.close()
                            baseFile = newFile
                            inoFile = os.fstat(baseFile.fileno()).st_ino
                            continue
                        # without a sleep cpu cycles increase to 99%
                        # every 0 after decimal place appears adds 10% to the cpu usage
                        time.sleep(0.0001)
                    except IOError:
                            # retry read
                            time.sleep(0.01)
                            break
        except Exception as ex:
            logging.error(f'Exception while reading Log:{baseFile} with error: {ex.message}')



def check_config():
    config = '/etc/dhcp_config.ini'
    if not os.path.exists(config):
        return False
    else:
        return True


def main():
    if check_config():
        # Start Polling
        parse_option82 = ProcessDhcp()
        parse_option82.Start_Polling()
    else:
        msg ="Could not find config file: /etc/dhcp_config.ini"
        logging.error(msg)
        print(msg)


if __name__ == "__main__":
    #lets go
    main()

