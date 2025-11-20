import requests
import urllib3
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("ai")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Ai:
    """Class for communicating with the AI component via a REST API."""

    def __init__(self, config):
        """
        Initialize an Ai instance.

        Args:
            config (dict): The main configuration.
        """
        self.config = config

    def processKpis(self, kpis):
        """
        Send measured KPIs to the AI component and get DL/UL slice allocations in return.

        Args:
            kpis (list): Measured KPIs for each slice.

        Raises:
            Exception: If retrieving the allocation from the AI component fails.

        Returns:
            dict: DL/UL allocation response from the AI component.
        """
        aiParams = {
            "kpis": kpis
        }

        logger.debug(f"Sending KPIs for AI/ML to process: {kpis}")

        resp = requests.post(f"{self.config["aiBaseUrl"]}/allocate_resource", json=aiParams)

        if resp.status_code != 200:
            logger.error(f"Could not get allocation from AI/ML; StatusCode={resp.status_code}")
            raise Exception("Getting allocation from AI/ML failed")

        respJson = resp.json()

        logger.debug(f"AI/ML response: {respJson}")

        return respJson

# For testing purposes
if __name__ == "__main__":
    ai = Ai({
        "aiBaseUrl": "http://172.29.6.15:5000"
    })
    allocation = ai.processKpis([
        {
            "downlink": {"throughput": 2944.0, "latency": 6.06, "jitter": 0.705, "packetLoss": 0.0},
            "uplink": {"throughput": 6544.0, "latency": 9.486, "jitter": 1.959, "packetLoss": 0.0}
        }, {
            "downlink": {"throughput": 9920.0, "latency": 5.742652, "jitter": 1.127, "packetLoss": 0.0},
            "uplink": {"throughput": 277640.0, "latency": 10.868348, "jitter": 2.122, "packetLoss": 0.0}
        }
    ])
    dlSlice1 = allocation["downlink_allocation"]["slice1"]
    dlSlice2 = allocation["downlink_allocation"]["slice2"]
    ulSlice1 = allocation["uplink_allocation"]["slice1"]
    ulSlice2 = allocation["uplink_allocation"]["slice2"]
    logger.info(f"DL slice allocation; Slice1={dlSlice1}, Slice2={dlSlice2}")
    logger.info(f"UL slice allocation; Slice1={ulSlice1}, Slice2={ulSlice2}")
