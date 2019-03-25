import datetime
import os
import paramiko
import sys
import time
import logging
logging.getLogger('paramiko.transport').setLevel(logging.ERROR)


class InstallSWException(Exception):
    ''' Exception thrown when an install component fails. '''
    pass

class InstallSW:
    '''
    This class is used for installing software
    '''
    
    # Contextualization, install the software for IPython and PyURDME.
    # Commands can be specified in 3 ways:
    # 1:  a string
    # 2:  a list a strings
    # 3:  a tuple, where the first item is a list of string and the 2nd item is a string.  The second
    #         item is a 'check' command, which should error (return code 1) if the first item(s) did not
    #         install correctly
    command_list = [
        
        # Basic contextualization
        "curl http://www.ubuntu.com", # Check to make sure networking is up.
        "sudo apt-get update",
        "sudo apt-get -y install git",
        "sudo apt-get -y install cmake gsl-bin libgsl0-dev",
        "sudo apt-get -y install python3-dev python3-pip",
        "sudo pip3 install dask[complete]",
        "sudo pip3 install bokeh",
        "sudo apt-get -y install python3-setuptools",
        "sudo apt-get -y install make",
        "sudo pip3 install retrying",
        "sudo pip3 install matplotlib",
                    
        # FEniCS
        #[
        # "sudo apt-get install software-properties-common",
        # "sudo add-apt-repository ppa:fenics-packages/fenics",
        # "sudo apt-get update",
        # "sudo apt-get install --no-install-recommends fenics"
        #],


        # So the workers can mount the controller via SSHfs
        [   "sudo apt-get -y install sshfs",
         #  "sudo gpasswd -a ubuntu fuse",
            "echo 'ServerAliveInterval 60' >> /home/ubuntu/.ssh/config",
        ],

                    
        # For the smart workflow
        [
            "sudo pip3 install sklearn",
            "sudo pip3 install tsfresh",
            "sudo rm -rf /usr/local/GPflowOpt;sudo mkdir -p /usr/local/GPflowOpt;sudo chown ubuntu /usr/local/GPflowOpt",
            "cd /usr/local/ && git clone https://github.com/GPflow/GPflowOpt.git",
            "cd /usr/local/GPflowOpt && sudo pip3 install . --process-dependency-links",
            "sudo rm -rf /usr/local/mio;sudo mkdir -p /usr/local/mio;sudo chown ubuntu /usr/local/mio",
            "cd /usr/local/ && git clone https://bitbucket.org/prashant_singh/mio.git",
            "cd /usr/local/mio && sudo python3 setup.py install"
        ],
                    
        # Jupyter notebook, python2 and python3 kernels
        [
           "sudo pip3 install jupyter",          
           "ipython profile create default"
        ],

        ## Install StochSS and GillesPy2
        [

            "sudo rm -rf /usr/local/gillespy2;sudo mkdir -p /usr/local/GillesPy2;sudo chown ubuntu /usr/local/GillesPy2",
            "cd /usr/local/ && git clone https://github.com/Wrede/GillesPy2.git",
            "cd /usr/local/GillesPy2 && git checkout dev_events && sudo python3 setup.py install"
            
            #"sudo pip3 install gillespy2"
        ],
          
        # Ochestral
        #[
        #  "git clone https://ahellander@bitbucket.org/Aratz/orchestral.git && cd orchestral && git checkout DLCM_cloud",
        #  "cd orchestral && git clone https://github.com/Aratz/modern_egfrd.git && cd modern_egfrd && git checkout orchestral",
        #  "mkdir orchestral/modern_egfrd/build",
        #  "cd orchestral/modern_egfrd/build && cmake -DCMAKE_BUILD_TYPE=Release .. && make RunGfrd",
        #],
                    
        "sync",  # This is critial for some infrastructures.
    ]
    
    # How many time do we try to install each package.
    NUM_INSTALL_RETRIES = 5
    # How long (in second to wait between package install attempts.
    INSTALL_RETRY_WAITTIME = 2
    # How many times to do try to connect to the server.
    MAX_NUMBER_SSH_CONNECT_ATTEMPTS = 100
    # How long (in seconds) to wait between ssh connect attempts.
    SSH_CONNECT_WAITTIME = 5
    # Default SSH port
    DEFAULT_SSH_PORT = 22

    def __init__(self, hostname, config=None, ssh_endpoint=None, username=None, password=None):
        if config is not None:
            self.config = config
        if ssh_endpoint is None:
            ssh_endpoint = self.DEFAULT_SSH_PORT
        if username is None:
            self.username = self.config['login_username']
        else:
            self.username = username
        self.password = password
        self.hostname = hostname
        self.ssh_endpoint = ssh_endpoint
        self.keyfile = self.config.sshkeyfilename()
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.log_file = None

    def connect(self):
        print "Connecting to {0}:{1} keyfile={2}".format(self.hostname,self.ssh_endpoint,self.keyfile)
        for i in range(self.MAX_NUMBER_SSH_CONNECT_ATTEMPTS):
            try:
                self.ssh.connect(self.hostname, self.ssh_endpoint, username=self.username, 
                    key_filename=self.keyfile)
                print "SSH connection established"
                return
            except Exception as e:
                #logging.exception(e)
                print "Retry in {0} seconds...\t\t{1}".format(self.SSH_CONNECT_WAITTIME,e)
                time.sleep(self.SSH_CONNECT_WAITTIME)
        print "ssh connect Failed!!!\t{0}:{1}".format(self.hostname,self.ssh_endpoint)
        raise Exception("Can not connect to {0}:{1}".format(self.hostname,self.ssh_endpoint))

    def run_with_logging(self):
        logging.debug("run_with_logging()")
        try:
            self.connect()
            if self.check_if_pyurdme_installed():
                print "pyurdme is already installed, skipping install."
            else:
                self.log_file = open('molns_install.log','w')
                self.log_exec('MOLNs Install Started: '+str(datetime.datetime.now())+'\n')
                logging.debug("MOLNs Install Started: {0}".format(datetime.datetime.now()))
                try:
                    self.exec_command_list_switch(self.command_list)
                    self.log_exec('\nMOLNs Install Completed: '+str(datetime.datetime.now())+'\n')
                    logging.debug("MOLNs Install Complete: {0}".format(datetime.datetime.now()))
                except Exception as e:
                    logging.exception(e)
                    raise sys.exc_info()[1], None, sys.exc_info()[2]
                finally:
                    self.log_file.close()
        except Exception as e:
            logging.exception(e)
            raise sys.exc_info()[1], None, sys.exc_info()[2]
        finally:
            self.ssh.close()

    def run(self):
        self.connect()
        if self.check_if_pyurdme_installed():
            print "pyurdme is already installed, skipping install."
        else:
            self.exec_command_list_switch(self.command_list)
        self.ssh.close()

    def exec_command_list_switch(self, command_list):
        # get total size:
        command_cnt=0
        for i in InstallSW.command_list:
            if isinstance(i,list):
                command_cnt += len(i)
            else:
                command_cnt += 1
        command_exec_cnt = 0
        tic = time.time()
        # execute commands
        for command_obj in command_list:
            #logging.debug("exec_command_list_switch(): command_obj={0}".format(command_obj))
            fix_command = None
            if isinstance(command_obj, str):
                command_group_list = [command_obj]
                if "apt-get -y install" in command_obj:
                    # For unknown reasons, apt-get will fail, and need to be re-updated.
                    # This code seems to fix this transient error.
                    fix_command = "sudo apt-get update"
            elif isinstance(command_obj, list):
                command_group_list = command_obj
            elif isinstance(command_obj, tuple):
                if isinstance(command_obj[0], list):
                    command_group_list = command_obj[0]
                else:
                    command_group_list = [command_obj[0]]
                fix_command = command_obj[1]
            else:
                raise InstallSWException("exec_command_list_switch: got unknown command {0}".format(command_obj))
            
            install_success = False
            for attempt_num in range(0, self.NUM_INSTALL_RETRIES):
                try:
                    #logging.debug("command_group_list={0}".format(command_group_list))
                    for n, command in enumerate(command_group_list):
                        #logging.debug("command={0}".format(command))
                        if attempt_num == 0:
                            #print "EXECUTING...\t{0}:{1}\t{2}".format(self.hostname, self.ssh_endpoint, command)
                            print "[{0}/{1}] EXECUTING...\t{2}".format(command_exec_cnt+n, command_cnt, command)
                        else:
                            print "RETRY {3}.....\t{2}".format(self.hostname, self.ssh_endpoint, command, attempt_num)
                        self.exec_command(command, verbose=False)
                    install_success = True
                    command_exec_cnt += len(command_group_list)
                    break
                except InstallSWException as e:
                    if fix_command is not None:
                        try:
                            print "FIXING......\t{0}".format(fix_command)
                            self.exec_command(fix_command)
                            print "FIX WORKED.."
                        except InstallSWException as e:
                            print "FIX FAILED...\t{0}".format(e)
                            
                    time.sleep(self.INSTALL_RETRY_WAITTIME)

            if not install_success:
                raise SystemExit("CRITICAL ERROR: could not complete command '{0}'. Exiting.".format(command))
        print "Installation complete in {0}s".format(time.time() - tic)


    def log_exec(self, msg):
        if self.log_file is not None:
            self.log_file.write(msg)
            self.log_file.flush()

    def check_if_pyurdme_installed(self):
        try:
           self.exec_command('source /usr/local/pyurdme/pyurdme_init && python -c "import pyurdme"', verbose=False)
           return True
        except InstallSWException:
            return False

    def exec_command(self, command, pretty_command=None, verbose=True):
        if pretty_command is None:
            pretty_command = command
        try:
            stdout_data = []
            stderr_data = []
            self.log_exec('\n\nInstallSW.exec_command({0})\n'.format(command))
            session = self.ssh.get_transport().open_session()
            session.exec_command(command)
            nbytes = 4096
            #TODO add a timeout here, don't wait for commands forever.
            while True:
                if session.recv_ready():
                    msg = session.recv(nbytes)
                    stdout_data.append(msg)
                    self.log_exec(msg)
                if session.recv_stderr_ready():
                    msg = session.recv_stderr(nbytes)
                    stderr_data.append(msg)
                    self.log_exec(msg)
                if session.exit_status_ready():
                    break
                time.sleep(0.1) # Sleep breifly to prevent over-polling

            status = session.recv_exit_status()
            self.log_exec('\nInstallSW.exec_command({0}) Exit Status={1}'.format(command, status))
            str_return = ''.join(stdout_data).splitlines()
            stderr_str = ''.join(stderr_data)
            session.close()
            if status != 0:
                raise paramiko.SSHException("Exit Code: {0}\tSTDOUT: {1}\tSTDERR: {2}\n\n".format(status, "\n".join(str_return), stderr_str))
            if verbose:
                print "OK.........."
            return str_return
        except paramiko.SSHException as e:
            if verbose:
                print "FAILED......\t{0}".format(e)
            raise InstallSWException()

    def exec_multi_command(self, command, next_command):
        try:
            stdin, stdout, stderr = self.ssh.exec_command(command)
            stdin.write(next_command)
            stdin.flush()
            status = stdout.channel.recv_exit_status()
            if status != 0:
                raise paramiko.SSHException("Exit Code: {0}\tSTDOUT: {1}\tSTDERR: {2}\n\n".format(status, stdout.read(), stderr.read()))
        except paramiko.SSHException as e:
            print "FAILED......\t{0}:{1}\t{2}\t{3}".format(self.hostname, self.ssh_endpoint, command, e)
            raise InstallSWException()

if __name__ == "__main__":
    print "{0}".format(InstallSW.command_list)
    print "len={0}".format(len(InstallSW.command_list))
    cnt=0
    for i in InstallSW.command_list:
        if isinstance(i,list):
            cnt += len(i)
        else:
            cnt += 1
    print "cnt={0}".format(cnt)

