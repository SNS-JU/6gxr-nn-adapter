import requests
import urllib3
import logging
import copy
import time

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("osm")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Osm:
    """Class for communicating with an OSM component via a REST API."""

    def __init__(self, config):
        """
        Initialize an Osm instance.

        Args:
            config (dict): The main configuration.
        """
        self.config = config
        self.apps = []

    def startVms(self):
        """
        Start all virtual machines in OpenStack.

        Raises:
            Exception: If starting the VMs fails.
        """
        resp = requests.post(f"{self.config["osmBaseUrl"]}/osm_create", json={
            "applications": self.apps
        })

        if resp.status_code != 200:
            logger.error(f"Starting VMs failed; StatusCode={resp.status_code}")
            raise Exception(f"Starting VMs failed!")

        respJson = resp.json()

        logger.debug(f"VMs started; VMData={respJson}")

    def stopRunningVms(self):
        """
        Stop all virtual machines in OpenStack.

        Raises:
            Exception: If retrieving or stopping any running VMs fails.
        """
        resp = requests.get(f"{self.config["osmBaseUrl"]}/osm_info")

        if resp.status_code != 200:
            logger.error(f"Retrieving all running VMs failed; StatusCode={resp.status_code}")
            raise Exception("Error retrieving all running VMs!")

        respJson = resp.json()

        if not respJson:
            logger.debug("No running VMs found")
            return

        resp = requests.delete(f"{self.config["osmBaseUrl"]}/osm_delete")

        if resp.status_code != 200:
            logger.error(f"Failed to stop VMs; StatusCode={resp.status_code}")
            raise Exception("Error stopping all running VMs!")

    def initialize(self, apps):
        """
        Stop any running VMs and start new ones with the requested applications.

        Args:
            apps (list): The names of applications to run in the VMs.

        Raises:
            Exception: If starting the VMs fails.
        """
        # Deep copy as we extend the dictionary in this object
        self.apps = copy.deepcopy(apps)

        logger.debug("Initializing OSM: Stopping all running VMs")

        self.stopRunningVms()

        logger.debug("Initializing OSM: Starting VMs")

        self.startVms()

        logger.debug("Initializing OSM: Done")

    def cleanup(self):
        """
        Stop all running VMs in OpenStack.

        Raises:
            Exception: If stopping the VMs fails.
        """
        logger.debug("Cleaning up OSM: Stopping all running VMs")
        self.stopRunningVms()
        logger.debug("Cleaning up OSM: Done")

# For testing purposes
if __name__ == "__main__":
    osm = Osm({
        "osmBaseUrl": "http://10.50.150.103:5001"
    })
    osm.initialize(["Nginx", "Nginx"])
    time.sleep(120)
    osm.cleanup()
