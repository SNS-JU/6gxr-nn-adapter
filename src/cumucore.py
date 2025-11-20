from pathlib import Path
import requests
import logging
import urllib3
import json
import time

from utils import *

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("cumucore")

currentDir = Path(__file__).parent
sliceConfFile = currentDir.parent / "conf" / "slice.json"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Cumucore:
    """Class for communicating with Cumucore via a REST API."""

    def __init__(self, config):
        """
        Initialize a Cumucore instance.

        Args:
            config (dict): The main configuration.
        """
        self.config = config

    def sliceExists(self, slices, sliceName):
        """
        Check whether a slice exists in a slice list.

        Args:
            slices (list): List of existing slices in Cumucore.
            sliceName (str): Name of the slice to search for in the list.

        Returns:
            bool: True if the slice exists in the submitted list.
        """
        return (next((item for item in slices if item["sliceName"] == sliceName), None) != None)

    def deleteSlice(self, sliceName):
        """
        Delete a slice in Cumucore via a REST API call.

        Args:
            sliceName (str): The name of the slice to remove.

        Raises:
            Exception: If deleting the slice fails.
        """
        logger.debug(f"Deleting existing Cumucore slice '{sliceName}'")

        resp = requests.delete(f"{self.config["cumucoreBaseUrl"]}/api/v1.0/network-slice/slice-instance/" + sliceName, verify=False)

        if resp.status_code != 200:
            raise Exception("Deleting Cumucore slice failed!")

    def deleteExistingSlices(self):
        """
        Delete all configured slices that exist in Cumucore.

        Raises:
            Exception: If retrieving or deleting any Cumucore slices fails.
        """
        logger.debug("Retrieving all existing Cumucore slices")

        resp = requests.get(f"{self.config["cumucoreBaseUrl"]}/api/v1.0/network-slice/slice-instance", verify=False)

        if resp.status_code != 200:
            raise Exception("Retrieving existing Cumucore slices failed!")

        existingSlices = json.loads(resp.text)["Data"]

        # Delete all existing (configured) slices
        for item in self.config["slices"]:
            if self.sliceExists(existingSlices, item["id"]):
                self.deleteSlice(item["id"])

    def createSlices(self):
        """
        Create all configured slices in Cumucore via a REST API call.

        Raises:
            Exception: If creating slices in Cumucore fails.
        """
        logger.debug("Creating Cumucore slices")

        # Get the Cumucore REST API request payload template
        template = json.loads(readFileContents(sliceConfFile))

        for item in self.config["slices"]:
            template["sliceName"] = item["id"]
            template["serviceProfile"]["sNSSAIList"] = item["sNSSAIList"]
            template["networkSliceSubnet"]["sliceProfile"]["sNSSAIList"] = item["sNSSAIList"]

            logger.debug(f"Creating Cumucore slice '{item["id"]}'; SST={item["sNSSAIList"]}")

            resp = requests.post(f"{self.config["cumucoreBaseUrl"]}/api/v1.0/network-slice/slice-instance", json=template, verify=False)

            if resp.status_code != 200:
                raise Exception(f"Creating Cumucore slice '{item["id"]}' failed!")

    def initialize(self):
        """
        Delete existing slices and create new ones according to the configuration.

        Raises:
            Exception: If deleting or creating slices fails.
        """
        self.deleteExistingSlices()
        self.createSlices()

    def cleanup(self):
        """
        Delete all slices currently existing in Cumucore.
        """
        self.deleteExistingSlices()

# For testing purposes
if __name__ == "__main__":
    cumucore = Cumucore({
        "defaultSliceId": "b84725bc-955a-44bb-9327-21c9d7eb5f65",
        "slices": [
            {"id": "5480f617-8d26-4ece-8b5a-a811b08f0012", "sNSSAIList": [{"sst": 1, "sd": "000002"}]},
            {"id": "c969da01-609b-4c71-ae96-1bece0ebf6c2", "sNSSAIList": [{"sst": 1, "sd": "000003"}]}
        ],
        "cumucoreBaseUrl": "https://172.29.19.2:3000"
    })
    cumucore.initialize()
    time.sleep(10)
    cumucore.cleanup()
