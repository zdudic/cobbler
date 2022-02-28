#!/bin/env python

# this was written for python2
# Import cobbler disto, arguments are:
# $1 = http or nfs path to iso
# $2 = arch
# ks file is hardcoded, /var/lib/cobbler/kickstarts/default.ks
# -----------------------------------------------------------

import os
from time import gmtime, strftime
import datetime
import getpass
import distutils.spawn  # check if cobbler is installed
import subprocess
import wget
import sys
import re  # regex
import argparse
import logging, logging.handlers
import smtplib  # sending email, plain text
from email.mime.text import MIMEText

# --- define colors
class color:
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    DARKCYAN = '\033[36m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# -- Does root run this?
def i_am_root():
    """
    Exit if root doesn't run the script
    """
    i_am = getpass.getuser()
    return True if i_am == "root" else False

if not i_am_root():
    sys.exit(color.RED + "Only root can run this script." + color.END)

# -- argument work
parser = argparse.ArgumentParser(description='Import new distro into Cobbler')
parser.add_argument("-p", "--path", help="[ HTTP(s) | NFS ] path of an ISO", required=True)
parser.add_argument("-a", "--arch", help="Distro architecture, supported are: i386, x86_64, arm", required=True)
parser.add_argument("-n", "--nickname", help="Nickname for distribution")
args = parser.parse_args()
iso_source_path = args.path
distro_arch = args.arch
nickname = args.nickname

# -- define LOGGING
PROGRAM = os.path.basename(sys.argv[0])  # name of this script
LOG_PATH = ("/var/log/" + PROGRAM)  # put together "/var/log/<script_name>"
if not os.path.exists(LOG_PATH):  # create LOG_PATH if doesn't exists
    os.makedirs(LOG_PATH)
    os.chown(LOG_PATH, -1, 0)  # root(-1 means no change)
    os.chmod(LOG_PATH, 0775)
LOG_FILE = (LOG_PATH + "/" + datetime.datetime.now().strftime("%m-%d-%Y_%Hh%Mm%Ss"))
formatter = logging.Formatter('%(asctime)s:%(levelname)s: %(message)s')
handler = logging.handlers.TimedRotatingFileHandler(LOG_FILE, when='MIDNIGHT', backupCount=50, utc=False)
handler.setFormatter(formatter)
# Set up a specific logger with our desired output level
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

logger.debug("")
logger.debug(color.GREEN + "START AT : " + strftime("%a, %d %b %Y %H:%M:%S", gmtime()) + color.END)

KS_FILE = "/var/lib/cobbler/kickstarts/default.ks"
VALID_ARCH = re.compile('[iI]386$|[xX]86_64$|[aA][rR][mM]$')
NEW_DISTRO_NAME = subprocess.check_output(['basename %s .iso' % iso_source_path],
                                          shell=True).rstrip()  # rstrip() remove \n
ISO_NAME = subprocess.check_output(['basename %s' % iso_source_path], shell=True).rstrip()


def find_download_location(location="/tmp/"):
    """
    Function has one argument, if it's not provided, then it's /tmp/
    """
    global DOWNLOAD_PLACE
    if os.path.isdir(location):
        DOWNLOAD_PLACE = location
    else:
        DOWNLOAD_PLACE = "/tmp/"

def is_cobbler_installed():
    """
    Check if Cobbler is present
    """
    logger.debug("Check if Cobbler app is installed")
    print("Check if Cobbler app is installed")
    if not distutils.spawn.find_executable("cobbler"):
        logger.debug(color.RED + "Cobbler is not installed on this system." + color.END)
        sys.exit(color.RED + "Cobbler is not installed on this system." + color.END)

