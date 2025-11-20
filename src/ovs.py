import json
import socket
import logging
import time

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("ovs")

class Ovs:
    """Class for communicating with Open vSwitch using RPC messages."""

    INGRESS_POLICING_RATE = "ingress_policing_rate"
    INGRESS_POLICING_BURST = "ingress_policing_burst"

    def __init__(self, config):
        """
        Initialize an Ovs instance.

        Args:
            config (dict): The main configuration.
        """
        self.config = config

    def getJsonRpcRequest(self, interface, rate, burst):
        """
        Construct and return an RPC message to set the policing rate and burst.

        Args:
            interface (str): The name of the OvS interface to use.
            rate (int): The ingress policing rate.
            burst (int): The ingress policing burst.

        Returns:
            dict: The constructed RPC message.
        """
        return {
            "id": 1,
            "method": "transact",
            "params": [
                "Open_vSwitch", {
                    "op": "update",
                    "table": "Interface",
                    "where": [
                        ["name", "==", interface]
                    ],
                    "row": {
                        self.INGRESS_POLICING_RATE: rate,
                        self.INGRESS_POLICING_BURST: burst
                    }
                }
            ]
        }

    def sendJsonRpcRequest(self, host, port, request):
        """
        Send an RPC message to OvS via a TCP socket.

        Args:
            host (str): The host name or IP address of OvS.
            port (int): The port on which OvS is listening.
            request (dict): The RPC message to send.

        Raises:
            Exception: If sending the RPC message fails.

        Returns:
            dict: The RPC response from OvS.
        """
        logger.debug(f"Sending request to OvS: {request}")
        response = None

        try:
            sock = socket.create_connection((host, port))
            sock.sendall(json.dumps(request).encode() + b"\n")
            response = sock.recv(4096)
            sock.close()
        except Exception as e:
            raise Exception(f"Error sending request to OvS: {str(e)}")

        return json.loads(response.decode())

    def setInterfaceValues(self, interfaceName, rate, burst):
        """
        Construct an RPC message for the given interface and send it to OvS.

        Args:
            interfaceName (str): The name of the interface to configure.
            rate (int): The ingress policing rate to set.
            burst (int): The ingress policing burst to set.

        Raises:
            Exception: If setting the rate or burst value on OvS fails.
        """
        request = self.getJsonRpcRequest(
            interfaceName, rate, burst)

        response = self.sendJsonRpcRequest(
            self.config["ovsHostName"],
            self.config["ovsHostPort"],
            request
        )

        logger.debug(f"OvS response: {response}")

        if response["error"] != None:
            raise Exception(f"Error setting rate/burst value: {response["error"] }")

    def setDownlinkUplinkValues(self, allocation):
        """
        Set the DL/UL rate and burst values for each configured slice.

        Args:
            allocation (dict): Slice-specific allocation from AI.

        Raises:
            Exception: If setting the rate or burst values on OvS fails.
        """
        for index, slice in enumerate(self.config["slices"]):
            dlRate = allocation[index]["dl"]["rate"]
            dlBurst = allocation[index]["dl"]["burst"]
            interface = slice["downlinkOvsInterface"]

            logger.debug(f"Setting DL rate/burst for slice '{slice["id"]}': {dlRate}/{dlBurst} ({interface})")
            self.setInterfaceValues(interface, dlRate, dlBurst)

            ulRate = allocation[index]["ul"]["rate"]
            ulBurst = allocation[index]["ul"]["burst"]
            interface = slice["uplinkOvsInterface"]

            logger.debug(f"Setting UL rate/burst for slice '{slice["id"]}': {ulRate}/{ulBurst} ({interface})")
            self.setInterfaceValues(interface, ulRate, ulBurst)

# For testing purposes
if __name__ == "__main__":
    ovs = Ovs({
        "slices": [
            {
                "id": "5480f617-8d26-4ece-8b5a-a811b08f0012",
                "sNSSAIList": [{"sst": 1, "sd": "000003"}],
                "downlinkOvsInterface": "cumucore-upf4-ranup-vhost",
                "uplinkOvsInterface": "cumucore-upf4-n6-vhost"
            },
            {
                "id": "c969da01-609b-4c71-ae96-1bece0ebf6c2",
                "sNSSAIList": [{"sst": 1, "sd": "000002"}],
                "downlinkOvsInterface": "cumucore-upf5-ranup-vhost",
                "uplinkOvsInterface": "cumucore-upf5-n6-vhost"
            }
        ],
        "ovsHostName": "localhost",
        "ovsHostPort": 6640
    })
    ovs.setDownlinkUplinkValues([
        {"dl": {"rate": 10000, "burst": 5000}, "ul": {"rate": 20000, "burst": 10000}},
        {"dl": {"rate": 30000, "burst": 15000}, "ul": {"rate": 40000, "burst": 20000}}
    ])
    time.sleep(20)
    ovs.setDownlinkUplinkValues([
        {"dl": {"rate": 0, "burst": 0}, "ul": {"rate": 0, "burst": 0}},
        {"dl": {"rate": 0, "burst": 0}, "ul": {"rate": 0, "burst": 0}}
    ])
