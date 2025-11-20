from pathlib import Path
import requests
import urllib3
import logging
import json
import copy
import time

from utils import *

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("qosium")

currentDir = Path(__file__).parent
sliceConf1 = currentDir.parent / "conf" / "qosium1.json"
sliceConf2 = currentDir.parent / "conf" / "qosium2.json"
sliceConfFiles = [sliceConf1, sliceConf2]

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Qosium:
    """Class for communicating with Qosium Storage via a REST API."""

    def __init__(self, config):
        """
        Initialize a Qosium instance.

        Args:
            config (dict): The main configuration.
        """
        self.config = config
        self.slices = []

    def startMeasurement(self, sliceId, measParams):
        """
        Start a Qosium measurement according to the slice-specific configuration.

        Args:
            sliceId (str): The name of the slice.
            measParams (dict): The measurement parameters.

        Raises:
            Exception: If starting the measurement fails.

        Returns:
            str: The identifier of the measurement created in Qosium Storage.
        """
        logger.debug(f"Starting measurement; SliceId={sliceId}")

        resp = requests.post(f"{self.config["qosiumBaseUrl"]}/measurement/start", json=measParams)

        if resp.status_code != 200:
            logger.error(f"Starting measurement failed; StatusCode={resp.status_code}")
            raise Exception(f"Starting measurement for slice '{sliceId}' failed!")

        respJson = resp.json()

        internalName = None

        if "internalName" in respJson:
            internalName = respJson["internalName"]

        if "QSMeasId" not in respJson or respJson["QSMeasId"] == None or respJson["QSMeasId"] == "null":
            logger.error(f"Starting measurement failed; InternalName={internalName}")
            raise Exception(f"Starting measurement for slice '{sliceId}' failed!")

        logger.info(f"Measurement started; QSMeasId={respJson["QSMeasId"]}, InternalName={internalName}")

        return respJson["QSMeasId"]

    def stopRunningMeasurements(self):
        """
        Stop all running measurements in Qosium Storage.

        Raises:
            Exception: If retrieving or stopping any running measurements fails.
        """
        resp = requests.get(f"{self.config["qosiumBaseUrl"]}/measurement/status/all")

        if resp.status_code != 200:
            logger.error(f"Retrieving all running measurements failed; StatusCode={resp.status_code}")
            raise Exception("Error retrieving all running measurements!")

        respJson = resp.json()

        for item in respJson:
            if "QSMeasId" not in item:
                logger.warning("Encountered a non-existent measurement ID in running measurements")
                continue

            qsMeasId = item["QSMeasId"]

            if qsMeasId == None or qsMeasId == "null":
                logger.warning("Encountered a null measurement ID in running measurements")
                continue

            resp = requests.get(f"{self.config["qosiumBaseUrl"]}/measurement/stop?QSMeasId={qsMeasId}")

            if resp.status_code != 200:
                # XXX: Ignore possible error code because of a bug in Qosium REST API
                logger.warning(f"Failed to stop measurement; StatusCode={resp.status_code}, QSMeasId={qsMeasId}")

    def getLatestKpis(self, qsMeasId):
        """
        Get the latest KPI values of a Qosium measurement.

        Args:
            qsMeasId (str): The identifier of the running measurement.

        Raises:
            Exception: If retrieving the latest KPIs for the measurement fails.

        Returns:
            dict: The DL/UL KPIs (throughput, latency, jitter, packet loss ratio) of the measurement.
        """
        logger.debug(f"Getting the latest measurement result; QsMeasId={qsMeasId}")

        resp = requests.get(f"{self.config["qosiumBaseUrl"]}/AverageResult?qmId={qsMeasId}&limit=1&sort=desc")

        if resp.status_code != 200:
            logger.error(f"Failed to get the latest measurement result; QsMeasId={qsMeasId}, StatusCode={resp.status_code}")
            raise Exception("Failed to get the latest KPIs")

        respJson = resp.json()

        # Result set is empty or invalid
        if len(respJson) != 1:
            logger.error(f"Measurement result set invalid; QsMeasId={qsMeasId}")
            raise Exception("Invalid measurement set encountered")

        retval = {
            "time": respJson[0]["time"],
            "downlink": {
                "throughput": respJson[0]["secRecBitsS"],
                "latency": respJson[0]["sentDelayS"],
                "jitter": respJson[0]["sentJitter"],
                #"packetLoss": respJson[0]["sentPacketLoss"]
                "packetLoss": 0.0
            },
            "uplink": {
                "throughput": respJson[0]["primRecBitsS"],
                "latency": respJson[0]["recDelayS"],
                "jitter": respJson[0]["recJitter"],
                #"packetLoss": respJson[0]["recPacketLoss"]
                "packetLoss": 0.0
            }
        }

        logger.debug(f"Got DL/UL KPIs: {retval}")

        return retval

    def initialize(self, slices):
        """
        Stop any running measurements and start new ones according to the slice configuration.

        Args:
            slices (dict): The slice configuration (slice name and type).

        Raises:
            Exception: If stopping or starting Qosium measurements fails.
        """
        # Deep copy as we extend the dictionary in this object
        self.slices = copy.deepcopy(slices)

        logger.debug("Initializing Qosium: Stopping all running measurements")

        self.stopRunningMeasurements()

        logger.debug("Initializing Qosium: Starting slice-specific measurements")

        if not self.slices:
            # No slices defined; use the default slice ID and UE #1
            measParams = json.loads(readFileContents(sliceConfFiles[0]))
            measParams["measurement_description"] = f"SliceId={self.config["defaultSliceId"]}"

            logger.debug("No slices defined; use default slice ID")

            self.startMeasurement(self.config["defaultSliceId"], measParams)

        for index, item in enumerate(self.slices):
            measParams = json.loads(readFileContents(sliceConfFiles[index]))
            measParams["measurement_description"] = f"SliceId={item["id"]}"

            # Start measurement and store measurement ID in the internal slices variable
            self.slices[index]["qsMeasId"] = self.startMeasurement(item["id"], measParams)

        logger.debug("Initializing Qosium: Done")

    def cleanup(self):
        """
        Stop all running measurements in Qosium Storage.

        Raises:
            Exception: If stopping the running measurements fails.
        """
        logger.debug("Cleaning up Qosium: Stopping all running measurements")
        self.stopRunningMeasurements()
        logger.debug("Cleaning up Qosium: Done")

    def getKpisPerSlice(self):
        """
        Get the KPIs of all Qosium measurements (all slices).

        Raises:
            Exception: If retrieving the latest KPIs from the measurements fails.

        Returns:
            list: The measured KPIs for each slice.
        """
        kpis = []

        for item in self.slices:
            kpis.append(self.getLatestKpis(item["qsMeasId"]))

        return kpis

# For testing purposes
if __name__ == "__main__":
    qosium = Qosium({
        "defaultSliceId": "b84725bc-955a-44bb-9327-21c9d7eb5f65",
        "qosiumBaseUrl": "http://172.29.12.66:8080"
    })
    qosium.initialize([
        {"id": "5480f617-8d26-4ece-8b5a-a811b08f0012", "type": "eMBB"},
        {"id": "c969da01-609b-4c71-ae96-1bece0ebf6c2", "type": "uRLLC"}
    ])
    kpis = qosium.getKpisPerSlice()
    logger.info(kpis)
    time.sleep(2)
    qosium.cleanup()