def is_distro_present():
    """
    Check if distro already exists
    """
    logger.debug("Check if " + NEW_DISTRO_NAME + " is present.")
    print("Check if " + NEW_DISTRO_NAME + " is present.")
    # NEW_DISTRO_STATUS = subprocess.call(['basename %s .iso' % iso_source_path], shell=True)  # returns $?
    # print ("exit status :" + str(NEW_DISTRO_STATUS))
    # NEW_DISTRO_NAME = subprocess.check_output(['basename %s .iso' % iso_source_path], shell=True)   # return output
    # print ("command's output :" + NEW_DISTRO_NAME)
    LIST_DISTRO = subprocess.check_output(['cobbler distro list'], shell=True)  # this is string
    if LIST_DISTRO.find(NEW_DISTRO_NAME) != -1:  # .find returs index if found, and -1 otherwise
        logger.debug("Distro " + NEW_DISTRO_NAME + " is already present.")  # rstrip() remove \n
        sys.exit("Distro " + NEW_DISTRO_NAME + " is already present.")

def get_http_iso():
    """
    Get ISO image from HTTP server using wget
    """
    if not os.path.exists(DOWNLOAD_PLACE):
        logger.debug("Directory " + DOWNLOAD_PLACE + " doesn't exist, check why?")
        sys.exit("Directory " + DOWNLOAD_PLACE + " doesn't exist, check why?")
    try:
        logger.debug("Wget downloading %s " % ISO_NAME)
        print("Wget downloading %s " % ISO_NAME)
        os.chdir(DOWNLOAD_PLACE)
        file = wget.download(iso_source_path)
        logger.debug("%s is downloaded" % ISO_NAME)
        print("\n %s is downloaded" % ISO_NAME)
    except:
        logger.debug("Can't wget %s " % ISO_NAME)
        sys.exit("Can't wget %s " % ISO_NAME)

def get_nfs_iso():
    """
    Get ISO image from NFS server using rsync
    """
    if not os.path.exists(DOWNLOAD_PLACE):
        logger.debug("Directory " + DOWNLOAD_PLACE + " doesn't exist, check why?")
        sys.exit("Directory " + DOWNLOAD_PLACE + " doesn't exist, check why?")
    try:
        logger.debug("Rsync-ing %s " % ISO_NAME)
        print("Rsync-ing %s " % ISO_NAME)
        os.chdir(DOWNLOAD_PLACE)
        subprocess.call(['rsync --progress -avH %s %s%s'
                         % (iso_source_path, DOWNLOAD_PLACE, ISO_NAME)], shell=True)
        logger.debug("%s is rsync-ed" % ISO_NAME)
        print("\n %s is rsync-ed" % ISO_NAME)
    except:
        logger.debug("Can't rsync %s from NFS server" % ISO_NAME)
        sys.exit("Can't rsync %s from NFS server" % ISO_NAME)

def find_iso_path_type_and_get_iso():
    """
    Find if an ISO path is http or nfs location,
    then get an ISO
    """
    if os.path.isfile(iso_source_path):
        # get iso via nfs
        get_nfs_iso()
    else:
        # get iso via http
        get_http_iso()

def create_mount_location():
    """
    Create mount location
    """
    try:
        if not os.path.exists("/mnt/%s" % NEW_DISTRO_NAME):
            logger.debug("Creating temp mount point /mnt/%s " % NEW_DISTRO_NAME)
            print("Creating temp mount point /mnt/%s " % NEW_DISTRO_NAME)
            os.makedirs("/mnt/%s" % NEW_DISTRO_NAME)
    except:
        logger.debug("Can't create temp mount point /mnt/%s" % NEW_DISTRO_NAME)
        sys.exit("Can't create temp mount point /mnt/%s" % NEW_DISTRO_NAME)

def mount_iso():
    """
    Mount ISO
    """
    try:
        subprocess.call(['mount -o loop %s%s /mnt/%s'
                         % (DOWNLOAD_PLACE, ISO_NAME, NEW_DISTRO_NAME)], shell=True)
        logger.debug("%s%s is loop mounted to /mnt/%s" % (DOWNLOAD_PLACE, ISO_NAME, NEW_DISTRO_NAME))
        print("%s%s is loop mounted to /mnt/%s" % (DOWNLOAD_PLACE, ISO_NAME, NEW_DISTRO_NAME))
    except:
        logger.debug("Can't mount %s%s" % (DOWNLOAD_PLACE, ISO_NAME))
        sys.exit("Can't mount %s%s" % (DOWNLOAD_PLACE, ISO_NAME))

def import_distro(nickname=NEW_DISTRO_NAME):
    """
    Import distro into Cobbler,
    nickname has default values (if user doesn't provide info for them)
    """
    try:
        subprocess.call(['cobbler import --path=/mnt/%s --name=%s --arch=%s --kickstart=%s'
                         % (NEW_DISTRO_NAME, nickname, distro_arch, KS_FILE)], shell=True)
        logger.debug(
            "%s was imported into Cobbler, still it's good to check import logs in /var/log/cobbler/tasks/" % NEW_DISTRO_NAME)
        print(
            "%s was imported into Cobbler, still it's good to check import logs in /var/log/cobbler/tasks/" % NEW_DISTRO_NAME)
    except:
        logger.debug("Can't import %s into Cobbler" % NEW_DISTRO_NAME)
        sys.exit("Can't import %s into Cobbler" % NEW_DISTRO_NAME)

def cleanup():
    """
    Cleanup: unmount /mnt/NEW_DISTRO_NAME, remove directory and downloaded ISO
    """
    try:
        subprocess.call(['umount /mnt/%s' % NEW_DISTRO_NAME], shell=True)
        logger.debug("Unmount /mnt/%s" % NEW_DISTRO_NAME)
        print("Unmount /mnt/%s" % NEW_DISTRO_NAME)
    except:
        logger.debug("Can't umount  /mnt/%s" % NEW_DISTRO_NAME)
        sys.exit("Can't umount /mnt/%s" % NEW_DISTRO_NAME)
    try:
        subprocess.call(['rmdir /mnt/%s' % NEW_DISTRO_NAME], shell=True)
        logger.debug("Remove directory /mnt/%s" % NEW_DISTRO_NAME)
        print("Remove directory /mnt/%s" % NEW_DISTRO_NAME)
    except:
        logger.debug("Can't remove directory /mnt/%s" % NEW_DISTRO_NAME)
        sys.exit("Can't remove directory /mnt/%s" % NEW_DISTRO_NAME)
    try:
        subprocess.call(['rm -f %s%s' % (DOWNLOAD_PLACE, ISO_NAME)], shell=True)
        logger.debug("Remove %s%s" % (DOWNLOAD_PLACE, ISO_NAME))
        print("Remove %s%s" % (DOWNLOAD_PLACE, ISO_NAME))
    except:
        logger.debug("Can't remove %s%s" % (DOWNLOAD_PLACE, ISO_NAME))
        sys.exit("Can't remove %s%s" % (DOWNLOAD_PLACE, ISO_NAME))


def cobbler_sync():
    """
    The command 'cobbler sync' has to be run so /etc/rsyncd.conf is updated.
    This is important on Master Cobbler since a distro will be replicated.
    """
    try:
        subprocess.call(['cobbler sync'], shell=True)
        logger.debug("Run cobbler sync command")
        print("Run cobbler sync command")
    except:
        logger.debug("Can't run cobbler sync command")
        sys.exit("Can't run cobbler sync command")

#
# ----- MAIN --------------

if __name__ == '__main__':
    # print 'This program is being run by itself'

    if not VALID_ARCH.match(distro_arch):
        sys.exit("%s is not valid architecture" % distro_arch)
    else:
        find_download_location()
        is_cobbler_installed()
        is_distro_present()
        find_iso_path_type_and_get_iso()
        create_mount_location()
        mount_iso()
        if nickname:
            import_distro(nickname)
        else:
            import_distro()
        cleanup()
        cobbler_sync()

# else:
# print 'I am being imported from another module'

# logger.debug("\n")
sys.exit(0)


